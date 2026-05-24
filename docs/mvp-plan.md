# Sleepytroll Home Assistant MVP Plan

> Required execution style: use subagents for independent implementation/review slices. Keep reverse-engineering artifacts out of HACS package. Track progress by updating checkboxes in this file.

**Goal:** Build a HACS-compatible Home Assistant custom integration for Sleepytroll Baby Rocker Gen 2 with UI config flow, Bluetooth discovery, Bluetooth proxy support, and all non-OTA app controls.

**Architecture:** A pure `protocol.py` owns command formatting and notification parsing. A BLE client layer resolves devices through Home Assistant Bluetooth APIs and connects with the Home Assistant Bluetooth stack's `bleak-retry-connector` so ESPHome Bluetooth proxies and other HA Bluetooth adapters work. Entity platforms expose the app controls as HA switch/select/number/button/sensor entities backed by one coordinator/client.

**Tech stack:** Home Assistant custom integration, HA Bluetooth API, Home Assistant-provided `bleak-retry-connector`, Python 3.13+-compatible code, pytest for protocol tests, HACS repository layout.

---

## Scope

In scope:
- HACS installable repository layout.
- Config flow UI with auto Bluetooth discovery and manual device selection.
- BLE proxy support through Home Assistant Bluetooth APIs.
- Non-OTA commands from Android app:
  - start/pause rocking
  - continuous mode
  - sensor mode
  - baby monitor mode
  - sleep program short/medium/long
  - runtime duration
  - rocking intensity
  - sound sensor sensitivity
  - movement sensor sensitivity
  - light sensitivity
  - acknowledge command
  - reset command as disabled diagnostic button
- Sensors parsed from notifications when available:
  - battery level
  - rocking status
  - rocking intensity
  - sound sensitivity
  - movement sensitivity
  - remaining time
  - rocker type
  - sleep program stage
  - microphone status
  - battery cycle count
  - device total time
  - motor time
  - firmware version
  - serial number
  - light value

Out of scope:
- OTA firmware update.
- Cloud/app account features.
- Device ownership/profile data from Android app database.
- Long-running hardware endurance tests before first code release.

## Protocol Facts

GATT:
- Service UUID: `55535343-FE7D-4AE5-8FA9-9FAFD205E455`
- Write characteristic: `49535343-8841-43F4-A8D4-ECBE34729BB3`
- Notify/read characteristic: `49535343-1E4D-4BD9-BA61-23C647249616`
- Notifications are UTF-8 text records split by `\r\n`, with packet prefixes `1,`, `2,`, `3,`, `4,`, `5,`.

Commands:
- `AT+MODE=01;` continuous
- `AT+MODE=02;` sensor
- `AT+MODE=03;` baby monitor
- `AT+SP=S;` sleep program short
- `AT+SP=M;` sleep program medium
- `AT+SP=L;` sleep program long
- `AT+ST=%02x;` runtime minutes, app bounds 10..480
- `AT+FR=%02x;` rocking intensity, app UI bounds 20..100
- `AT+SH=%02x;` sound sensor sensitivity, app clamps incoming value to 0..4
- `AT+AU=%02x;` movement sensor sensitivity, app clamps incoming value to 0..4
- `AT+BR=%02x;` light sensitivity, app UI bounds 0..100 step 10
- `AT+BH=01;` start/resume
- `AT+BH=00;` pause
- `AT+OK` acknowledge
- `AT+RESET` reset

## Files

Create:
- `.gitignore` to exclude reverse-engineering artifacts, virtualenvs, caches.
- `README.md` with HACS install and HA setup notes.
- `hacs.json` for HACS metadata.
- `pyproject.toml` for local test/lint tooling.
- `.github/workflows/validate.yml` for HACS and hassfest validation.
- `custom_components/sleepytroll/manifest.json`
- `custom_components/sleepytroll/strings.json`
- `custom_components/sleepytroll/__init__.py`
- `custom_components/sleepytroll/const.py`
- `custom_components/sleepytroll/protocol.py`
- `custom_components/sleepytroll/ble_client.py`
- `custom_components/sleepytroll/coordinator.py`
- `custom_components/sleepytroll/entity.py`
- `custom_components/sleepytroll/config_flow.py`
- `custom_components/sleepytroll/switch.py`
- `custom_components/sleepytroll/select.py`
- `custom_components/sleepytroll/number.py`
- `custom_components/sleepytroll/button.py`
- `custom_components/sleepytroll/sensor.py`
- `tests/test_protocol.py`

No writes:
- `apks/`
- `decompiled/`

## Tasks

### Task 1: Repository and HACS Scaffold

