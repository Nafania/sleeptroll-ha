# Sleepytroll for Home Assistant

Custom Home Assistant integration for Sleepytroll Baby Rocker Gen 2 over
Bluetooth.

## Status

MVP implementation is ready for real-device testing. OTA firmware updates are
intentionally out of scope. HACS metadata currently targets Home Assistant
`2025.6.0` or newer; real-device validation is still pending.

## Installation

1. Add this repository to HACS as a custom repository.
2. Choose category `Integration`.
3. Install `Sleepytroll`.
4. Restart Home Assistant.
5. Add the integration from Settings -> Devices & services.

## Features

- UI config flow with Bluetooth discovery.
- Manual Bluetooth address fallback.
- Home Assistant Bluetooth proxy/repeater support through HA Bluetooth APIs.
- Controls for start/pause, mode, sleep programs, runtime, rocking intensity,
  sound sensitivity, movement sensitivity, light sensitivity, and acknowledge.
- Diagnostic reset button, disabled by default.
- Sensors for battery, rocking status, remaining time, counters, firmware,
  serial number, and light value when the device sends notifications.

## Bluetooth Notes

The integration resolves devices through Home Assistant Bluetooth, using
connectable adapters/proxies. Do not pair the rocker with the host OS; keep it
available for Home Assistant to connect over BLE.

## Development

```bash
python3 -m pytest tests -q
uvx ruff check .
python3 -m compileall custom_components/sleepytroll
```

Implementation plan: [docs/mvp-plan.md](docs/mvp-plan.md).
