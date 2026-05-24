"""Base entities for Sleepytroll."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SleepytrollCoordinator


class SleepytrollEntity(CoordinatorEntity[SleepytrollCoordinator]):
    """Base Sleepytroll entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SleepytrollCoordinator,
        key: str,
        translation_key: str,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.address}_{key}"
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.address)},
            name=coordinator.client.name,
            manufacturer="Sleepytroll",
            model="Baby Rocker Gen 2",
        )
