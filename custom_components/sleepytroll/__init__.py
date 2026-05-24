"""The Sleepytroll integration."""

from __future__ import annotations

import logging
import re
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_NAME, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

_LEGACY_NUMERIC_ENTITY_RE = re.compile(r"^sleepytroll_.+_\d+$")

_ACTIVE_ENTITY_ID_KEYS: Final = (
    (Platform.SWITCH, "rocking"),
    (Platform.SELECT, "mode"),
    (Platform.NUMBER, "duration"),
    (Platform.NUMBER, "rocking_intensity"),
    (Platform.NUMBER, "sound_sensitivity"),
    (Platform.NUMBER, "movement_sensitivity"),
    (Platform.NUMBER, "light_sensitivity"),
    (Platform.BUTTON, "sync_state"),
    (Platform.BUTTON, "reset"),
    (Platform.SENSOR, "battery"),
    (Platform.SENSOR, "rocking_status"),
    (Platform.SENSOR, "rocking_intensity"),
    (Platform.SENSOR, "sound_sensitivity"),
    (Platform.SENSOR, "movement_sensitivity"),
    (Platform.SENSOR, "remaining_time"),
    (Platform.SENSOR, "rocker_type"),
    (Platform.SENSOR, "sleep_program_stage"),
    (Platform.SENSOR, "microphone_status"),
    (Platform.SENSOR, "battery_cycle_count"),
    (Platform.SENSOR, "device_total_time"),
    (Platform.SENSOR, "motor_time"),
    (Platform.SENSOR, "firmware_version"),
    (Platform.SENSOR, "serial_number"),
)

_DEPRECATED_ENTITY_ID_KEYS: Final = (
    (Platform.BUTTON, "acknowledge"),
    (Platform.BUTTON, "start_rocking"),
    (Platform.BUTTON, "pause_rocking"),
    (Platform.SENSOR, "light_value"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Sleepytroll from a config entry."""
    from homeassistant.components import bluetooth

    from .ble_client import SleepytrollBleClient
    from .coordinator import SleepytrollCoordinator

    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)
    _LOGGER.debug("Setting up Sleepytroll entry address=%s name=%s", address, name)
    _async_remove_deprecated_entities(hass, address)
    _async_repair_legacy_numeric_entity_ids(hass, address)

    client = SleepytrollBleClient(hass, address, name)
    coordinator = SleepytrollCoordinator(hass, entry, client)

    @callback
    def _async_bluetooth_update(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        """Keep HA Bluetooth's latest source data warm for this address."""
        _LOGGER.debug(
            "Bluetooth update for Sleepytroll address=%s change=%s source=%s rssi=%s",
            service_info.address,
            _change,
            getattr(service_info, "source", None),
            getattr(service_info, "rssi", None),
        )
        client.async_update_from_service_info(service_info)

    _LOGGER.debug("Registering Sleepytroll Bluetooth callback address=%s", address)
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_bluetooth_update,
            {"address": address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    try:
        _LOGGER.debug("Checking Sleepytroll connectability address=%s", address)
        await client.async_connect()
        _LOGGER.debug("Running first Sleepytroll refresh address=%s", address)
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        _LOGGER.debug("Sleepytroll first refresh not ready address=%s", address)
        await client.async_disconnect()
        raise
    except Exception as err:
        _LOGGER.debug("Sleepytroll first refresh failed address=%s", address)
        await client.async_disconnect()
        raise ConfigEntryNotReady(f"Could not connect to {name}") from err

    entry.runtime_data = coordinator
    _LOGGER.debug(
        "Forwarding Sleepytroll platforms address=%s platforms=%s",
        address,
        PLATFORMS,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Sleepytroll setup complete address=%s", address)
    return True


@callback
def _async_remove_deprecated_entities(hass: HomeAssistant, address: str) -> None:
    """Remove entities replaced by clearer controls."""
    entity_registry = er.async_get(hass)
    for platform, key in _DEPRECATED_ENTITY_ID_KEYS:
        entity_id = entity_registry.async_get_entity_id(
            platform,
            DOMAIN,
            f"{address}_{key}",
        )
        if entity_id is not None:
            _LOGGER.debug("Removing deprecated Sleepytroll entity %s", entity_id)
            entity_registry.async_remove(entity_id)


@callback
def _async_repair_legacy_numeric_entity_ids(
    hass: HomeAssistant, address: str
) -> None:
    """Rename legacy auto-generated numeric entity IDs to HA-style keys."""
    entity_registry = er.async_get(hass)
    for platform, key in _ACTIVE_ENTITY_ID_KEYS:
        entity_id = entity_registry.async_get_entity_id(
            platform,
            DOMAIN,
            f"{address}_{key}",
        )
        if entity_id is None:
            continue
        new_entity_id = _legacy_numeric_entity_id(entity_id, key)
        if new_entity_id is None:
            continue
        if entity_registry.async_get(new_entity_id) is not None:
            _LOGGER.debug(
                "Skipping Sleepytroll legacy entity ID repair because target exists: "
                "%s -> %s",
                entity_id,
                new_entity_id,
            )
            continue
        _LOGGER.debug(
            "Repairing Sleepytroll legacy entity ID %s -> %s",
            entity_id,
            new_entity_id,
        )
        entity_registry.async_update_entity(entity_id, new_entity_id=new_entity_id)


def _legacy_numeric_entity_id(entity_id: str, key: str) -> str | None:
    """Return repaired entity ID for legacy sleepytroll_*_<number> IDs."""
    domain, object_id = entity_id.split(".", 1)
    if not _LEGACY_NUMERIC_ENTITY_RE.match(object_id):
        return None
    prefix, _legacy_suffix = object_id.rsplit("_", 1)
    if prefix.endswith(f"_{key}"):
        return None
    return f"{domain}.{prefix}_{key}"


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    _LOGGER.debug("Unloading Sleepytroll entry address=%s", address)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
        _LOGGER.debug("Sleepytroll entry unloaded address=%s", address)
    else:
        _LOGGER.debug("Sleepytroll platform unload failed address=%s", address)
    return unload_ok
