# Tests for CAN 2.0B frame encoding, decoding, and CRC validation.
import pytest
from app.can_bus import CANBusInterface, CANFrame


def test_can_encode_and_decode_roundtrip():
    can = CANBusInterface()
    telemetry = {
        "Engine_RPM": 3200.0,
        "MAP_Injector": 95.5,
        "Fuel_Flow": 28.4,
        "Load": 0.65,
        "EGT1": 1210.0,
        "EGT2": 1205.0,
        "EGT3": 1215.0,
        "CHT": 210.0,
        "Oil_Temp": 88.0,
        "Oil_Pressure": 48.5,
        "EFI_Water_Temp": 84.0,
        "EFI_Fuel_Temp": 28.0,
        "Battery_Voltage": 28.1,
        "Battery_Current": 12.5,
        "Alternator_Temp": 58.0,
        "Vibration": 1.15,
    }

    frames = can.encode_telemetry(telemetry, timestamp_ms=1000.0)
    assert len(frames) == 4

    decoded = {}
    for frame in frames:
        decoded.update(can.decode_frame(frame))

    assert abs(decoded["Engine_RPM"] - telemetry["Engine_RPM"]) < 0.5
    assert abs(decoded["EGT1"] - telemetry["EGT1"]) < 0.5
    assert abs(decoded["CHT"] - telemetry["CHT"]) < 0.5
    assert abs(decoded["Oil_Pressure"] - telemetry["Oil_Pressure"]) < 0.5
    assert abs(decoded["Battery_Voltage"] - telemetry["Battery_Voltage"]) < 0.1


def test_can_crc_corruption_rejection():
    can = CANBusInterface()
    telemetry = {"Engine_RPM": 3000.0, "MAP_Injector": 90.0, "Fuel_Flow": 25.0, "Load": 0.6}
    frames = can.encode_telemetry(telemetry)
    frame0 = frames[0]

    # Corrupt byte 2
    corrupted_data = bytearray(frame0.data)
    corrupted_data[2] ^= 0xFF
    corrupted_frame = CANFrame(frame0.arbitration_id, bytes(corrupted_data))

    res = can.decode_frame(corrupted_frame)
    assert res.get("_error") == "CAN_CRC_MISMATCH"
