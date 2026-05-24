"""Sensor entities for Sleepytroll."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SleepytrollCoordinator
from .entity import SleepytrollEntity


@dataclass(frozen=True, kw_only=True)
class SleepytrollSensorDescription(SensorEntityDescription):
    """Sleepytroll sensor entity metadata."""

    state_attr: str
    fallback_attrs: tuple[str, ...] = ()


SENSOR_DESCRIPTIONS: Final = (
    SleepytrollSensorDescription(
        key="battery",
        translation_key="battery",
        state_attr="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SleepytrollSensorDescription(
        key="rocking_status",
        translation_key="rocking_status",
        state_attr="rocking_status",
    ),
    SleepytrollSensorDescription(
        key="rocking_intensity",
        translation_key="rocking_intensity",
        state_attr="rocking_intensity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SleepytrollSensorDescription(
        key="sound_sensitivity",
        translation_key="sound_sensitivity",
        state_attr="sound_sensitivity",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SleepytrollSensorDescription(
        key="movement_sensitivity",
        translation_key="movement_sensitivity",
        state_attr="movement_sensitivity",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SleepytrollSensorDescription(
        key="remaining_time",
        translation_key="remaining_time",
        state_attr="remaining_time_seconds",
        fallback_attrs=("remaining_time",),
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SleepytrollSensorDescription(
        key="rocker_type",
        translation_key="rocker_type",
        state_attr="rocker_type",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SleepytrollSensorDescription(
        key="sleep_program_stage",
        translation_key="sleep_program_stage",
        state_attr="sleep_program_stage",
    ),
    SleepytrollSensorDescription(
        key="microphone_status",
        translation_key="microphone_status",
        state_attr="microphone_status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SleepytrollSensorDescription(
        key="battery_cycle_count",
        translation_key="battery_cycle_count",
        state_attr="battery_cycle_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SleepytrollSensorDescription(
        key="device_total_time",
        translation_key="device_total_time",
        state_attr="device_total_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SleepytrollSensorDescription(
        key="motor_time",
        translation_key="motor_time",
        state_attr="motor_time_minutes",
        fallback_attrs=("motor_time",),
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SleepytrollSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        state_attr="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SleepytrollSensorDescription(
        key="serial_number",
        translation_key="serial_number",
        state_attr="serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SleepytrollSensorDescription(
        key="light_value",
        translation_key="light_value",
        state_attr="light_value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sleepytroll sensor entities."""
    coordinator: SleepytrollCoordinator = entry.runtime_data
    async_add_entities(
        SleepytrollSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SleepytrollSensor(SleepytrollEntity, SensorEntity):
    """Sensor entity for parsed Sleepytroll notification state."""

    entity_description: SleepytrollSensorDescription

    def __init__(
        self,
        coordinator: SleepytrollCoordinator,
        description: SleepytrollSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key, description.translation_key)
        self.entity_description = description

    @property
    def native_value(self) -> int | float | str | None:
        """Return current parsed value."""
        state = self.coordinator.data
        value = getattr(state, self.entity_description.state_attr, None)
        for fallback_attr in self.entity_description.fallback_attrs:
            if value is not None:
                break
            value = getattr(state, fallback_attr, None)
        return value
