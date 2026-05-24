"""The Sleepytroll integration."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .ble_client import SleepytrollBleClient
from .const import DEFAULT_NAME, PLATFORMS
from .coordinator import SleepytrollCoordinator

_LOGGER = logging.getLogger(__name__)

type SleepytrollConfigEntry = ConfigEntry[SleepytrollCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SleepytrollConfigEntry
) -> bool:
    """Set up Sleepytroll from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)
    _LOGGER.debug("Setting up Sleepytroll entry address=%s name=%s", address, name)

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
        _LOGGER.debug("Running first Sleepytroll refresh address=%s", address)
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        _LOGGER.debug("Sleepytroll first refresh not ready address=%s", address)
        raise
    except Exception as err:
        _LOGGER.debug("Sleepytroll first refresh failed address=%s", address)
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


async def async_unload_entry(
    hass: HomeAssistant, entry: SleepytrollConfigEntry
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
