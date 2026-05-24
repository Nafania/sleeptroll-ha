"""Coordinator for Sleepytroll."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .ble_client import SleepytrollBleClient
from .const import DOMAIN
from .protocol import SleepytrollState

_LOGGER = logging.getLogger(__name__)


class SleepytrollCoordinator(DataUpdateCoordinator[SleepytrollState]):
    """Coordinate Sleepytroll BLE state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SleepytrollBleClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=10),
        )
        self.client = client
        self.client.set_state_callback(self._async_handle_state)
        self._state = SleepytrollState()

    async def _async_update_data(self) -> SleepytrollState:
        """Fetch data."""
        await self.client.async_connect()
        return self._state

    @callback
    def _async_handle_state(self, state: SleepytrollState) -> None:
        """Merge notification state and update listeners."""
        self._state = self._state.merge(state)
        self.async_set_updated_data(self._state)

    async def async_send_command(self, command: str | bytes) -> None:
        """Send command and request entity refresh."""
        await self.client.async_write(command)
        self.async_set_updated_data(self._state)

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        await self.client.async_disconnect()
