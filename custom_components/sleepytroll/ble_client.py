"""Bluetooth client for Sleepytroll."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bleak import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from .const import NOTIFY_UUID, WRITE_UUID
from .protocol import SleepytrollState, parse_notification, state_from_packets

_LOGGER = logging.getLogger(__name__)


class SleepytrollBleClient:
    """Proxy-aware BLE client for Sleepytroll."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialize client."""
        self.hass = hass
        self.address = address
        self.name = name
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._state_callback: Callable[[SleepytrollState], None] | None = None

    @callback
    def set_state_callback(
        self, callback_func: Callable[[SleepytrollState], None]
    ) -> None:
        """Set state callback."""
        self._state_callback = callback_func

    @callback
    def async_update_from_service_info(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Update cached advertisement details."""
        if service_info.name:
            self.name = service_info.name

    async def async_connect(self) -> None:
        """Connect and subscribe to notifications."""
        if self._client and self._client.is_connected:
            return

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise ConfigEntryNotReady(
                f"No connectable Bluetooth adapter or proxy can reach {self.address}"
            )

        try:
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.name,
                ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                ),
            )
            await self._client.start_notify(NOTIFY_UUID, self._notification_handler)
        except BleakError as err:
            raise ConfigEntryNotReady(
                f"Bluetooth connection failed for {self.name}"
            ) from err

    async def async_disconnect(self) -> None:
        """Disconnect client."""
        client = self._client
        self._client = None
        if client and client.is_connected:
            try:
                await client.stop_notify(NOTIFY_UUID)
            except BleakError:
                _LOGGER.debug("Sleepytroll stop_notify failed", exc_info=True)
            await client.disconnect()

    async def async_write(self, command: str | bytes) -> None:
        """Write a command."""
        async with self._lock:
            await self.async_connect()
            assert self._client is not None
            payload = command.encode() if isinstance(command, str) else command
            try:
                await self._client.write_gatt_char(WRITE_UUID, payload, response=True)
            except BleakError as err:
                await self.async_disconnect()
                raise HomeAssistantError(
                    f"Failed to send command to {self.name}"
                ) from err

    async def async_refresh(self) -> SleepytrollState:
        """Ensure connection and return current state placeholder."""
        await self.async_connect()
        return SleepytrollState()

    def _notification_handler(self, _sender: int, data: bytearray) -> None:
        """Handle BLE notification."""
        if self._state_callback is None:
            return
        try:
            packets = parse_notification(bytes(data))
        except ValueError:
            _LOGGER.debug("Ignoring unparsable Sleepytroll notification: %r", data)
            return
        if not packets:
            return
        state = state_from_packets(packets)
        self._state_callback(state)
