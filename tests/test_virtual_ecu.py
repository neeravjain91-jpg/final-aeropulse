"""Automated Unit & Integration Tests for Virtual Engine Control Unit (ECU)."""
from __future__ import annotations

import struct
import pytest

from app.can_bus import CANFrame, SimulatedCANAdapter
from app.engine_model import EngineInputs, ReducedOrderPistonEngine
from app.virtual_ecu import VirtualECU


def test_virtual_ecu_initialization():
    """Verifies that Virtual ECU initializes with correct identifiers and CAN adapter."""
    adapter = SimulatedCANAdapter()
    ecu = VirtualECU(ecu_id="ECU-TEST-01", can_adapter=adapter)

    assert ecu.ecu_id == "ECU-TEST-01"
    assert ecu.can_adapter.connected is True
    assert ecu.stats.frames_transmitted == 0
    assert ecu.stats.packets_encoded == 0


def test_virtual_ecu_encodes_standard_can_frames():
    """Verifies that Virtual ECU encodes telemetry into 5 standard 8-byte CAN frames."""
    engine = ReducedOrderPistonEngine()
    telemetry = engine.simulate(rpm=3000.0, throttle=0.60, altitude_ft=5000.0, ambient_c=25.0)

    adapter = SimulatedCANAdapter()
    ecu = VirtualECU(can_adapter=adapter)

    frames = ecu.encode_and_transmit(telemetry, timestamp_ms=1000.0)

    assert len(frames) == 5
    can_ids = [f.arbitration_id for f in frames]
    assert can_ids == [0x100, 0x101, 0x102, 0x103, 0x104]

    for f in frames:
        assert len(f.data) == 8
        assert f.timestamp_ms == 1000.0

    assert ecu.stats.frames_transmitted == 5
    assert ecu.stats.packets_encoded == 1
    assert ecu.stats.sequence_number == 1


def test_virtual_ecu_crc8_integrity_calculation():
    """Verifies that frame 0x100 and 0x104 contain mathematically valid CRC-8 checksums."""
    engine = ReducedOrderPistonEngine()
    telemetry = engine.simulate(rpm=3000.0, throttle=0.60)

    ecu = VirtualECU()
    frames = ecu.encode_and_transmit(telemetry, timestamp_ms=500.0)

    frame100 = next(f for f in frames if f.arbitration_id == 0x100)
    payload100 = frame100.data[:7]
    expected_crc100 = ecu._crc8(payload100)
    actual_crc100 = frame100.data[7]
    assert actual_crc100 == expected_crc100

    frame104 = next(f for f in frames if f.arbitration_id == 0x104)
    payload104 = frame104.data[:7]
    expected_crc104 = ecu._crc8(payload104)
    actual_crc104 = frame104.data[7]
    assert actual_crc104 == expected_crc104


def test_virtual_ecu_sequence_monotonicity():
    """Verifies that transmission sequence counter increments monotonically modulo 256."""
    engine = ReducedOrderPistonEngine()
    telemetry = engine.simulate()

    ecu = VirtualECU()
    for seq in range(1, 10):
        frames = ecu.encode_and_transmit(telemetry, timestamp_ms=float(seq * 50))
        frame104 = next(f for f in frames if f.arbitration_id == 0x104)
        assert frame104.data[0] == seq % 256
        assert ecu.stats.sequence_number == seq % 256
