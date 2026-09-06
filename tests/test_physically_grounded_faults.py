# Tests for physically grounded fault propagation and sensor isolation.
import pytest
from app.simulator import inject_fault


def test_thermal_overheating_propagation():
    nominal = {"CHT": 190.0, "EFI_Water_Temp": 82.0, "Oil_Temp": 85.0, "EGT1": 1150.0, "Efficiency": 0.32}
    faulted = inject_fault(nominal, fault="overheating", severity=0.8)

    # Overheating must increase CHT, coolant temp, oil temp, and reduce efficiency
    assert faulted["CHT"] > nominal["CHT"] * 1.15
    assert faulted["EFI_Water_Temp"] > nominal["EFI_Water_Temp"] * 1.10
    assert faulted["Oil_Temp"] > nominal["Oil_Temp"] * 1.08
    assert faulted["Efficiency"] < nominal["Efficiency"]


def test_lubrication_degradation_propagation():
    nominal = {"Oil_Pressure": 50.0, "Oil_Temp": 85.0, "Vibration": 1.0, "Efficiency": 0.32}
    faulted = inject_fault(nominal, fault="lubrication", severity=0.7)

    # Lubrication failure drops oil pressure, elevates oil temp and vibration
    assert faulted["Oil_Pressure"] < nominal["Oil_Pressure"] * 0.65
    assert faulted["Oil_Temp"] > nominal["Oil_Temp"] * 1.15
    assert faulted["Vibration"] > nominal["Vibration"] * 1.20


def test_misfire_combustion_propagation():
    nominal = {"Engine_RPM": 3000.0, "EGT1": 1180.0, "EGT2": 1180.0, "Vibration": 1.0}
    faulted = inject_fault(nominal, fault="misfire", severity=0.6)

    # Misfire drops cylinder 1 EGT, drops RPM, and elevates vibration
    assert faulted["EGT1"] < nominal["EGT1"] * 0.85
    assert faulted["Engine_RPM"] < nominal["Engine_RPM"]
    assert faulted["Vibration"] > nominal["Vibration"] + 0.5


def test_sensor_fault_does_not_modify_engine_physics():
    nominal = {"CHT": 190.0, "Engine_RPM": 3000.0, "Fuel_Flow": 28.0, "Oil_Pressure": 50.0, "EFI_Water_Temp": 82.0}
    faulted_drift = inject_fault(nominal, fault="sensor_drift", severity=0.8)
    faulted_spike = inject_fault(nominal, fault="sensor_spike", severity=0.8)

    # Sensor faults modify transducer buffer but preserve engine mechanics
    assert faulted_drift.get("EFI_Water_Temp", 0.0) > nominal["EFI_Water_Temp"] + 40.0
    assert faulted_drift["Engine_RPM"] == nominal["Engine_RPM"]
    assert faulted_drift["Fuel_Flow"] == nominal["Fuel_Flow"]
    assert faulted_spike["CHT"] > nominal["CHT"] + 90.0
    assert faulted_spike["Engine_RPM"] == nominal["Engine_RPM"]
