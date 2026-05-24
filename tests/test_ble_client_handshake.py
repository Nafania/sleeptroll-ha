from pathlib import Path

BLE_CLIENT_PATH = (
    Path(__file__).parents[1] / "custom_components" / "sleepytroll" / "ble_client.py"
)


def test_identity_packet_schedules_state_sync_acknowledgement() -> None:
    source = BLE_CLIENT_PATH.read_text()

    assert "FirstPacket" in source
    assert "command_acknowledge" in source
    assert "isinstance(packet, FirstPacket)" in source
    assert "async_create_task(self._async_sync_after_identity())" in source
    assert "await asyncio.sleep(1.0)" in source
