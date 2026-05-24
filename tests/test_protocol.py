import importlib.util
import sys
from pathlib import Path

import pytest

PROTOCOL_PATH = (
    Path(__file__).parents[1] / "custom_components" / "sleepytroll" / "protocol.py"
)
spec = importlib.util.spec_from_file_location("sleepytroll_protocol", PROTOCOL_PATH)
assert spec is not None
protocol = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)

BabyRockerMode = protocol.BabyRockerMode
FifthPacket = protocol.FifthPacket
FirstPacket = protocol.FirstPacket
FourthPacket = protocol.FourthPacket
SecondPacket = protocol.SecondPacket
SleepProgram = protocol.SleepProgram
SleepytrollState = protocol.SleepytrollState
ThirdPacket = protocol.ThirdPacket
build_acknowledge_command = protocol.build_acknowledge_command
build_light_sensitivity_command = protocol.build_light_sensitivity_command
build_mode_command = protocol.build_mode_command
build_movement_sensor_sensitivity_command = (
    protocol.build_movement_sensor_sensitivity_command
)
build_pause_command = protocol.build_pause_command
build_reset_command = protocol.build_reset_command
build_rocking_intensity_command = protocol.build_rocking_intensity_command
build_runtime_command = protocol.build_runtime_command
build_sleep_program_command = protocol.build_sleep_program_command
build_sound_sensor_sensitivity_command = protocol.build_sound_sensor_sensitivity_command
build_start_command = protocol.build_start_command
command_acknowledge = protocol.command_acknowledge
command_duration = protocol.command_duration
command_light_sensitivity = protocol.command_light_sensitivity
command_mode = protocol.command_mode
command_movement_sensitivity = protocol.command_movement_sensitivity
command_play = protocol.command_play
command_reset = protocol.command_reset
command_rocking_intensity = protocol.command_rocking_intensity
command_sleep_program = protocol.command_sleep_program
command_sound_sensitivity = protocol.command_sound_sensitivity
parse_notification = protocol.parse_notification
state_from_packets = protocol.state_from_packets


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (BabyRockerMode.CONTINUOUS, b"AT+MODE=01;"),
        (BabyRockerMode.SENSOR, b"AT+MODE=02;"),
        (BabyRockerMode.BABY_MONITOR, b"AT+MODE=03;"),
    ],
)
def test_build_mode_commands(mode: BabyRockerMode, expected: bytes) -> None:
    assert build_mode_command(mode) == expected


@pytest.mark.parametrize(
    ("program", "expected"),
    [
        (SleepProgram.SHORT, b"AT+SP=S;"),
        (SleepProgram.MEDIUM, b"AT+SP=M;"),
        (SleepProgram.LONG, b"AT+SP=L;"),
    ],
)
def test_build_sleep_program_commands(program: SleepProgram, expected: bytes) -> None:
    assert build_sleep_program_command(program) == expected


@pytest.mark.parametrize(
    ("builder", "value", "expected"),
    [
        (build_runtime_command, 10, b"AT+ST=0a;"),
        (build_runtime_command, 480, b"AT+ST=1e0;"),
        (build_rocking_intensity_command, 20, b"AT+FR=14;"),
        (build_rocking_intensity_command, 100, b"AT+FR=64;"),
        (build_sound_sensor_sensitivity_command, 4, b"AT+SH=04;"),
        (build_movement_sensor_sensitivity_command, 3, b"AT+AU=03;"),
        (build_light_sensitivity_command, 0, b"AT+BR=00;"),
        (build_light_sensitivity_command, 100, b"AT+BR=64;"),
    ],
)
def test_build_value_commands(builder, value: int, expected: bytes) -> None:
    assert builder(value) == expected


@pytest.mark.parametrize(
    ("builder", "value"),
    [
        (build_runtime_command, 9),
        (build_runtime_command, 481),
        (build_rocking_intensity_command, 19),
        (build_rocking_intensity_command, 101),
        (build_sound_sensor_sensitivity_command, -1),
        (build_sound_sensor_sensitivity_command, 5),
        (build_movement_sensor_sensitivity_command, -1),
        (build_movement_sensor_sensitivity_command, 5),
        (build_light_sensitivity_command, -10),
        (build_light_sensitivity_command, 110),
        (build_light_sensitivity_command, 15),
    ],
)
def test_value_command_bounds_are_validated(builder, value: int) -> None:
    with pytest.raises(ValueError):
        builder(value)


def test_build_start_pause_acknowledge_and_reset_commands() -> None:
    assert build_start_command() == b"AT+BH=01;"
    assert build_pause_command() == b"AT+BH=00;"
    assert build_acknowledge_command() == b"AT+OK"
    assert build_reset_command() == b"AT+RESET"


