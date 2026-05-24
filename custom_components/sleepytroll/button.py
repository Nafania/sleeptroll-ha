"""Button entities for Sleepytroll."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SleepytrollCoordinator
from .entity import SleepytrollEntity
from .protocol import command_acknowledge, command_play, command_reset

_LOGGER = logging.getLogger(__name__)

CommandBuilder = Callable[[], str | bytes]


@dataclass(frozen=True, kw_only=True)
class SleepytrollButtonDescription(ButtonEntityDescription):
    """Sleepytroll button entity metadata."""

    command_builder: CommandBuilder


BUTTON_DESCRIPTIONS: Final = (
    SleepytrollButtonDescription(
        key="start_rocking",
        translation_key="start_rocking",
        icon="mdi:play",
        command_builder=lambda: command_play(True),
    ),
    SleepytrollButtonDescription(
        key="pause_rocking",
        translation_key="pause_rocking",
        icon="mdi:pause",
        command_builder=lambda: command_play(False),
    ),
    SleepytrollButtonDescription(
        key="sync_state",
        translation_key="sync_state",
        icon="mdi:sync",
        entity_category=EntityCategory.DIAGNOSTIC,
        command_builder=command_acknowledge,
    ),
    SleepytrollButtonDescription(
        key="reset",
        translation_key="reset",
        icon="mdi:restart-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        command_builder=command_reset,
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
    """Set up Sleepytroll button entities."""
    coordinator: SleepytrollCoordinator = entry.runtime_data
    async_add_entities(
        SleepytrollButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    )


class SleepytrollButton(SleepytrollEntity, ButtonEntity):
    """Button entity for Sleepytroll commands."""

    entity_description: SleepytrollButtonDescription

    def __init__(
        self,
        coordinator: SleepytrollCoordinator,
        description: SleepytrollButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key, description.translation_key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        command = _command_to_str(self.entity_description.command_builder())
        _LOGGER.debug(
            "Pressing Sleepytroll button address=%s key=%s command=%r",
            self.coordinator.client.address,
            self.entity_description.key,
            command,
        )
        await self.coordinator.async_send_command(command)
