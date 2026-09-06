"""Virtual CAN 2.0B Bus and Controller Emulation Subsystem.

Simulates physical CAN bus network physics: bit timing, frame serialization delay,
priority-based arbitration, transmit/receive queues, bus load utilization %,
packet loss, CRC corruption, stale frames, jitter, and queue overflows.
"""
from __future__ import annotations

import heapq
import math
import random
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .can_bus import CANFrame, CANHardwareAdapter


@dataclass
class VirtualCANBusConfig:
    """Configuration for physical network properties of the virtual CAN bus."""
    bitrate_bps: int = 500000  # Standard 500 kbps UAV avionics CAN bus
    max_queue_depth: int = 64
    propagation_delay_us: float = 5.0  # Nominal cable propagation delay
    packet_loss_prob: float = 0.0
    crc_corruption_prob: float = 0.0
    stale_frame_prob: float = 0.0
    out_of_order_prob: float = 0.0
    jitter_us_std: float = 0.0
    rng_seed: Optional[int] = 42


@dataclass
class CANBusDiagnostics:
    """Operational diagnostics and network telemetry for the virtual CAN bus."""
    frames_transmitted: int = 0
    frames_received: int = 0
    frames_dropped_queue_full: int = 0
    frames_dropped_simulated_loss: int = 0
    crc_corruptions_injected: int = 0
    stale_frames_injected: int = 0
    out_of_order_events: int = 0
    estimated_bus_utilization_pct: float = 0.0
    total_bus_busy_time_us: float = 0.0
    current_tx_queue_size: int = 0
    current_rx_queue_size: int = 0
    peak_queue_depth: int = 0
    mean_frame_latency_us: float = 0.0


@dataclass(order=True)
class QueuedCANMessage:
    """Internal prioritized representation of a CAN frame scheduled for transmission."""
    priority: int  # Arbitration ID determines priority (lowest ID wins)
    scheduled_tx_time_us: float
    frame: CANFrame = field(compare=False)
    source_node: str = field(compare=False, default="ECU")