def test_entity_command_aliases_accept_home_assistant_values() -> None:
    assert command_mode("continuous") == b"AT+MODE=01;"
    assert command_mode("sensor") == b"AT+MODE=02;"
    assert command_mode("baby_monitor") == b"AT+MODE=03;"
    assert command_sleep_program("short") == b"AT+SP=S;"
    assert command_sleep_program("medium") == b"AT+SP=M;"
    assert command_sleep_program("long") == b"AT+SP=L;"
    assert command_duration(10) == b"AT+ST=0a;"
    assert command_rocking_intensity(80) == b"AT+FR=50;"
    assert command_sound_sensitivity(4) == b"AT+SH=04;"
    assert command_movement_sensitivity(3) == b"AT+AU=03;"
    assert command_light_sensitivity(50) == b"AT+BR=32;"
    assert command_play(True) == b"AT+BH=01;"
    assert command_play(False) == b"AT+BH=00;"
    assert command_acknowledge() == b"AT+OK"
    assert command_reset() == b"AT+RESET"


def test_parse_notification_splits_text_records_and_packet_boundaries() -> None:
    packets = parse_notification(
        b"noise2,6403500905010203ff\r\n"
        b"1,123456789,abcd1.6.7"
        b"5,32"
    )

    assert packets == [
        SecondPacket(
            battery_level=100,
            rocking_status=3,
            rocking_intensity=80,
            sound_sensitivity=4,
            movement_sensitivity=4,
            remaining_time_raw="010203",
            remaining_time_seconds=3723,
            crc_valid=None,
        ),
        FirstPacket(
            serial_number="123456789-abcd",
            firmware_version="1.6.7",
            code="123456789",
            verification_code="abcd",
            crc_valid=None,
        ),
        FifthPacket(cmd_response="32", light_value=50, crc_valid=None),
    ]


def test_parse_second_packet_clamps_sensor_sensitivity_and_time() -> None:
    assert parse_notification("2,3203500905010203ff") == [
        SecondPacket(
            battery_level=50,
            rocking_status=3,
            rocking_intensity=80,
            sound_sensitivity=4,
            movement_sensitivity=4,
            remaining_time_raw="010203",
            remaining_time_seconds=3723,
            crc_valid=None,
        )
    ]


def test_parse_third_packet_includes_type_stage_cycles_totals_and_motor_time() -> None:
    assert parse_notification("3,02010a0064002d") == [
        ThirdPacket(
            rocker_type=2,
            sleep_program_stage="01",
            microphone_status=10,
            battery_cycle_count=100,
            device_total_time=45,
            motor_time_minutes=0,
            crc_valid=None,
        )
    ]


def test_parse_first_packet_includes_serial_and_firmware_version() -> None:
    assert parse_notification("1,123456789,abcd1.6.7") == [
        FirstPacket(
            serial_number="123456789-abcd",
            firmware_version="1.6.7",
            code="123456789",
            verification_code="abcd",
            crc_valid=None,
        )
    ]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("4,OK", FourthPacket(cmd_response="OK")),
        (
            "4,020001",
            FourthPacket(cmd_response="020001", pop_value=2, motor_status="01"),
        ),
        ("4,0000", FourthPacket(cmd_response="0000", device_will_disconnect=True)),
    ],
)
def test_parse_fourth_packet_command_status(
    payload: str, expected: FourthPacket
) -> None:
    assert parse_notification(payload) == [expected]


def test_parse_fifth_packet_includes_light_value() -> None:
    assert parse_notification("5,64") == [
        FifthPacket(cmd_response="64", light_value=100, crc_valid=None)
    ]


def test_state_from_packets_merges_known_fields() -> None:
    packets = parse_notification(
        "1,123456789,abcd1.6.7\r\n"
        "2,6403500905010203ff"
        "3,02010a0064002d"
        "5,64"
    )

    state = state_from_packets(packets)

    assert state == SleepytrollState(
        serial_number="123456789-abcd",
        firmware_version="1.6.7",
        battery_level=100,
        rocking_status=3,
        rocking_intensity=80,
        sound_sensitivity=4,
        movement_sensitivity=4,
        remaining_time_raw="010203",
        remaining_time_seconds=3723,
        rocker_type=2,
        sleep_program_stage="01",
        microphone_status=10,
        battery_cycle_count=100,
        device_total_time=45,
        motor_time_minutes=0,
        light_value=100,
    )


def test_state_merge_keeps_existing_values_when_update_is_partial() -> None:
    base = SleepytrollState(battery_level=70, rocking_intensity=40)
    update = SleepytrollState(rocking_intensity=80, light_value=50)

    assert base.merge(update) == SleepytrollState(
        battery_level=70,
        rocking_intensity=80,
        light_value=50,
    )
