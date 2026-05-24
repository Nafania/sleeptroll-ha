"""Constants for the Sleepytroll integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "sleepytroll"

SERVICE_UUID = "55535343-fe7d-4ae5-8fa9-9fafd205e455"
ADVERTISEMENT_SERVICE_UUID = "00001315-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"
NOTIFY_UUID = "49535343-1e4d-4bd9-ba61-23c647249616"

DEFAULT_NAME = "Sleepytroll"

CONF_MANUAL_ADDRESS = "manual_address"

PLATFORMS = [
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SENSOR,
]