class VirtualCANBus(CANHardwareAdapter):
    """
    Deterministic Virtual CAN Bus network connecting Virtual ECU, FADEC, and Flight Computer.
    """

    def __init__(self, config: Optional[VirtualCANBusConfig] = None):
        self.config = config or VirtualCANBusConfig()
        self._rng = random.Random(self.config.rng_seed)
        self.connected = True

        # Priority queues for arbitration
        self._tx_queue: List[QueuedCANMessage] = []
        self._rx_queue: List[CANFrame] = []

        self.sim_time_us: float = 0.0
        self.stats = CANBusDiagnostics()
        self._latencies_us: List[float] = []

    def connect(self) -> bool:
        self.connected = True
        return True

    def calculate_frame_bits(self, dlc: int) -> int:
        """
        Computes standard CAN 2.0B frame bit length including average stuff bits:
        SOF(1) + ID(11) + RTR(1) + IDE(1) + r0(1) + DLC(4) + Data(8*DLC) + CRC(15+1) + ACK(2) + EOF(7) + IFS(3)
        Plus ~15% stuff-bit overhead on static fields and data.
        """
        base_bits = 47 + 8 * dlc
        stuff_bits = int(math.ceil(base_bits * 0.15))
        return base_bits + stuff_bits

    def calculate_serialization_time_us(self, dlc: int) -> float:
        """Calculates theoretical transmission time across the configured bitrate."""
        total_bits = self.calculate_frame_bits(dlc)
        return (float(total_bits) / float(self.config.bitrate_bps)) * 1_000_000.0

    def send(self, frame: CANFrame, sim_time_us: Optional[float] = None) -> bool:
        """Enqueues a frame for prioritized bus arbitration and transmission."""
        if not self.connected:
            return False

        now_us = sim_time_us if sim_time_us is not None else self.sim_time_us
        self.sim_time_us = now_us

        # Check queue capacity
        if len(self._tx_queue) >= self.config.max_queue_depth:
            self.stats.frames_dropped_queue_full += 1
            return False

        # Compute scheduled transmission slot
        ser_time_us = self.calculate_serialization_time_us(frame.dlc)
        prop_delay_us = self.config.propagation_delay_us
        jitter_us = self._rng.gauss(0.0, self.config.jitter_us_std) if self.config.jitter_us_std > 0 else 0.0

        tx_time_us = now_us + ser_time_us + prop_delay_us + max(0.0, jitter_us)

        # Enqueue with priority = arbitration_id
        queued_msg = QueuedCANMessage(
            priority=frame.arbitration_id,
            scheduled_tx_time_us=tx_time_us,
            frame=frame,
        )
        heapq.heappush(self._tx_queue, queued_msg)
        self.stats.frames_transmitted += 1
        self.stats.current_tx_queue_size = len(self._tx_queue)
        self.stats.peak_queue_depth = max(self.stats.peak_queue_depth, len(self._tx_queue))

        return True

    def step_bus(self, time_step_us: float = 1000.0) -> None:
        """
        Advances the virtual CAN bus simulation clock by time_step_us.
        Performs arbitration, transmits ready frames, applies channel faults, and fills RX queue.
        """
        self.sim_time_us += time_step_us
        busy_time_in_step_us = 0.0

        while self._tx_queue and self._tx_queue[0].scheduled_tx_time_us <= self.sim_time_us:
            msg = heapq.heappop(self._tx_queue)
            self.stats.current_tx_queue_size = len(self._tx_queue)

            frame = msg.frame
            frame_ser_time = self.calculate_serialization_time_us(frame.dlc)
            busy_time_in_step_us += frame_ser_time
            self.stats.total_bus_busy_time_us += frame_ser_time

            latency = self.sim_time_us - (frame.timestamp_ms * 1000.0 if frame.timestamp_ms > 0 else self.sim_time_us)
            self._latencies_us.append(max(0.0, latency))

            # 1. Check Simulated Packet Loss
            if self.config.packet_loss_prob > 0.0 and self._rng.random() < self.config.packet_loss_prob:
                self.stats.frames_dropped_simulated_loss += 1
                continue

            # 2. Check CRC Bit Corruption Injection
            data_bytes = bytearray(frame.data)
            if self.config.crc_corruption_prob > 0.0 and self._rng.random() < self.config.crc_corruption_prob:
                # Corrupt last byte (CRC byte) or payload
                if len(data_bytes) > 0:
                    data_bytes[-1] ^= 0xFF
                    self.stats.crc_corruptions_injected += 1

            # 3. Check Stale Frame (simulate delayed old frame)
            if self.config.stale_frame_prob > 0.0 and self._rng.random() < self.config.stale_frame_prob:
                self.stats.stale_frames_injected += 1
                # Old timestamp in past
                delivered_frame = CANFrame(
                    arbitration_id=frame.arbitration_id,
                    data=bytes(data_bytes),
                    dlc=frame.dlc,
                    is_extended=frame.is_extended,
                    timestamp_ms=max(0.0, (self.sim_time_us - 500000.0) / 1000.0),  # 500ms stale
                )
            else:
                delivered_frame = CANFrame(
                    arbitration_id=frame.arbitration_id,
                    data=bytes(data_bytes),
                    dlc=frame.dlc,
                    is_extended=frame.is_extended,
                    timestamp_ms=round(self.sim_time_us / 1000.0, 3),
                )

            # 4. Out-of-Order Delivery check
            if self.config.out_of_order_prob > 0.0 and len(self._rx_queue) > 1 and self._rng.random() < self.config.out_of_order_prob:
                self._rx_queue.insert(0, delivered_frame)
                self.stats.out_of_order_events += 1
            else:
                self._rx_queue.append(delivered_frame)

            self.stats.frames_received += 1

        # Update Bus Load Utilization %
        self.stats.current_rx_queue_size = len(self._rx_queue)
        if self.sim_time_us > 0.0:
            self.stats.estimated_bus_utilization_pct = min(
                100.0, round((self.stats.total_bus_busy_time_us / self.sim_time_us) * 100.0, 2)
            )
        if self._latencies_us:
            self.stats.mean_frame_latency_us = round(sum(self._latencies_us) / len(self._latencies_us), 2)

    def receive(self, timeout_s: float = 0.1) -> Optional[CANFrame]:
        """Dequeues the next arrived CAN frame from the RX buffer."""
        if self._rx_queue:
            frame = self._rx_queue.pop(0)
            self.stats.current_rx_queue_size = len(self._rx_queue)
            return frame
        return None

    def flush_and_receive_all(self) -> List[CANFrame]:
        """Flushes and returns all delivered frames currently in the RX queue."""
        frames = list(self._rx_queue)
        self._rx_queue.clear()
        self.stats.current_rx_queue_size = 0
        return frames

    def get_bus_utilization_pct(self) -> float:
        """Returns the estimated bus utilization percentage."""
        return self.stats.estimated_bus_utilization_pct

    def reset(self) -> None:
        self._tx_queue.clear()
        self._rx_queue.clear()
        self._rng = random.Random(self.config.rng_seed)
        self.sim_time_us = 0.0
        self.stats = CANBusDiagnostics()
        self._latencies_us.clear()
