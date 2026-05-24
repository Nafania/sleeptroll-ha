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

    client = SleepytrollBleClient(hass, address, name)
    coordinator = SleepytrollCoordinator(hass, entry, client)

    @callback
    def _async_bluetooth_update(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        """Keep HA Bluetooth's latest source data warm for this address."""
        client.async_update_from_service_info(service_info)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_bluetooth_update,
            {"address": address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(f"Could not connect to {name}") from err

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SleepytrollConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok
