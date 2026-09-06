"""Virtual Engine Control Unit (ECU) for AeroPulse-X Propulsion Digital Twin.

Simulates the onboard electronic control unit (ECU) data producer.
Responsibilities:
  - Receives authoritative engine physical telemetry from the engine model
  - Encodes telemetry into standard CAN 2.0B / ISO 11898 frames (0x100 - 0x104)
  - Maintains monotonic sequence counters, timestamps, and signal scaling
  - Calculates payload CRC-8 checksums
  - Provides deterministic simulation clock and transmission scheduler
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .can_bus import CANBusInterface, CANFrame, CANHardwareAdapter, SimulatedCANAdapter
from .engine_model import EngineInputs, ReducedOrderPistonEngine


@dataclass
class ECUTxStats:
    """Telemetry transmission statistics tracked by Virtual ECU."""
    frames_transmitted: int = 0
    packets_encoded: int = 0
    sequence_number: int = 0
    last_tx_timestamp_ms: float = 0.0
    active_can_id_count: int = 5


class VirtualECU:
    """
    Virtual Engine Control Unit simulating an airborne sensor ingestion & CAN transmission node.
    Acts as a telemetry interface layer over the authoritative engine physics model.
    """

    ID_ENGINE_DYNAMICS = 0x100
    ID_TEMPERATURES = 0x101
    ID_LUB_COOLANT = 0x102
    ID_ELEC_VIB = 0x103
    ID_ECU_STATUS = 0x104

    def __init__(
        self,
        ecu_id: str = "ECU-MALE-01",
        can_adapter: Optional[CANHardwareAdapter] = None,
        sampling_frequency_hz: float = 20.0,
    ):
        self.ecu_id = ecu_id
        self.can_adapter = can_adapter or SimulatedCANAdapter()
        if not getattr(self.can_adapter, "connected", False):
            self.can_adapter.connect()

        self.sampling_frequency_hz = sampling_frequency_hz
        self.sequence_counter: int = 0
        self.stats = ECUTxStats()
        self._sim_time_ms: float = 0.0

    @staticmethod
    def _crc8(data: bytes) -> int:
        """Calculates standard CRC-8 polynomial (x^8 + x^2 + x + 1 -> 0x07)."""
        crc = 0x00
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x07) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    def encode_and_transmit(
        self,
        telemetry: Dict[str, Any],
        timestamp_ms: Optional[float] = None,
    ) -> List[CANFrame]:
        """
        Encodes authoritative engine telemetry into standard CAN frames and transmits them.
        Returns the list of generated CAN frames for verification and HIL tracking.
        """
        now_ms = timestamp_ms if timestamp_ms is not None else (time.time() * 1000.0)
        self._sim_time_ms = now_ms
        self.sequence_counter = (self.sequence_counter + 1) % 256

        frames: List[CANFrame] = []

        # -------------------------------------------------------------
        # Frame 1: 0x100 — Engine Dynamics
        # Payload (7 bytes data + 1 byte CRC-8):
        # [0-1] RPM (scale: 0.25 RPM/bit, uint16)
        # [2-3] MAP (scale: 0.01 inHg/bit, uint16)
        # [4-5] Fuel Flow (scale: 0.01 L/h/bit, uint16)
        # [6]   Throttle/Load (scale: 0.5 %/bit, uint8)
        # [7]   CRC-8 Checksum
        # -------------------------------------------------------------
        rpm_raw = int(min(65535, max(0, float(telemetry.get("Engine_RPM", 0.0)) / 0.25)))
        map_raw = int(min(65535, max(0, float(telemetry.get("MAP_Injector", 0.0)) / 0.01)))
        ff_raw = int(min(65535, max(0, float(telemetry.get("Fuel_Flow", 0.0)) / 0.01)))
        thr_raw = int(min(255, max(0, float(telemetry.get("Load", telemetry.get("throttle", 0.6))) * 200.0)))
        payload100 = struct.pack("<HHHB", rpm_raw, map_raw, ff_raw, thr_raw)
        crc100 = self._crc8(payload100)
        frame100 = CANFrame(self.ID_ENGINE_DYNAMICS, payload100 + bytes([crc100]), timestamp_ms=now_ms)
        frames.append(frame100)

        # -------------------------------------------------------------
        # Frame 2: 0x101 — Temperatures
        # Payload (8 bytes):
        # [0-1] EGT1 (scale: 0.1 °F/bit, uint16)
        # [2-3] EGT2 (scale: 0.1 °F/bit, uint16)
        # [4-5] EGT3 (scale: 0.1 °F/bit, uint16)
        # [6-7] CHT  (scale: 0.1 °F/bit, uint16)
        # -------------------------------------------------------------
        egt1_raw = int(min(65535, max(0, float(telemetry.get("EGT1", 0.0)) * 10.0)))
        egt2_raw = int(min(65535, max(0, float(telemetry.get("EGT2", 0.0)) * 10.0)))
        egt3_raw = int(min(65535, max(0, float(telemetry.get("EGT3", 0.0)) * 10.0)))
        cht_raw = int(min(65535, max(0, float(telemetry.get("CHT", 0.0)) * 10.0)))
        payload101 = struct.pack("<HHHH", egt1_raw, egt2_raw, egt3_raw, cht_raw)
        frame101 = CANFrame(self.ID_TEMPERATURES, payload101, timestamp_ms=now_ms)
        frames.append(frame101)

        # -------------------------------------------------------------
        # Frame 3: 0x102 — Lubrication & Coolant
        # Payload (8 bytes):
        # [0-1] Oil Temp (scale: 0.1 °F/bit, int16)
        # [2-3] Oil Pressure (scale: 0.1 psi/bit, uint16)
        # [4-5] Water Temp (scale: 0.1 °F/bit, int16)
        # [6-7] Fuel Temp (scale: 0.1 °F/bit, int16)
        # -------------------------------------------------------------
        oil_t_raw = int(max(-32768, min(32767, float(telemetry.get("Oil_Temp", 0.0)) * 10.0)))
        oil_p_raw = int(min(65535, max(0, float(telemetry.get("Oil_Pressure", 0.0)) * 10.0)))
        wat_t_raw = int(max(-32768, min(32767, float(telemetry.get("EFI_Water_Temp", 0.0)) * 10.0)))
        fue_t_raw = int(max(-32768, min(32767, float(telemetry.get("EFI_Fuel_Temp", 0.0)) * 10.0)))
        payload102 = struct.pack("<hHhh", oil_t_raw, oil_p_raw, wat_t_raw, fue_t_raw)
        frame102 = CANFrame(self.ID_LUB_COOLANT, payload102, timestamp_ms=now_ms)
        frames.append(frame102)

        # -------------------------------------------------------------
        # Frame 4: 0x103 — Electrical & Vibration
        # Payload (8 bytes):
        # [0-1] Battery Voltage (scale: 0.01 V/bit, uint16)
        # [2-3] Battery Current (scale: 0.1 A/bit, int16)
        # [4-5] Alternator Temp (scale: 0.1 °F/bit, int16)
        # [6-7] Vibration (scale: 0.001 g/bit, uint16)
        # -------------------------------------------------------------
        bat_v_raw = int(min(65535, max(0, float(telemetry.get("Battery_Voltage", 0.0)) * 100.0)))
        bat_i_raw = int(max(-32768, min(32767, float(telemetry.get("Battery_Current", 0.0)) * 10.0)))
        alt_t_raw = int(max(-32768, min(32767, float(telemetry.get("Alternator_Temp", 0.0)) * 10.0)))
        vib_raw = int(min(65535, max(0, float(telemetry.get("Vibration", 0.0)) * 1000.0)))
        payload103 = struct.pack("<HhhH", bat_v_raw, bat_i_raw, alt_t_raw, vib_raw)
        frame103 = CANFrame(self.ID_ELEC_VIB, payload103, timestamp_ms=now_ms)
        frames.append(frame103)

        # -------------------------------------------------------------
        # Frame 5: 0x104 — ECU Status & Sequence Heartbeat
        # Payload (8 bytes):
        # [0]   Sequence Counter (uint8, 0-255)
        # [1]   ECU Health Status Flags (0x01: OK, 0x02: SENSOR_DEGRADED, 0x04: OVERHEAT)
        # [2-3] Indicated Power (scale: 0.1 kW/bit, uint16)
        # [4-5] Brake Power (scale: 0.1 kW/bit, uint16)
        # [6]   Thermal Efficiency (scale: 0.005 / bit, uint8)
        # [7]   CRC-8 Checksum of [0-6]
        # -------------------------------------------------------------
        status_flags = 0x01  # ECU_ONLINE_OK
        if float(telemetry.get("CHT", 0.0)) > 240.0:
            status_flags |= 0x04  # OVERHEAT
        if float(telemetry.get("Oil_Pressure", 50.0)) < 35.0:
            status_flags |= 0x08  # LOW_OIL_PRESS

        ind_p_raw = int(min(65535, max(0, float(telemetry.get("Indicated_Power_kW", 0.0)) * 10.0)))
        brk_p_raw = int(min(65535, max(0, float(telemetry.get("Brake_Power_kW", 0.0)) * 10.0)))
        eff_raw = int(min(255, max(0, float(telemetry.get("Efficiency", 0.30)) / 0.005)))
        payload104_data = struct.pack("<BBHHB", self.sequence_counter, status_flags, ind_p_raw, brk_p_raw, eff_raw)
        crc104 = self._crc8(payload104_data)
        frame104 = CANFrame(self.ID_ECU_STATUS, payload104_data + bytes([crc104]), timestamp_ms=now_ms)
        frames.append(frame104)

        # Transmit via adapter
        for f in frames:
            self.can_adapter.send(f)
            self.stats.frames_transmitted += 1

        self.stats.packets_encoded += 1
        self.stats.sequence_number = self.sequence_counter
        self.stats.last_tx_timestamp_ms = now_ms

        return frames
