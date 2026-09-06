import pytest
from app.can_bus import CANBusInterface, SimulatedCANAdapter, CANFrame
from app.exceptions import CANBusError

def test_simulated_can_disconnect():
    adapter = SimulatedCANAdapter()
    adapter.connected = False
    with pytest.raises(CANBusError, match="CAN bus disconnected"):
        adapter.send(CANFrame(0x100, b"\x00"*8))

def test_can_sequence_counter_rollover():
    can = CANBusInterface()
    for i in range(25):
        frames = can.encode_telemetry({"Engine_RPM": 4500.0})
        assert len(frames) == 4
