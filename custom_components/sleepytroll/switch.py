"""Switch entities for Sleepytroll."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SleepytrollCoordinator
from .entity import SleepytrollEntity
from .protocol import command_play

_LOGGER = logging.getLogger(__name__)


def _command_to_str(command: str | bytes) -> str:
    """Normalize protocol command output for the BLE client."""
    if isinstance(command, bytes):
        return command.decode()
    return command


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sleepytroll switch entities."""
    coordinator: SleepytrollCoordinator = entry.runtime_data
    async_add_entities([SleepytrollRockingSwitch(coordinator)])


class SleepytrollRockingSwitch(SleepytrollEntity, SwitchEntity):
    """Switch that starts or pauses rocking."""

    def __init__(self, coordinator: SleepytrollCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "rocking", "rocking")
        self._is_on = False

    @property
    def is_on(self) -> bool:
        """Return whether rocking is active."""
        status = getattr(self.coordinator.data, "rocking_status", None)
        if status is None:
            return self._is_on
        if isinstance(status, str):
            normalized = status.lower()
            if normalized in {
                "on",
                "rocking",
                "running",
                "active",
                "start",
                "started",
                "listening",
            }:
                self._is_on = True
                return self._is_on
            if normalized in {
                "off",
                "paused",
                "stopped",
                "idle",
                "pause",
                "standby",
            }:
                self._is_on = False
                return self._is_on
        if isinstance(status, int):
            # Android app treats 1/2 as active and 3 as standby.
            if status in {1, 2}:
                self._is_on = True
            elif status in {0, 3}:
                self._is_on = False
            return self._is_on
        return self._is_on

    async def async_turn_on(self, **kwargs: object) -> None:
        """Start rocking."""
        _LOGGER.debug(
            "Turning Sleepytroll rocking on address=%s",
            self.coordinator.client.address,
        )
        await self.coordinator.async_send_command(_command_to_str(command_play(True)))
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: object) -> None:
        """Pause rocking."""
        _LOGGER.debug(
            "Turning Sleepytroll rocking off address=%s",
            self.coordinator.client.address,
        )
        await self.coordinator.async_send_command(_command_to_str(command_play(False)))
        self._is_on = False
        self.async_write_ha_state()
