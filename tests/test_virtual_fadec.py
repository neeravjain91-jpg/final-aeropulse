"""Automated Unit & Integration Tests for Virtual FADEC Supervisory Logic."""
from __future__ import annotations

import pytest

from app.engine_model import ReducedOrderPistonEngine
from app.virtual_ecu import VirtualECU
from app.virtual_fadec import DTCSeverity, DiagnosticTroubleCode, VirtualFADEC


def test_virtual_fadec_initialization():
    """Verifies that Virtual FADEC initializes with default parameters and empty DTC list."""
    fadec = VirtualFADEC(fadec_id="FADEC-TEST-01")
    assert fadec.fadec_id == "FADEC-TEST-01"
    assert len(fadec.active_dtcs) == 0
    assert fadec.last_supervisory_state is None


def test_virtual_fadec_nominal_operation():
    """Verifies that nominal telemetry produces NOMINAL mode with zero DTCs and full throttle capability."""
    engine = ReducedOrderPistonEngine()
    telemetry = engine.simulate(rpm=3000.0, throttle=0.60, altitude_ft=5000.0, ambient_c=25.0)

    fadec = VirtualFADEC()
    state = fadec.evaluate_supervisory_logic(telemetry, pilot_commanded_throttle=0.75, timestamp_ms=100.0)

    assert state.mode == "NOMINAL"
    assert state.throttle_cap == 1.00
    assert state.commanded_throttle == 0.75
    assert len(state.active_dtcs) == 0
    assert len(state.exceedances_detected) == 0


def test_virtual_fadec_thermal_limit_derate():
    """Verifies that exceeding CHT redline raises ENGINE_OVERTEMP DTC and enforces 50% throttle derate."""
    fadec = VirtualFADEC()
    telemetry = {
        "Engine_RPM": 3000.0,
        "CHT": 255.0,  # Exceeds 245.0 °F redline
        "Oil_Temp": 200.0,
        "Oil_Pressure": 55.0,
        "EGT1": 1300.0,
        "EGT2": 1300.0,
        "Vibration": 1.20,
        "Battery_Voltage": 28.0,
    }

    state = fadec.evaluate_supervisory_logic(telemetry, pilot_commanded_throttle=0.90, timestamp_ms=200.0)

    assert state.mode == "DERATE_THROTTLE_MAX_50"
    assert state.throttle_cap == 0.50
    assert state.commanded_throttle == 0.50
    assert "ENGINE_OVERTEMP" in [d.code for d in state.active_dtcs]
    assert "CHT_OVERTEMP" in state.exceedances_detected


def test_virtual_fadec_low_oil_pressure_emergency():
    """Verifies that critically low oil pressure raises LOW_OIL_PRESSURE DTC and enforces emergency RTL derate."""
    fadec = VirtualFADEC()
    telemetry = {
        "Engine_RPM": 3000.0,
        "CHT": 200.0,
        "Oil_Temp": 210.0,
        "Oil_Pressure": 22.0,  # Below 25.0 psi -> EMERGENCY
        "EGT1": 1250.0,
        "EGT2": 1250.0,
        "Vibration": 1.10,
        "Battery_Voltage": 28.0,
    }

    state = fadec.evaluate_supervisory_logic(telemetry, pilot_commanded_throttle=0.80, timestamp_ms=300.0)

    assert state.mode == "EMERGENCY_RTL"
    assert state.throttle_cap == 0.40
    assert state.commanded_throttle == 0.40
    assert "LOW_OIL_PRESSURE" in [d.code for d in state.active_dtcs]


def test_virtual_fadec_ingest_can_frames():
    """Verifies that Virtual FADEC decodes CAN frames from Virtual ECU accurately."""
    engine = ReducedOrderPistonEngine()
    telemetry = engine.simulate(rpm=3200.0, throttle=0.65)

    ecu = VirtualECU()
    frames = ecu.encode_and_transmit(telemetry, timestamp_ms=400.0)

    fadec = VirtualFADEC()
    decoded = fadec.ingest_can_frames(frames)

    assert abs(decoded["Engine_RPM"] - 3200.0) <= 2.0
    assert "CHT" in decoded
    assert "Oil_Pressure" in decoded
    assert "Battery_Voltage" in decoded
