"""Select entities for Sleepytroll."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SleepytrollCoordinator
from .entity import SleepytrollEntity
from .protocol import command_mode, command_sleep_program

MODE_CONTINUOUS: Final = "continuous"
MODE_SENSOR: Final = "sensor"
MODE_BABY_MONITOR: Final = "baby_monitor"
SLEEP_SHORT: Final = "sleep_short"
SLEEP_MEDIUM: Final = "sleep_medium"
SLEEP_LONG: Final = "sleep_long"


@dataclass(frozen=True, kw_only=True)
class SleepytrollSelectOption:
    """Sleepytroll select option metadata."""

    option: str
    command_value: str
    sleep_program: bool = False


OPTIONS: Final = (
    SleepytrollSelectOption(option=MODE_CONTINUOUS, command_value="continuous"),
    SleepytrollSelectOption(option=MODE_SENSOR, command_value="sensor"),
    SleepytrollSelectOption(option=MODE_BABY_MONITOR, command_value="baby_monitor"),
    SleepytrollSelectOption(
        option=SLEEP_SHORT, command_value="short", sleep_program=True
    ),
    SleepytrollSelectOption(
        option=SLEEP_MEDIUM, command_value="medium", sleep_program=True
    ),
    SleepytrollSelectOption(
        option=SLEEP_LONG, command_value="long", sleep_program=True
    ),
)
OPTION_BY_VALUE: Final = {description.option: description for description in OPTIONS}


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
    """Set up Sleepytroll select entities."""
    coordinator: SleepytrollCoordinator = entry.runtime_data
    async_add_entities([SleepytrollModeSelect(coordinator)])


class SleepytrollModeSelect(SleepytrollEntity, SelectEntity):
    """Select Sleepytroll mode or sleep program."""

    _attr_options = [description.option for description in OPTIONS]

    def __init__(self, coordinator: SleepytrollCoordinator) -> None:
        """Initialize the select."""
        super().__init__(coordinator, "mode", "mode")
        self._current_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return last mode or sleep program selected from Home Assistant."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Select a mode or sleep program."""
        description = OPTION_BY_VALUE[option]
        if description.sleep_program:
            command = command_sleep_program(description.command_value)
        else:
            command = command_mode(description.command_value)
        await self.coordinator.async_send_command(_command_to_str(command))
        self._current_option = option
        self.async_write_ha_state()
