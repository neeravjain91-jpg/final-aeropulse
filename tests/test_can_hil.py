"""Comprehensive Test Suite for CAN HIL Closed-Loop Simulator, Fault Injections, and Security."""
from __future__ import annotations

import pytest

from app.can_hil import CANHILSimulator, HILFaultType


def test_can_hil_simulator_initialization():
    """Verifies that CAN HIL simulator initializes all closed-loop components."""
    sim = CANHILSimulator()
    assert sim.engine is not None
    assert sim.ecu is not None
    assert sim.fadec is not None
    assert sim.edge_node is not None
    assert sim.security_mgr is not None
    assert len(sim.step_history) == 0


def test_can_hil_closed_loop_nominal_step():
    """Verifies that a single nominal HIL step executes cleanly across all 10 pipeline stages."""
    sim = CANHILSimulator()
    step_res = sim.execute_step(
        step_index=0,
        sim_time_ms=0.0,
        pilot_throttle=0.60,
        rpm=3000.0,
        altitude_ft=5000.0,
        ambient_c=25.0,
    )

    assert step_res.step_index == 0
    assert step_res.pilot_throttle == 0.60
    assert step_res.effective_throttle == 0.60
    assert len(step_res.can_frames_tx) == 5
    assert len(step_res.can_frames_rx) == 5
    assert step_res.fadec_state.mode == "NOMINAL"
    assert step_res.security_verified is True
    assert step_res.step_latency_ms < 5.0


def test_can_hil_master_16_scenario_validation_matrix():
    """Verifies that all 16 HIL validation scenarios pass 100%."""
    sim = CANHILSimulator()
    report = sim.run_master_hil_validation_suite()

    assert report["total_scenarios"] == 16
    assert report["passed_scenarios"] == 16
    assert report["failed_scenarios"] == 0
    assert report["pass_ratio_pct"] == 100.0
    assert report["status"] == "PASS"

    timing = report["timing_statistics"]
    assert timing["mean_latency_ms"] < 2.0
    assert timing["p99_latency_ms"] < 5.0


def test_can_crc_corruption_rejection():
    """Verifies that corrupted CRC CAN frames are rejected by FADEC and logged as CAN_CRC_MISMATCH."""
    sim = CANHILSimulator()
    res = sim.run_scenario(
        scenario_name="CRC_CORRUPTION_TEST",
        fault_type=HILFaultType.CRC_CORRUPTION,
        num_steps=10,
    )
    assert res.passed is True
    assert res.can_integrity_ok is True


def test_anti_replay_security_defense():
    """Verifies that replayed and stale sequence packets are rejected by the security layer."""
    sim = CANHILSimulator()
    res_replay = sim.run_scenario(
        scenario_name="SEQUENCE_REPLAY_TEST",
        fault_type=HILFaultType.SEQUENCE_REPLAY,
        num_steps=10,
    )
    assert res_replay.passed is True
    assert res_replay.security_ok is True


def test_sensor_vs_engine_fault_discrimination():
    """
    Verifies that the system discriminates Case A (Real Thermal Degradation) from Case B (Isolated Sensor Drift).
    """
    sim = CANHILSimulator()

    # Case A: Real Engine Thermal Degradation
    res_engine = sim.run_scenario(
        scenario_name="CASE_A_THERMAL_ENGINE",
        fault_type=HILFaultType.THERMAL_DEGRADATION,
        severity=0.85,
        num_steps=15,
    )
    assert res_engine.passed is True
    assert "ENGINE_OVERTEMP" in res_engine.dtcs_raised
    assert res_engine.fadec_derate_triggered is True

    # Case B: Isolated Sensor Drift
    sim.reset()
    res_sensor = sim.run_scenario(
        scenario_name="CASE_B_SENSOR_DRIFT",
        fault_type=HILFaultType.SENSOR_TRANSDUCER_FAULT,
        severity=0.85,
        num_steps=15,
    )
    assert res_sensor.passed is True
    assert "SENSOR_IMPLAUSIBILITY" in res_sensor.dtcs_raised
    # Sensor fault should not cause false engine derating
    assert res_sensor.fadec_derate_triggered is False


def test_failure_recovery_on_frame_dropout():
    """Verifies that frame dropouts are handled safely without crashing or fabricating health state."""
    sim = CANHILSimulator()
    res = sim.run_scenario(
        scenario_name="FRAME_DROPOUT_TEST",
        fault_type=HILFaultType.FRAME_DROPOUT,
        num_steps=10,
    )
    assert res.passed is True
