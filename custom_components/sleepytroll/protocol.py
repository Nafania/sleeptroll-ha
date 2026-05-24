"""Sleepytroll BLE protocol helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, fields
from enum import Enum

SERVICE_UUID = "55535343-FE7D-4AE5-8FA9-9FAFD205E455"
WRITE_CHARACTERISTIC_UUID = "49535343-8841-43F4-A8D4-ECBE34729BB3"
NOTIFY_CHARACTERISTIC_UUID = "49535343-1E4D-4BD9-BA61-23C647249616"

_PACKET_PREFIXES = ("1,", "2,", "3,", "4,", "5,")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


class BabyRockerMode(Enum):
    """Non-OTA rocker operating modes."""

    CONTINUOUS = 1
    SENSOR = 2
    BABY_MONITOR = 3


class SleepProgram(Enum):
    """Sleep program lengths."""

    SHORT = "S"
    MEDIUM = "M"
    LONG = "L"


@dataclass(frozen=True)
class FirstPacket:
    """Serial number and firmware packet."""

    serial_number: str
    firmware_version: str
    code: str
    verification_code: str
    crc_valid: bool | None = None


@dataclass(frozen=True)
class SecondPacket:
    """Live status packet."""

    battery_level: int
    rocking_status: int
    rocking_intensity: int
    sound_sensitivity: int
    movement_sensitivity: int
    remaining_time_raw: str
    remaining_time_seconds: int
    crc_valid: bool | None = None


@dataclass(frozen=True)
class ThirdPacket:
    """Device counters and sleep-program stage packet."""

    rocker_type: int
    sleep_program_stage: str
    microphone_status: int
    battery_cycle_count: int
    device_total_time: int
    motor_time_minutes: int
    crc_valid: bool | None = None


@dataclass(frozen=True)
class FourthPacket:
    """Command/status response packet."""

    cmd_response: str
    pop_value: int | None = None
    motor_status: str | None = None
    device_will_disconnect: bool = False
    crc_valid: bool | None = None


@dataclass(frozen=True)
class FifthPacket:
    """Light sensitivity packet."""

    cmd_response: str
    light_value: int
    crc_valid: bool | None = None


type ParsedPacket = (
    FirstPacket | SecondPacket | ThirdPacket | FourthPacket | FifthPacket
)


@dataclass(frozen=True)
class SleepytrollState:
    """Merged Sleepytroll state exposed to Home Assistant entities."""

    serial_number: str | None = None
    firmware_version: str | None = None
    battery_level: int | None = None
    rocking_status: int | None = None
    rocking_intensity: int | None = None
    sound_sensitivity: int | None = None
    movement_sensitivity: int | None = None
    remaining_time_raw: str | None = None
    remaining_time_seconds: int | None = None
    rocker_type: int | None = None
    sleep_program_stage: str | None = None
    microphone_status: int | None = None
    battery_cycle_count: int | None = None
    device_total_time: int | None = None
    motor_time_minutes: int | None = None
    cmd_response: str | None = None
    pop_value: int | None = None
    motor_status: str | None = None
    device_will_disconnect: bool | None = None
    light_value: int | None = None

    def merge(self, update: SleepytrollState) -> SleepytrollState:
        """Return state with non-None values from update applied."""

        return SleepytrollState(
            **{
                field.name: (
                    getattr(update, field.name)
                    if getattr(update, field.name) is not None
                    else getattr(self, field.name)
                )
                for field in fields(self)
            }
        )


def build_mode_command(mode: BabyRockerMode) -> bytes:
    """Build continuous/sensor/baby-monitor mode command."""

    if not isinstance(mode, BabyRockerMode):
        raise ValueError(f"Unsupported rocker mode: {mode!r}")
    return _encode(f"AT+MODE={mode.value:02d};")


def build_sleep_program_command(program: SleepProgram) -> bytes:
    """Build short/medium/long sleep-program command."""

    if not isinstance(program, SleepProgram):
        raise ValueError(f"Unsupported sleep program: {program!r}")
    return _encode(f"AT+SP={program.value};")


def build_runtime_command(minutes: int) -> bytes:
    """Build runtime command. App UI bounds are 10..480 minutes."""

    _validate_range("runtime minutes", minutes, 10, 480)
    return _encode(f"AT+ST={minutes:02x};")


def build_rocking_intensity_command(percent: int) -> bytes:
    """Build rocking intensity command. App UI bounds are 20..100."""

    _validate_range("rocking intensity", percent, 20, 100)
    return _encode(f"AT+FR={percent:02x};")


def build_sound_sensor_sensitivity_command(level: int) -> bytes:
    """Build sound sensor sensitivity command. App bounds are 0..4."""

    _validate_range("sound sensor sensitivity", level, 0, 4)
    return _encode(f"AT+SH={level:02x};")


def build_movement_sensor_sensitivity_command(level: int) -> bytes:
    """Build movement sensor sensitivity command. App bounds are 0..4."""

    _validate_range("movement sensor sensitivity", level, 0, 4)
    return _encode(f"AT+AU={level:02x};")


def build_light_sensitivity_command(percent: int) -> bytes:
    """Build light sensitivity command. App UI bounds are 0..100 step 10."""

    _validate_range("light sensitivity", percent, 0, 100)
    if percent % 10 != 0:
        raise ValueError("light sensitivity must use step 10")
    return _encode(f"AT+BR={percent:02x};")


def build_start_command() -> bytes:
    """Build start/resume rocking command."""

    return b"AT+BH=01;"


def build_pause_command() -> bytes:
    """Build pause rocking command."""

    return b"AT+BH=00;"


def build_acknowledge_command() -> bytes:
    """Build command acknowledgement."""

    return b"AT+OK"


def build_reset_command() -> bytes:
    """Build reset command."""

    return b"AT+RESET"


def command_mode(mode: BabyRockerMode | str) -> bytes:
    """Build a mode command from an enum or Home Assistant option string."""

    if isinstance(mode, str):
        key = mode.lower().replace("-", "_").replace(" ", "_")
        mode = {
            "continuous": BabyRockerMode.CONTINUOUS,
            "sensor": BabyRockerMode.SENSOR,
            "baby_monitor": BabyRockerMode.BABY_MONITOR,
        }.get(key)
    if not isinstance(mode, BabyRockerMode):
        raise ValueError(f"Unsupported rocker mode: {mode!r}")
    return build_mode_command(mode)


def command_sleep_program(program: SleepProgram | str) -> bytes:
    """Build a sleep program command from an enum or HA option string."""

    if isinstance(program, str):
        key = program.lower().replace("-", "_").replace(" ", "_")
        program = {
            "short": SleepProgram.SHORT,
            "sleep_short": SleepProgram.SHORT,
            "s": SleepProgram.SHORT,
            "medium": SleepProgram.MEDIUM,
            "sleep_medium": SleepProgram.MEDIUM,
            "m": SleepProgram.MEDIUM,
            "long": SleepProgram.LONG,
            "sleep_long": SleepProgram.LONG,
            "l": SleepProgram.LONG,
        }.get(key)
    if not isinstance(program, SleepProgram):
        raise ValueError(f"Unsupported sleep program: {program!r}")
    return build_sleep_program_command(program)


def command_duration(minutes: int) -> bytes:
    """Build a runtime duration command."""

    return build_runtime_command(minutes)


def command_rocking_intensity(percent: int) -> bytes:
    """Build a rocking intensity command."""

    return build_rocking_intensity_command(percent)


def command_sound_sensitivity(level: int) -> bytes:
    """Build a sound sensor sensitivity command."""

    return build_sound_sensor_sensitivity_command(level)


def command_movement_sensitivity(level: int) -> bytes:
    """Build a movement sensor sensitivity command."""

    return build_movement_sensor_sensitivity_command(level)


def command_light_sensitivity(percent: int) -> bytes:
    """Build a light sensitivity command."""

    return build_light_sensitivity_command(percent)


def command_play(enabled: bool) -> bytes:
    """Build a start or pause command."""

    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")
    return build_start_command() if enabled else build_pause_command()


def command_acknowledge() -> bytes:
    """Build command acknowledgement."""

    return build_acknowledge_command()


def command_reset() -> bytes:
    """Build reset command."""

    return build_reset_command()


def option_from_rocker_type(rocker_type: int | None) -> str | None:
    """Return the Home Assistant mode option for a device rocker type."""

    # Packet 3 exposes the same run-mode values the Android UI highlights.
    # Baby monitor has a command value, but no distinct observed state value.
    return {
        1: "continuous",
        2: "sensor",
        3: "sleep_short",
        4: "sleep_medium",
        5: "sleep_long",
    }.get(rocker_type)


def parse_notification(
    data: bytes | bytearray | memoryview | str,
) -> list[ParsedPacket]:
    """Parse one BLE notification into packet dataclasses.

    Notifications are UTF-8 text. The app accepts multiple packet records in
    one line, so this scans each non-empty CRLF record for packet prefixes.
    """

    text = _decode_notification(data)
    packets: list[ParsedPacket] = []
    for line in (part.strip() for part in text.splitlines()):
        if not line:
            continue
        for raw_packet in _extract_packets(line):
            packet = parse_packet(raw_packet)
            if packet is not None:
                packets.append(packet)
    return packets


def parse_packet(raw_packet: str) -> ParsedPacket | None:
    """Parse a single text packet record."""

    raw_packet = raw_packet.strip()
    if raw_packet.startswith("1,"):
        return _parse_first_packet(raw_packet)
    if raw_packet.startswith("2,"):
        return _parse_second_packet(raw_packet[2:])
    if raw_packet.startswith("3,"):
        return _parse_third_packet(raw_packet)
    if raw_packet.startswith("4,"):
        return _parse_fourth_packet(raw_packet[2:])
    if raw_packet.startswith("5,"):
        return _parse_fifth_packet(raw_packet)
    return None


def state_from_packets(packets: Iterable[ParsedPacket]) -> SleepytrollState:
    """Build a partial merged state from parsed notification packets."""

    state = SleepytrollState()
    for packet in packets:
        if isinstance(packet, FirstPacket):
            state = state.merge(
                SleepytrollState(
                    serial_number=packet.serial_number,
                    firmware_version=packet.firmware_version,
                )
            )
        elif isinstance(packet, SecondPacket):
            state = state.merge(
                SleepytrollState(
                    battery_level=packet.battery_level,
                    rocking_status=packet.rocking_status,
                    rocking_intensity=packet.rocking_intensity,
                    sound_sensitivity=packet.sound_sensitivity,
                    movement_sensitivity=packet.movement_sensitivity,
                    remaining_time_raw=packet.remaining_time_raw,
                    remaining_time_seconds=packet.remaining_time_seconds,
                )
            )
        elif isinstance(packet, ThirdPacket):
            state = state.merge(
                SleepytrollState(
                    rocker_type=packet.rocker_type,
                    sleep_program_stage=packet.sleep_program_stage,
                    microphone_status=packet.microphone_status,
                    battery_cycle_count=packet.battery_cycle_count,
                    device_total_time=packet.device_total_time,
                    motor_time_minutes=packet.motor_time_minutes,
                )
            )
        elif isinstance(packet, FourthPacket):
            state = state.merge(
                SleepytrollState(
                    cmd_response=packet.cmd_response,
                    pop_value=packet.pop_value,
                    motor_status=packet.motor_status,
                    device_will_disconnect=packet.device_will_disconnect,
                )
            )
        elif isinstance(packet, FifthPacket):
            state = state.merge(SleepytrollState(light_value=packet.light_value))
    return state


def _parse_first_packet(raw_packet: str) -> FirstPacket | None:
    if len(raw_packet) <= 16:
        return None

    firmware_and_crc = raw_packet[16:]
    crc_valid: bool | None = None
    firmware_version = firmware_and_crc

    if len(firmware_and_crc) == 9:
        firmware_version = firmware_and_crc[:5]
        crc_valid = _crc_matches(raw_packet[:21], firmware_and_crc[5:])

    code = raw_packet[2:11]
    verification_code = raw_packet[12:16]
    return FirstPacket(
        serial_number=f"{code}-{verification_code}",
        firmware_version=firmware_version,
        code=code,
        verification_code=verification_code,
        crc_valid=crc_valid,
    )


def _parse_second_packet(body: str) -> SecondPacket | None:
    if len(body) < 18 or not _is_hex(body[:18]):
        return None

    crc_valid: bool | None = None
    if len(body) == 22 and _is_hex(body):
        crc_valid = _crc_matches(body[:18], body[18:])

    remaining_time_raw = body[10:16]
    remaining_time_seconds = (
        _hex_to_int(remaining_time_raw[0:2]) * 3600
        + _hex_to_int(remaining_time_raw[2:4]) * 60
        + _hex_to_int(remaining_time_raw[4:6])
    )
    return SecondPacket(
        battery_level=_hex_to_int(body[0:2]),
        rocking_status=_hex_to_int(body[2:4]),
        rocking_intensity=_hex_to_int(body[4:6]),
        sound_sensitivity=min(_hex_to_int(body[6:8]), 4),
        movement_sensitivity=min(_hex_to_int(body[8:10]), 4),
        remaining_time_raw=remaining_time_raw,
        remaining_time_seconds=remaining_time_seconds,
        crc_valid=crc_valid,
    )


def _parse_third_packet(raw_packet: str) -> ThirdPacket | None:
    if len(raw_packet) < 16 or not _is_hex(raw_packet[2:16]):
        return None

    crc_valid: bool | None = None
    if len(raw_packet) == 20 and _is_hex(raw_packet[2:]):
        # The Android app checks this shape as CRC, then also reads it as
        # motor time. Keep the value visible and expose CRC as best effort.
        crc_valid = _crc_matches(raw_packet[:16], raw_packet[16:20])

    motor_time_minutes = 0
    if len(raw_packet) >= 20 and _is_hex(raw_packet[16:20]):
        motor_time_minutes = _hex_to_int(raw_packet[16:18]) * 60 + _hex_to_int(
            raw_packet[18:20]
        )

    return ThirdPacket(
        rocker_type=_hex_to_int(raw_packet[2:4]),
        sleep_program_stage=raw_packet[4:6],
        microphone_status=_hex_to_int(raw_packet[6:8]),
        battery_cycle_count=_hex_to_int(raw_packet[8:12]),
        device_total_time=_hex_to_int(raw_packet[12:16]),
        motor_time_minutes=motor_time_minutes,
        crc_valid=crc_valid,
    )


def _parse_fourth_packet(body: str) -> FourthPacket:
    crc_valid: bool | None = None
    cmd_response = body
    if len(body) == 10:
        crc_valid = True
        cmd_response = body[:2]
    elif body.startswith("04"):
        cmd_response = body[:2]

    motor_status = body[4:6] if len(body) >= 6 else None
    status_code = cmd_response[:2]
    pop_value = (
        int(status_code) if status_code in {"01", "02", "03", "04", "05"} else None
    )

    return FourthPacket(
        cmd_response=cmd_response,
        pop_value=pop_value,
        motor_status=motor_status,
        device_will_disconnect=body.startswith("0000"),
        crc_valid=crc_valid,
    )


def _parse_fifth_packet(raw_packet: str) -> FifthPacket | None:
    if len(raw_packet) < 4 or not _is_hex(raw_packet[2:4]):
        return None
    cmd_response = raw_packet[2:]
    return FifthPacket(
        cmd_response=cmd_response,
        light_value=_hex_to_int(raw_packet[2:4]),
        crc_valid=None,
    )


def _extract_packets(line: str) -> list[str]:
    starts: list[int] = []
    for prefix in _PACKET_PREFIXES:
        start = line.find(prefix)
        while start != -1:
            starts.append(start)
            start = line.find(prefix, start + 1)

    packets: list[str] = []
    sorted_starts = sorted(set(starts))
    for index, start in enumerate(sorted_starts):
        end = sorted_starts[index + 1] if index + 1 < len(sorted_starts) else len(line)
        packets.append(line[start:end])
    return packets


def _validate_range(name: str, value: int, minimum: int, maximum: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")


def _encode(command: str) -> bytes:
    return command.encode("utf-8")


def _decode_notification(data: bytes | bytearray | memoryview | str) -> str:
    if isinstance(data, str):
        return data
    return bytes(data).decode("utf-8", errors="ignore")


def _hex_to_int(value: str) -> int:
    return int(value, 16)


def _is_hex(value: str) -> bool:
    return bool(value) and len(value) % 2 == 0 and _HEX_RE.match(value) is not None


def _crc_matches(payload: str, expected_crc: str) -> bool | None:
    if not expected_crc or len(expected_crc) != 4:
        return None
    payload_bytes = (
        bytes.fromhex(payload) if _is_hex(payload) else payload.encode("utf-8")
    )
    return f"{_crc16_modbus(payload_bytes):04x}" == expected_crc.lower()


def _crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF
