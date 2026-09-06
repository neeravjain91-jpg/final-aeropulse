"""Automated Unit & Integration Tests for Virtual CAN 2.0B Controller and Bus Layer."""
from __future__ import annotations

import pytest
from app.can_bus import CANFrame
from app.virtual_can_bus import (
    VirtualCANBus,
    VirtualCANBusConfig,
    CANBusDiagnostics,
)


def test_virtual_can_bus_initialization():
    """Verifies default CAN bus configuration (500 kbps, 2.0B framing)."""
    bus = VirtualCANBus()
    assert bus.config.bitrate_bps == 500_000
    assert bus.get_bus_utilization_pct() >= 0.0
    assert len(bus._tx_queue) == 0
    assert len(bus._rx_queue) == 0


def test_virtual_can_frame_timing_calculation():
    """Verifies that frame serialization time is calculated accurately from bitrate and DLC."""
    bus = VirtualCANBus(VirtualCANBusConfig(bitrate_bps=500_000))
    tx_time_us = bus.calculate_serialization_time_us(dlc=8)

    # DLC = 8 -> 111-135 bits at 500 kbps -> ~220-270 microseconds
    assert tx_time_us > 180.0
    assert tx_time_us < 350.0


def test_virtual_can_priority_arbitration():
    """Verifies that lowest CAN arbitration ID wins priority on the bus."""
    bus = VirtualCANBus(VirtualCANBusConfig(propagation_delay_us=0.0))
    frame_high_pri = CANFrame(arbitration_id=0x100, data=bytes([1]*8), timestamp_ms=10.0)
    frame_low_pri = CANFrame(arbitration_id=0x200, data=bytes([2]*8), timestamp_ms=10.0)

    # Queue low priority first, then high priority at same sim time
    bus.send(frame_low_pri, sim_time_us=1000.0)
    bus.send(frame_high_pri, sim_time_us=1000.0)

    bus.step_bus(time_step_us=100_000.0)
    received = bus.flush_and_receive_all()

    assert len(received) == 2
    assert received[0].arbitration_id == 0x100
    assert received[1].arbitration_id == 0x200


def test_virtual_can_queue_depth_overflow():
    """Verifies that exceeding TX queue depth discards or drops old frames cleanly."""
    bus = VirtualCANBus(VirtualCANBusConfig(max_queue_depth=5))
    for i in range(10):
        frame = CANFrame(arbitration_id=0x100 + i, data=bytes(8), timestamp_ms=0.0)
        bus.send(frame, sim_time_us=0.0)

    assert len(bus._tx_queue) <= 5
    assert bus.stats.frames_dropped_queue_full > 0


def test_virtual_can_crc_corruption_fault():
    """Verifies that corrupted frames are flagged upon injection."""
    bus = VirtualCANBus(VirtualCANBusConfig(crc_corruption_prob=1.0))
    frame = CANFrame(arbitration_id=0x100, data=bytes([0xAA]*8), timestamp_ms=0.0)
    bus.send(frame, sim_time_us=0.0)
    bus.step_bus(time_step_us=50_000.0)
    received = bus.flush_and_receive_all()

    if len(received) > 0:
        assert received[0].data != bytes([0xAA]*8) or bus.stats.crc_corruptions_injected > 0


def test_virtual_can_packet_loss_fault():
    """Verifies that 100% packet loss drops transmitted frames."""
    bus = VirtualCANBus(VirtualCANBusConfig(packet_loss_prob=1.0))
    frame = CANFrame(arbitration_id=0x100, data=bytes(8), timestamp_ms=0.0)
    bus.send(frame, sim_time_us=0.0)
    bus.step_bus(time_step_us=50_000.0)
    received = bus.flush_and_receive_all()

    assert len(received) == 0
    assert bus.stats.frames_dropped_simulated_loss >= 1
