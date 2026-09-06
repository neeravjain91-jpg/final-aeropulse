"""Automated Unit & Integration Tests for Virtual Sensor Layer."""
from __future__ import annotations

import pytest
from app.virtual_sensors import (
    VirtualSensorArray,
    VirtualSensor,
    SensorFaultConfig,
    SensorReading,
)


def test_virtual_sensor_array_initialization():
    """Verifies that VirtualSensorArray initializes all 16 channels with valid specifications."""
    sensors = VirtualSensorArray(master_seed=42)
    assert len(sensors.sensors) == 16
    assert "Engine_RPM" in sensors.sensors
    assert "CHT" in sensors.sensors
    assert "EGT1" in sensors.sensors
    assert "Oil_Pressure" in sensors.sensors
    assert "Battery_Voltage" in sensors.sensors
    assert sensors.sensors["CHT"].physical_unit == "deg_F"
    assert sensors.sensors["Oil_Pressure"].physical_unit == "psi"


def test_virtual_sensor_deterministic_reproducibility():
    """Verifies that two instances with the same seed generate identical sensor readings."""
    s1 = VirtualSensorArray(master_seed=123)
    s2 = VirtualSensorArray(master_seed=123)

    raw_val = {"Engine_RPM": 3000.0, "CHT": 200.0, "Oil_Pressure": 55.0}
    r1 = s1.get_observed_telemetry(raw_val, sim_time_s=1.0)
    r2 = s2.get_observed_telemetry(raw_val, sim_time_s=1.0)

    assert r1["Engine_RPM"] == r2["Engine_RPM"]
    assert r1["CHT"] == r2["CHT"]
    assert r1["Oil_Pressure"] == r2["Oil_Pressure"]


def test_virtual_sensor_bias_injection():
    """Verifies that injecting a constant bias correctly offsets the sensor output."""
    sensors = VirtualSensorArray(master_seed=42)
    sensors.configure_sensor_fault("CHT", SensorFaultConfig(bias=25.0, noise_std=0.0))

    readings = sensors.get_observed_telemetry({"CHT": 190.0}, sim_time_s=0.0)
    assert abs(readings["CHT"] - 215.0) < 0.5


def test_virtual_sensor_temporal_drift_injection():
    """Verifies that temporal drift accumulates linearly with simulation time."""
    sensors = VirtualSensorArray(master_seed=42)
    sensors.configure_sensor_fault("CHT", SensorFaultConfig(drift_rate_per_sec=10.0, noise_std=0.0))

    r_0 = sensors.get_observed_telemetry({"CHT": 200.0}, sim_time_s=0.0)["CHT"]
    r_5 = sensors.get_observed_telemetry({"CHT": 200.0}, sim_time_s=5.0)["CHT"]

    assert abs(r_0 - 200.0) < 0.5
    assert abs(r_5 - 250.0) < 0.5


def test_virtual_sensor_stuck_at_fault():
    """Verifies that a stuck-at fault overrides raw input values unconditionally."""
    sensors = VirtualSensorArray(master_seed=42)
    sensors.configure_sensor_fault("Oil_Pressure", SensorFaultConfig(stuck_at_value=12.5))

    r1 = sensors.get_observed_telemetry({"Oil_Pressure": 55.0}, sim_time_s=1.0)["Oil_Pressure"]
    r2 = sensors.get_observed_telemetry({"Oil_Pressure": 75.0}, sim_time_s=2.0)["Oil_Pressure"]

    assert r1 == 12.5
    assert r2 == 12.5


def test_virtual_sensor_dropout_fault():
    """Verifies that dropout returns configured dropout value."""
    sensors = VirtualSensorArray(master_seed=42)
    sensors.configure_sensor_fault("Engine_RPM", SensorFaultConfig(is_dropout=True, dropout_value=0.0))

    r1 = sensors.get_observed_telemetry({"Engine_RPM": 3200.0}, sim_time_s=1.0)["Engine_RPM"]
    assert r1 == 0.0


def test_virtual_sensor_saturation_limits():
    """Verifies that sensor output respects min/max saturation limits."""
    sensors = VirtualSensorArray(master_seed=42)
    sensors.configure_sensor_fault("CHT", SensorFaultConfig(max_saturation=300.0))
    readings = sensors.get_observed_telemetry({"CHT": 9999.0}, sim_time_s=0.0)
    assert readings["CHT"] <= 300.0


def test_virtual_sensor_reset_functionality():
    """Verifies that reset_all_sensors clears all active fault configurations."""
    sensors = VirtualSensorArray(master_seed=42)
    sensors.configure_sensor_fault("CHT", SensorFaultConfig(bias=50.0, stuck_at_value=300.0))
    sensors.reset_all_sensors()

    readings = sensors.get_observed_telemetry({"CHT": 190.0}, sim_time_s=0.0)
    assert abs(readings["CHT"] - 190.0) < 5.0
