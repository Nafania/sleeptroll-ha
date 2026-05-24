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
from .protocol import (
    FirstPacket,
    SleepytrollState,
    command_acknowledge,
    parse_notification,
    state_from_packets,
)

_LOGGER = logging.getLogger(__name__)


def _payload_for_log(payload: bytes) -> str:
    """Return readable BLE payload details for debug logs."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = "<non-utf8>"
    return f"text={text!r} hex={payload.hex()}"


def _service_info_for_log(
    service_info: bluetooth.BluetoothServiceInfoBleak | None,
) -> dict[str, object | None] | None:
    """Return stable Bluetooth service info fields for debug logs."""
    if service_info is None:
        return None
    return {
        "address": service_info.address,
        "name": service_info.name,
        "source": getattr(service_info, "source", None),
        "rssi": getattr(service_info, "rssi", None),
        "connectable": getattr(service_info, "connectable", None),
        "service_uuids": service_info.service_uuids,
    }


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
        self._identity_sync_sent = False
        self._identity_sync_task: asyncio.Task[None] | None = None

    @callback
    def set_state_callback(
        self, callback_func: Callable[[SleepytrollState], None]
    ) -> None:
        """Set state callback."""
        _LOGGER.debug("Registered Sleepytroll state callback address=%s", self.address)
        self._state_callback = callback_func

    @callback
    def async_update_from_service_info(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Update cached advertisement details."""
        _LOGGER.debug(
            "Sleepytroll advertisement update address=%s name=%s source=%s rssi=%s "
            "connectable=%s service_uuids=%s",
            service_info.address,
            service_info.name,
            getattr(service_info, "source", None),
            getattr(service_info, "rssi", None),
            getattr(service_info, "connectable", None),
            service_info.service_uuids,
        )
        if service_info.name:
            self.name = service_info.name

    async def async_connect(self) -> None:
        """Connect and subscribe to notifications."""
        if self._client and self._client.is_connected:
            _LOGGER.debug("Sleepytroll already connected address=%s", self.address)
            return

        _LOGGER.debug(
            "Resolving connectable Sleepytroll BLEDevice address=%s", self.address
        )
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            any_ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=False
            )
            connectable_service_info = bluetooth.async_last_service_info(
                self.hass, self.address, connectable=True
            )
            any_service_info = bluetooth.async_last_service_info(
                self.hass, self.address, connectable=False
            )
            _LOGGER.debug(
                "No connectable Bluetooth adapter/proxy for Sleepytroll address=%s; "
                "any_ble_device=%s connectable_service_info=%s "
                "any_service_info=%s connectable_scanners=%s all_scanners=%s",
                self.address,
                any_ble_device,
                _service_info_for_log(connectable_service_info),
                _service_info_for_log(any_service_info),
                bluetooth.async_scanner_count(self.hass, connectable=True),
                bluetooth.async_scanner_count(self.hass, connectable=False),
            )
            raise ConfigEntryNotReady(
                f"No connectable Bluetooth adapter or proxy can reach {self.address}"
            )

        try:
            _LOGGER.debug(
                "Connecting to Sleepytroll address=%s name=%s ble_device=%s",
                self.address,
                self.name,
                ble_device,
            )
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.name,
                ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                ),
            )
            _LOGGER.debug(
                "Sleepytroll connected address=%s; starting notifications uuid=%s",
                self.address,
                NOTIFY_UUID,
            )
            self._identity_sync_sent = False
            await self._client.start_notify(NOTIFY_UUID, self._notification_handler)
            _LOGGER.debug("Sleepytroll notifications active address=%s", self.address)
        except BleakError as err:
            _LOGGER.debug(
                "Sleepytroll Bluetooth connection failed address=%s name=%s",
                self.address,
                self.name,
                exc_info=True,
            )
            raise ConfigEntryNotReady(
                f"Bluetooth connection failed for {self.name}"
            ) from err

    async def async_disconnect(self) -> None:
        """Disconnect client."""
        task = self._identity_sync_task
        if (
            task is not None
            and not task.done()
            and task is not asyncio.current_task()
        ):
            task.cancel()
        self._identity_sync_task = None
        self._identity_sync_sent = False

        client = self._client
        self._client = None
        if client and client.is_connected:
            _LOGGER.debug("Disconnecting Sleepytroll address=%s", self.address)
            try:
                await client.stop_notify(NOTIFY_UUID)
                _LOGGER.debug(
                    "Sleepytroll notifications stopped address=%s", self.address
                )
            except BleakError:
                _LOGGER.debug("Sleepytroll stop_notify failed", exc_info=True)
            await client.disconnect()
            _LOGGER.debug("Sleepytroll disconnected address=%s", self.address)
        else:
            _LOGGER.debug(
                "Sleepytroll disconnect skipped; not connected address=%s",
                self.address,
            )

    async def async_write(self, command: str | bytes) -> None:
        """Write a command."""
        async with self._lock:
            await self.async_connect()
            assert self._client is not None
            payload = command.encode() if isinstance(command, str) else command
            _LOGGER.debug(
                "Writing Sleepytroll command address=%s uuid=%s %s",
                self.address,
                WRITE_UUID,
                _payload_for_log(payload),
            )
            try:
                await self._client.write_gatt_char(WRITE_UUID, payload, response=True)
                _LOGGER.debug(
                    "Sleepytroll command write complete address=%s", self.address
                )
            except BleakError as err:
                _LOGGER.debug(
                    "Sleepytroll command write failed address=%s %s",
                    self.address,
                    _payload_for_log(payload),
                    exc_info=True,
                )
                await self.async_disconnect()
                raise HomeAssistantError(
                    f"Failed to send command to {self.name}"
                ) from err

    async def async_refresh(self) -> SleepytrollState:
        """Ensure connection and return current state placeholder."""
        _LOGGER.debug("Refreshing Sleepytroll connection address=%s", self.address)
        await self.async_connect()
        return SleepytrollState()

    def _notification_handler(self, sender: object, data: bytearray) -> None:
        """Handle BLE notification."""
        if self._state_callback is None:
            _LOGGER.debug(
                "Ignoring Sleepytroll notification without callback address=%s",
                self.address,
            )
            return
        raw_data = bytes(data)
        _LOGGER.debug(
            "Sleepytroll notification address=%s sender=%s %s",
            self.address,
            sender,
            _payload_for_log(raw_data),
        )
        try:
            packets = parse_notification(raw_data)
        except ValueError:
            _LOGGER.debug(
                "Ignoring unparsable Sleepytroll notification address=%s data=%r",
                self.address,
                raw_data,
                exc_info=True,
            )
            return
        if not packets:
            _LOGGER.debug(
                "Sleepytroll notification produced no packets address=%s data=%r",
                self.address,
                raw_data,
            )
            return
        _LOGGER.debug(
            "Sleepytroll parsed packets address=%s packets=%r",
            self.address,
            packets,
        )
        if any(isinstance(packet, FirstPacket) for packet in packets):
            self._schedule_identity_sync()
        state = state_from_packets(packets)
        _LOGGER.debug(
            "Sleepytroll parsed state address=%s state=%r", self.address, state
        )
        self._state_callback(state)

    @callback
    def _schedule_identity_sync(self) -> None:
        """Schedule the post-identity state sync command used by the app."""
        if self._identity_sync_sent:
            _LOGGER.debug(
                "Sleepytroll identity sync already sent address=%s", self.address
            )
            return

        self._identity_sync_sent = True
        _LOGGER.debug(
            "Scheduling Sleepytroll identity sync address=%s delay=1.0s",
            self.address,
        )
        task = self.hass.async_create_task(self._async_sync_after_identity())
        self._identity_sync_task = task
        task.add_done_callback(self._identity_sync_done)

    @callback
    def _identity_sync_done(self, task: asyncio.Task[None]) -> None:
        """Handle identity sync completion."""
        if self._identity_sync_task is task:
            self._identity_sync_task = None
        if task.cancelled():
            _LOGGER.debug(
                "Sleepytroll identity sync cancelled address=%s", self.address
            )
            return
        if err := task.exception():
            self._identity_sync_sent = False
            _LOGGER.debug(
                "Sleepytroll identity sync failed address=%s",
                self.address,
                exc_info=err,
            )

    async def _async_sync_after_identity(self) -> None:
        """Send AT+OK after identity packet so the device emits full state."""
        await asyncio.sleep(1.0)
        command = command_acknowledge()
        _LOGGER.debug(
            "Sending Sleepytroll identity sync address=%s command=%r",
            self.address,
            command,
        )
        await self.async_write(command)
