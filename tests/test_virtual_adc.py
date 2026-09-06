"""Automated Unit & Integration Tests for Virtual ADC and Digital Sensor Ingestion."""
from __future__ import annotations

import pytest
from app.virtual_adc import VirtualADCSystem, ADCChannelConfig, ADCConversionResult


def test_virtual_adc_system_initialization():
    """Verifies that VirtualADCSystem initializes with all 16 channel configurations."""
    adc = VirtualADCSystem()
    assert len(adc.channels) == 16
    assert "Engine_RPM" in adc.channels
    assert "CHT" in adc.channels
    assert "Oil_Pressure" in adc.channels
    assert "Battery_Voltage" in adc.channels


def test_virtual_adc_quantization_12bit():
    """Verifies that 12-bit ADC converts continuous voltage to [0, 4095] counts accurately."""
    adc = VirtualADCSystem()
    trace = adc.convert_channel("CHT", sensor_value=200.0)

    assert trace.adc_digital_counts >= 0
    assert trace.adc_digital_counts <= 4095
    assert abs(trace.ecu_observed_value - 200.0) < 0.5


def test_virtual_adc_quantization_16bit():
    """Verifies that 16-bit ADC converts higher precision signals to [0, 65535] counts."""
    adc = VirtualADCSystem()
    trace = adc.convert_channel("EFI_Fuel_Temp", sensor_value=25.0)

    assert trace.adc_digital_counts >= 0
    assert trace.adc_digital_counts <= 65535
    assert abs(trace.ecu_observed_value - 25.0) < 0.05


def test_virtual_adc_voltage_clamping():
    """Verifies that out-of-range sensor voltages saturate cleanly at ADC reference rails."""
    adc = VirtualADCSystem()
    # Negative value below engineering min
    trace_low = adc.convert_channel("Oil_Pressure", sensor_value=-50.0)
    assert trace_low.sensor_analog_voltage == 0.5
    assert trace_low.is_saturated is True

    # Massive value exceeding engineering max
    trace_high = adc.convert_channel("Oil_Pressure", sensor_value=999.0)
    assert trace_high.sensor_analog_voltage == 4.5
    assert trace_high.is_saturated is True


def test_virtual_adc_4tier_audit_trace():
    """Verifies that audit trace contains complete physical -> voltage -> counts -> observed chain."""
    adc = VirtualADCSystem()
    telemetry = {"Engine_RPM": 4500.0, "CHT": 215.0, "Oil_Pressure": 58.0}
    traces = adc.convert_sensor_readings(telemetry)

    assert len(traces) == 3
    for channel_name, tr in traces.items():
        assert tr.channel_name == channel_name
        assert tr.simulated_physical_value is not None
        assert tr.adc_digital_counts is not None
        assert tr.ecu_observed_value is not None


def test_virtual_adc_digital_bus_passthrough():
    """Verifies that purely digital telemetry fields pass through without loss of precision."""
    adc = VirtualADCSystem()
    telemetry = {"Operating_State": "CRUISE", "Degradation_Severity": 0.45}
    ecu_obs = adc.get_ecu_ingested_telemetry(telemetry)

    assert ecu_obs["Operating_State"] == "CRUISE"
    assert ecu_obs["Degradation_Severity"] == 0.45
