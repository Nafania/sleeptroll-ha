"""The Sleepytroll integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_NAME, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


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
    for platform, key in (
        (Platform.SWITCH, "rocking"),
        (Platform.BUTTON, "acknowledge"),
    ):
        entity_id = entity_registry.async_get_entity_id(
            platform,
            DOMAIN,
            f"{address}_{key}",
        )
        if entity_id is not None:
            _LOGGER.debug("Removing deprecated Sleepytroll entity %s", entity_id)
            entity_registry.async_remove(entity_id)


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
