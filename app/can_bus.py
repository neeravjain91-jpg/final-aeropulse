"""CAN Bus (ISO 11898 / CAN 2.0B) Message Framing and Telemetry Ingestion Layer."""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from .exceptions import CANBusError


@dataclass
class CANFrame:
    """Standard 8-byte CAN 2.0B Message Frame."""
    arbitration_id: int
    data: bytes
    dlc: int = 8
    is_extended: bool = False
    timestamp_ms: float = 0.0

    def __post_init__(self):
        if len(self.data) > 8:
            self.data = self.data[:8]
        elif len(self.data) < 8:
            self.data = self.data.ljust(8, b"\x00")
        self.dlc = len(self.data)

    @property
    def can_id(self) -> int:
        return self.arbitration_id

    @property
    def payload(self) -> bytes:
        return self.data


class CANHardwareAdapter:
    """Hardware Abstraction Layer for CAN transceivers (SocketCAN, Simulator, USB-CAN)."""
    def connect(self) -> bool:
        raise NotImplementedError
    def send(self, frame: CANFrame) -> bool:
        raise NotImplementedError
    def receive(self, timeout_s: float = 0.1) -> Optional[CANFrame]:
        raise NotImplementedError


class SimulatedCANAdapter(CANHardwareAdapter):
    def __init__(self):
        self.connected = False
        self.buffer: List[CANFrame] = []

    def connect(self) -> bool:
        self.connected = True
        return True

    def send(self, frame: CANFrame) -> bool:
        if not self.connected:
            raise CANBusError("CAN bus disconnected.", error_code="CAN_BUS_OFF")
        self.buffer.append(frame)
        return True

    def receive(self, timeout_s: float = 0.1) -> Optional[CANFrame]:
        if self.buffer:
            return self.buffer.pop(0)
        return None


class SocketCANAdapter(CANHardwareAdapter):
    """
    Linux SocketCAN Hardware Adapter (ISO 11898 standard on Linux kernel).
    Provides direct socket.AF_CAN / socket.SOCK_RAW interface on Linux UAV flight computers.
    Falls back gracefully to interface stub / simulation mode on non-Linux platforms (Windows).
    """

    def __init__(self, interface_name: str = "vcan0", bitrate: int = 500000):
        import socket as _socket
        self.interface_name = interface_name
        self.bitrate = bitrate
        self.connected = False
        self._socket = None
        self._is_linux = hasattr(_socket, "AF_CAN")

    def connect(self) -> bool:
        if self._is_linux:
            try:
                import socket as _socket
                self._socket = _socket.socket(_socket.AF_CAN, _socket.SOCK_RAW, _socket.CAN_RAW)
                self._socket.bind((self.interface_name,))
                self.connected = True
                return True
            except Exception:
                self.connected = False
                return False
        else:
            # Non-Linux platform: interface-ready demonstrator
            self.connected = False
            return False

    def send(self, frame: CANFrame) -> bool:
        if self._is_linux and self.connected and self._socket:
            can_id = frame.arbitration_id
            if frame.is_extended:
                can_id |= 0x80000000
            can_pkt = struct.pack("=IB3x8s", can_id, frame.dlc, frame.data)
            self._socket.send(can_pkt)
            return True
        elif not self._is_linux:
            return True
        return False

    def receive(self, timeout_s: float = 0.1) -> Optional[CANFrame]:
        if self._is_linux and self.connected and self._socket:
            import select
            r, _, _ = select.select([self._socket], [], [], timeout_s)
            if r:
                can_pkt = self._socket.recv(16)
                can_id, dlc, data = struct.unpack("=IB3x8s", can_pkt)
                return CANFrame(arbitration_id=can_id & 0x1FFFFFFF, data=data[:dlc], dlc=dlc)
        return None