- [x] Initialize local git repo on `main`.
- [x] Add `.gitignore`, `README.md`, `hacs.json`, `pyproject.toml`, validation workflow.
- [x] Add integration manifest and translation strings.
- [x] Verify HACS package content excludes `apks/` and `decompiled/`.

### Task 2: Protocol Module, TDD First

- [x] Write failing pytest tests in `tests/test_protocol.py` for all command builders.
- [x] Run `python3 -m pytest tests/test_protocol.py -q` and confirm command tests fail.
- [x] Implement `protocol.py` command builders with bounds validation.
- [x] Run protocol tests and confirm command tests pass.
- [x] Write failing pytest tests for packet parsing:
  - second packet: battery/status/intensity/sensitivity/time
  - third packet: rocker type/stage/mic/cycles/total/motor time
  - first packet: serial/version
  - fifth packet: light value
- [x] Implement packet parser.
- [x] Run protocol tests and confirm parser tests pass.

### Task 3: BLE Client

- [x] Implement `SleepytrollBleClient` around HA Bluetooth device resolution and `bleak-retry-connector`.
- [x] Use `bluetooth.async_ble_device_from_address(hass, address, connectable=True)` before every connection attempt.
- [x] Use notify callback on read characteristic and feed parsed state to coordinator.
- [x] Serialize writes with an `asyncio.Lock`.
- [x] Disconnect cleanly on unload.
- [x] Surface Bluetooth/proxy slot/connect failures as HA update errors, not crashes.

### Task 4: Config Flow

- [x] Implement `async_step_bluetooth` using `BluetoothServiceInfoBleak`.
- [x] Match Sleepytroll advertising UUID `00001315-0000-1000-8000-00805f9b34fb` discovered from Android scan filter.
- [x] Use unique ID from normalized Bluetooth address.
- [x] Implement user step listing discovered Sleepytroll devices from `async_discovered_service_info`.
- [x] Add manual address fallback when no discovery is visible.
- [x] Add config flow translations and field descriptions for HACS/custom integration UI.
- [x] Abort duplicate entries.
- [x] Store address and name in config entry data.

### Task 5: Coordinator and Entities

- [x] Implement coordinator with latest parsed state.
- [x] Register Bluetooth callback by address to refresh BLEDevice/advertisement source.
- [x] Forward platforms: switch, select, number, button, sensor.
- [x] Implement shared base entity with device info and availability.
- [x] Implement switch/select/number/button entities mapped to protocol commands.
- [x] Implement sensors from parsed state with diagnostic categories where appropriate.
- [x] Disable reset button by default and mark it diagnostic.

### Task 6: Local Verification

- [x] Run protocol tests.
- [x] Run Python compile check for custom component.
- [x] Run Home Assistant 2025.6 import smoke test for integration modules.
- [x] Add debug logs for discovery, BLE proxy resolution, commands, notifications, and state merge.
- [x] Avoid custom `bleak-retry-connector` manifest pin; use Home Assistant Bluetooth stack version.
- [x] Run `hacs/action` and `hassfest` via GitHub Actions after push.
- [ ] Install via HACS custom repository in Home Assistant.
- [ ] Add integration through UI config flow.
- [ ] Test connection through local Bluetooth adapter.
- [ ] Test connection through BLE proxy/repeater.
- [ ] Test commands on real device:
  - start/pause
  - mode select
  - sleep programs
  - duration
  - rocking intensity
  - sound/movement/light sensitivity
  - acknowledge
- [ ] Confirm sensors update from notifications.
- [ ] Do not test reset until user explicitly confirms.

### Task 7: Release Prep

- [x] Update README with HACS target HA version, Bluetooth proxy note, and no-OTA statement.
- [x] Commit implementation.
- [x] Push `main` to `Nafania/sleeptroll-ha`.
- [ ] Tag initial release after HA device test passes.

## Subagent Plan

- Protocol worker: owns `custom_components/sleepytroll/protocol.py` and `tests/test_protocol.py`.
- HA integration worker: owns `custom_components/sleepytroll/__init__.py`, `custom_components/sleepytroll/config_flow.py`, `custom_components/sleepytroll/coordinator.py`, `custom_components/sleepytroll/ble_client.py`, `custom_components/sleepytroll/entity.py`.
- Entity worker: owns platform files `custom_components/sleepytroll/switch.py`, `custom_components/sleepytroll/select.py`, `custom_components/sleepytroll/number.py`, `custom_components/sleepytroll/button.py`, `custom_components/sleepytroll/sensor.py`.
- Review worker: checks HACS layout, config flow, BLE proxy assumptions, no OTA exposure.

Workers must not edit `apks/` or `decompiled/`, and must not revert parallel edits.
