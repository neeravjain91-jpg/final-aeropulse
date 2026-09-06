import pytest
import numpy as np
from app.sensor_health import assess_sensor_health

def test_dual_simultaneous_sensor_faults():
    twin = {"z_scores": {"CHT": 4.2, "Vibration": 3.8, "EFI_Water_Temp": 0.2, "Oil_Temp": 0.1, "EGT1": 0.1, "EGT2": 0.1, "EGT3": 0.1, "Engine_RPM": 0.1, "Oil_Pressure": 0.1}}
    telemetry = {"CHT": 290.0, "Vibration": 3.5, "EFI_Water_Temp": 180.0, "EGT1": 1280.0, "EGT2": 1280.0, "EGT3": 1280.0, "Engine_RPM": 4500.0, "Oil_Pressure": 60.0}
    sh = assess_sensor_health(telemetry, twin)
    assert sh["is_sensor_fault_only"] is True
    assert "CHT" in sh["suspect_sensors"]
    assert "Vibration" in sh["suspect_sensors"]

def test_sensor_drift_plus_real_engine_overheat():
    twin = {"z_scores": {"EFI_Water_Temp": 5.0, "CHT": 3.8, "Oil_Temp": 3.5, "EGT1": 2.8, "EGT2": 2.9, "EGT3": 2.9}}
    telemetry = {"EFI_Water_Temp": 240.0, "CHT": 260.0, "Oil_Temp": 220.0, "EGT1": 1420.0, "EGT2": 1430.0, "EGT3": 1425.0}
    sh = assess_sensor_health(telemetry, twin)
    assert sh["is_sensor_fault_only"] is False

def test_intermittent_sensor_dropout():
    twin = {"z_scores": {"CHT": 0.0, "EFI_Water_Temp": 0.1, "Oil_Temp": 0.1, "EGT1": 0.1, "EGT2": 0.1, "EGT3": 0.1}}
    telemetry = {"CHT": None, "EFI_Water_Temp": 180.0, "EGT1": 1280.0, "EGT2": 1280.0, "EGT3": 1280.0}
    sh = assess_sensor_health(telemetry, twin)
    assert "CHT" in sh["suspect_sensors"]
    assert sh["overall_trust_score"] < 50.0

def test_vibration_sensor_fault_during_misfire():
    twin = {"z_scores": {"EGT1": -4.5, "EGT2": 0.2, "EGT3": 0.2, "Vibration": 0.0}}
    telemetry = {"EGT1": 950.0, "EGT2": 1280.0, "EGT3": 1280.0, "Vibration": None}
    sh = assess_sensor_health(telemetry, twin)
    assert "Vibration" in sh["suspect_sensors"]
