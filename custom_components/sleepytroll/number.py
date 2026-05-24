"""Number entities for Sleepytroll."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SleepytrollCoordinator
from .entity import SleepytrollEntity
from .protocol import (
    command_duration,
    command_light_sensitivity,
    command_movement_sensitivity,
    command_rocking_intensity,
    command_sound_sensitivity,
)

_LOGGER = logging.getLogger(__name__)

CommandBuilder = Callable[[int], str | bytes]


@dataclass(frozen=True, kw_only=True)
class SleepytrollNumberDescription(NumberEntityDescription):
    """Sleepytroll number entity metadata."""

    key: str
    translation_key: str
    state_attr: str
    native_min_value: float
    native_max_value: float
    native_step: float
    command_builder: CommandBuilder
    native_unit_of_measurement: str | None = None


NUMBER_DESCRIPTIONS: Final = (
    SleepytrollNumberDescription(
        key="duration",
        translation_key="duration",
        state_attr="duration",
        native_min_value=10,
        native_max_value=480,
        native_step=10,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        command_builder=command_duration,
    ),
    SleepytrollNumberDescription(
        key="rocking_intensity",
        translation_key="rocking_intensity",
        state_attr="rocking_intensity",
        native_min_value=20,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        command_builder=command_rocking_intensity,
    ),
    SleepytrollNumberDescription(
        key="sound_sensitivity",
        translation_key="sound_sensitivity",
        state_attr="sound_sensitivity",
        native_min_value=0,
        native_max_value=4,
        native_step=1,
        command_builder=command_sound_sensitivity,
    ),
    SleepytrollNumberDescription(
        key="movement_sensitivity",
        translation_key="movement_sensitivity",
        state_attr="movement_sensitivity",
        native_min_value=0,
        native_max_value=4,
        native_step=1,
        command_builder=command_movement_sensitivity,
    ),
    SleepytrollNumberDescription(
        key="light_sensitivity",
        translation_key="light_sensitivity",
        state_attr="light_value",
        native_min_value=0,
        native_max_value=100,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
        command_builder=command_light_sensitivity,
    ),
)


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
    """Set up Sleepytroll number entities."""
    coordinator: SleepytrollCoordinator = entry.runtime_data
    async_add_entities(
        SleepytrollNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    )


class SleepytrollNumber(SleepytrollEntity, NumberEntity):
    """Number entity for numeric Sleepytroll settings."""

    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: SleepytrollCoordinator,
        description: SleepytrollNumberDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, description.key, description.translation_key)
        self.entity_description = description
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._native_value: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return current numeric value."""
        state = self.coordinator.data
        value = getattr(state, self.entity_description.state_attr, None)
        if value is None:
            return self._native_value
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set a numeric Sleepytroll setting."""
        int_value = int(value)
        command = _command_to_str(self.entity_description.command_builder(int_value))
        _LOGGER.debug(
            "Setting Sleepytroll number address=%s key=%s value=%s command=%r",
            self.coordinator.client.address,
            self.entity_description.key,
            int_value,
            command,
        )
        await self.coordinator.async_send_command(command)
        if self.entity_description.key == "light_sensitivity" and int_value == 0:
            _LOGGER.debug(
                "Repeating Sleepytroll light_sensitivity=0 command after 200 ms "
                "address=%s",
                self.coordinator.client.address,
            )
            await asyncio.sleep(0.2)
            await self.coordinator.async_send_command(command)
        self._native_value = float(value)
        self.async_write_ha_state()