class CANBusInterface:
    """
    Decodes and encodes canonical UAV engine CAN frames.
    Message ID Mapping:
      0x100: Engine Dynamics (RPM, MAP, Fuel Flow, Throttle)
      0x101: Temperatures (EGT1, EGT2, EGT3, CHT)
      0x102: Lubrication & Coolant (Oil Temp, Oil Press, Water Temp, Fuel Temp)
      0x103: Electrical & Vibration (Battery V, Battery I, Alt Temp, Vibration)
    """

    ID_ENGINE_DYNAMICS = 0x100
    ID_TEMPERATURES = 0x101
    ID_LUB_COOLANT = 0x102
    ID_ELEC_VIB = 0x103

    def __init__(self, adapter: Optional[CANHardwareAdapter] = None):
        self.adapter = adapter or SimulatedCANAdapter()
        self.adapter.connect()
        self.sequence_counter: int = 0
        self.last_decoded_telemetry: Dict[str, Any] = {}
        self.stats = {"frames_rx": 0, "crc_errors": 0, "seq_errors": 0, "dropped": 0}

    @staticmethod
    def _crc8(data: bytes) -> int:
        """Computes simple CRC-8 checksum for payload validation."""
        crc = 0x00
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x07) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    def encode_telemetry(self, telemetry: Dict[str, Any], timestamp_ms: float = 0.0) -> List[CANFrame]:
        """Encodes canonical telemetry dictionary into 4 standard CAN frames."""
        frames: List[CANFrame] = []
        self.sequence_counter = (self.sequence_counter + 1) % 16

        # 1. 0x100 Engine Dynamics
        rpm_raw = int(round(min(65535, max(0, float(telemetry.get("Engine_RPM", 0.0)) / 0.25))))
        map_raw = int(round(min(65535, max(0, float(telemetry.get("MAP_Injector", 0.0)) / 0.01))))
        ff_raw = int(round(min(65535, max(0, float(telemetry.get("Fuel_Flow", 0.0)) / 0.01))))
        thr_raw = int(round(min(255, max(0, float(telemetry.get("Load", 0.6)) * 200))))
        payload100 = struct.pack("<HHHB", rpm_raw, map_raw, ff_raw, thr_raw)
        crc100 = self._crc8(payload100)
        frames.append(CANFrame(self.ID_ENGINE_DYNAMICS, payload100 + bytes([crc100]), timestamp_ms=timestamp_ms))

        # 2. 0x101 Temperatures
        egt1_raw = int(round(min(65535, max(0, float(telemetry.get("EGT1", 0.0)) * 10.0))))
        egt2_raw = int(round(min(65535, max(0, float(telemetry.get("EGT2", 0.0)) * 10.0))))
        egt3_raw = int(round(min(65535, max(0, float(telemetry.get("EGT3", 0.0)) * 10.0))))
        cht_raw = int(round(min(65535, max(0, float(telemetry.get("CHT", 0.0)) * 10.0))))
        payload101 = struct.pack("<HHHH", egt1_raw, egt2_raw, egt3_raw, cht_raw)
        frames.append(CANFrame(self.ID_TEMPERATURES, payload101, timestamp_ms=timestamp_ms))

        # 3. 0x102 Lubrication & Coolant
        oil_t_raw = int(round(max(-32768, min(32767, float(telemetry.get("Oil_Temp", 0.0)) * 10.0))))
        oil_p_raw = int(round(min(65535, max(0, float(telemetry.get("Oil_Pressure", 0.0)) * 10.0))))
        wat_t_raw = int(round(max(-32768, min(32767, float(telemetry.get("EFI_Water_Temp", 0.0)) * 10.0))))
        fue_t_raw = int(round(max(-32768, min(32767, float(telemetry.get("EFI_Fuel_Temp", 0.0)) * 10.0))))
        payload102 = struct.pack("<hHhh", oil_t_raw, oil_p_raw, wat_t_raw, fue_t_raw)
        frames.append(CANFrame(self.ID_LUB_COOLANT, payload102, timestamp_ms=timestamp_ms))

        # 4. 0x103 Electrical & Vibration
        bat_v_raw = int(round(min(65535, max(0, float(telemetry.get("Battery_Voltage", 0.0)) * 100.0))))
        bat_i_raw = int(round(max(-32768, min(32767, float(telemetry.get("Battery_Current", 0.0)) * 10.0))))
        alt_t_raw = int(round(max(-32768, min(32767, float(telemetry.get("Alternator_Temp", 0.0)) * 10.0))))
        vib_raw = int(round(min(65535, max(0, float(telemetry.get("Vibration", 0.0)) * 1000.0))))
        payload103 = struct.pack("<HhhH", bat_v_raw, bat_i_raw, alt_t_raw, vib_raw)
        frames.append(CANFrame(self.ID_ELEC_VIB, payload103, timestamp_ms=timestamp_ms))

        return frames

    def decode_frame(self, frame: CANFrame) -> Dict[str, Any]:
        """Decodes single incoming CAN frame into telemetry fields with error validation."""
        self.stats["frames_rx"] += 1
        if frame.arbitration_id == self.ID_ENGINE_DYNAMICS:
            if len(frame.data) >= 8:
                payload = frame.data[:7]
                expected_crc = self._crc8(payload)
                actual_crc = frame.data[7]
                if actual_crc != expected_crc:
                    self.stats["crc_errors"] += 1
                    return {"_error": "CAN_CRC_MISMATCH", "arbitration_id": frame.arbitration_id}
                rpm_raw, map_raw, ff_raw, thr_raw = struct.unpack("<HHHB", payload)
                self.last_decoded_telemetry["Engine_RPM"] = round(rpm_raw * 0.25, 1)
                self.last_decoded_telemetry["MAP_Injector"] = round(map_raw * 0.01, 2)
                self.last_decoded_telemetry["Fuel_Flow"] = round(ff_raw * 0.01, 2)
                self.last_decoded_telemetry["Load"] = round(thr_raw / 200.0, 3)

        elif frame.arbitration_id == self.ID_TEMPERATURES:
            if len(frame.data) >= 8:
                egt1_raw, egt2_raw, egt3_raw, cht_raw = struct.unpack("<HHHH", frame.data[:8])
                self.last_decoded_telemetry["EGT1"] = round(egt1_raw * 0.1, 1)
                self.last_decoded_telemetry["EGT2"] = round(egt2_raw * 0.1, 1)
                self.last_decoded_telemetry["EGT3"] = round(egt3_raw * 0.1, 1)
                self.last_decoded_telemetry["CHT"] = round(cht_raw * 0.1, 1)

        elif frame.arbitration_id == self.ID_LUB_COOLANT:
            if len(frame.data) >= 8:
                oil_t_raw, oil_p_raw, wat_t_raw, fue_t_raw = struct.unpack("<hHhh", frame.data[:8])
                self.last_decoded_telemetry["Oil_Temp"] = round(oil_t_raw * 0.1, 1)
                self.last_decoded_telemetry["Oil_Pressure"] = round(oil_p_raw * 0.1, 1)
                self.last_decoded_telemetry["EFI_Water_Temp"] = round(wat_t_raw * 0.1, 1)
                self.last_decoded_telemetry["EFI_Fuel_Temp"] = round(fue_t_raw * 0.1, 1)

        elif frame.arbitration_id == self.ID_ELEC_VIB:
            if len(frame.data) >= 8:
                bat_v_raw, bat_i_raw, alt_t_raw, vib_raw = struct.unpack("<HhhH", frame.data[:8])
                self.last_decoded_telemetry["Battery_Voltage"] = round(bat_v_raw * 0.01, 2)
                self.last_decoded_telemetry["Battery_Current"] = round(bat_i_raw * 0.1, 2)
                self.last_decoded_telemetry["Alternator_Temp"] = round(alt_t_raw * 0.1, 1)
                self.last_decoded_telemetry["Vibration"] = round(vib_raw * 0.001, 3)

        return dict(self.last_decoded_telemetry)

    def decode_frames(self, frames: List[CANFrame]) -> Dict[str, Any]:
        """Decodes a sequence/batch of incoming CAN frames into a unified telemetry state."""
        result: Dict[str, Any] = {}
        for frame in frames:
            decoded = self.decode_frame(frame)
            result.update(decoded)
        return result


AeroPulseCANInterface = CANBusInterface
