"""Config flow for Sleepytroll."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import CONF_MANUAL_ADDRESS, DEFAULT_NAME, DOMAIN, SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


def _normalize_address(address: str) -> str:
    """Normalize a Bluetooth address for unique IDs."""
    return address.strip().replace("-", ":").upper()


def _discovery_name(discovery_info: BluetoothServiceInfoBleak) -> str:
    """Return a stable display name for a discovery."""
    return discovery_info.name or DEFAULT_NAME


def _looks_like_sleepytroll(discovery_info: BluetoothServiceInfoBleak) -> bool:
    """Return true if discovery data is likely a Sleepytroll."""
    service_uuids = {uuid.lower() for uuid in discovery_info.service_uuids}
    return (
        SERVICE_UUID in service_uuids
        or _discovery_name(discovery_info).lower().startswith("sleepytroll")
    )


class SleepytrollConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sleepytroll."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        _LOGGER.debug("Discovered Sleepytroll candidate: %s", discovery_info.as_dict())
        if not _looks_like_sleepytroll(discovery_info):
            return self.async_abort(reason="not_supported")

        address = _normalize_address(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": f"{_discovery_name(discovery_info)} ({address})"
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        if user_input is not None:
            assert self._discovery_info is not None
            address = _normalize_address(self._discovery_info.address)
            return self.async_create_entry(
                title=_discovery_name(self._discovery_info),
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: _discovery_name(self._discovery_info),
                },
            )

        return self.async_show_form(step_id="bluetooth_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual add flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = (user_input.get(CONF_ADDRESS) or "").strip()
            manual_address = (user_input.get(CONF_MANUAL_ADDRESS) or "").strip()
            selected_address = _normalize_address(manual_address or address)
            if not selected_address:
                errors["base"] = "no_devices_found"
            else:
                await self.async_set_unique_id(selected_address)
                self._abort_if_unique_id_configured()

                discovery = self._discovered_devices.get(selected_address)
                name = _discovery_name(discovery) if discovery else DEFAULT_NAME
                return self.async_create_entry(
                    title=name,
                    data={CONF_ADDRESS: selected_address, CONF_NAME: name},
                )

        current_ids = self._async_current_ids(include_ignore=False)
        for discovery in async_discovered_service_info(self.hass, connectable=True):
            if not _looks_like_sleepytroll(discovery):
                continue
            address = _normalize_address(discovery.address)
            if address in current_ids or address in self._discovered_devices:
                continue
            self._discovered_devices[address] = discovery

        schema_fields: dict[Any, Any] = {}
        if self._discovered_devices:
            schema_fields[vol.Optional(CONF_ADDRESS)] = vol.In(
                {
                    address: f"{_discovery_name(info)} ({address})"
                    for address, info in self._discovered_devices.items()
                }
            )
        manual_key = (
            vol.Optional(CONF_MANUAL_ADDRESS)
            if self._discovered_devices
            else vol.Required(CONF_MANUAL_ADDRESS)
        )
        schema_fields[manual_key] = str

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
        )
