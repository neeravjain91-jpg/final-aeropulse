"""Automated Unit & Integration Tests for Master Software-in-the-Loop (SIL) Emulation Suite."""
from __future__ import annotations

import pytest
from app.virtual_sil import MasterSILSimulator, SILScenarioResult


def test_master_sil_step_cycle_execution():
    """Verifies that MasterSILSimulator executes a closed-loop step cycle across all 11 stages."""
    sim = MasterSILSimulator(master_seed=42)
    step = sim.step_cycle(throttle_cmd=0.60, altitude_ft=5000.0, ambient_c=25.0)

    assert "physical_state" in step
    assert "power_state" in step
    assert "ecu_observed" in step
    assert "edge_summary" in step
    assert "fadec_state" in step
    assert "watchdog_status" in step
    assert "scheduler_summary" in step
    assert "actuated_throttle" in step
    assert step["actuated_throttle"] == 0.60
    assert step["host_cycle_latency_ms"] > 0.0


def test_master_sil_18_scenarios_all_pass():
    """Verifies that all 18 deterministic SIL scenarios (SIL_A through SIL_R) execute and pass."""
    sim = MasterSILSimulator(master_seed=42)
    results = sim.run_18_sil_scenarios()

    assert len(results) == 18
    passed_count = sum(1 for r in results if r.passed)
    failed_scenarios = [r.scenario_id for r in results if not r.passed]

    assert passed_count == 18, f"Failed SIL scenarios: {failed_scenarios}"


def test_master_sil_sensor_vs_engine_fault_discrimination():
    """
    Verifies formal discrimination between:
    - Case A: Isolated transducer fault (vetoes false derate)
    - Case B: True engine degradation (enforces autonomic derate)
    """
    sim = MasterSILSimulator(master_seed=42)
    res = sim.demonstrate_sensor_vs_engine_fault()

    assert res["discrimination_demonstrated"] is True
    assert res["case_a_isolated_sensor_fault"]["passed"] is True
    assert res["case_a_isolated_sensor_fault"]["false_derate_vetoed"] is True
    assert res["case_b_true_engine_degradation"]["passed"] is True
    assert res["case_b_true_engine_degradation"]["autonomic_derate_enforced"] is True


def test_master_sil_closed_loop_flight_trace():
    """Verifies that the full 10-minute flight mission trace generates 60 contiguous data points."""
    sim = MasterSILSimulator(master_seed=42)
    trace = sim.run_closed_loop_mission_flight()

    assert len(trace) == 60
    phases = set(pt.phase_name for pt in trace)
    assert "STARTUP" in phases
    assert "TAKEOFF" in phases
    assert "CLIMB" in phases
    assert "CRUISE" in phases
    assert "HIGH_ALTITUDE" in phases
    assert "THERMAL_DEGRADATION" in phases
    assert "FADEC_AUTONOMIC_DERATE" in phases
    assert "RECOVERY_LANDING" in phases

    for pt in trace:
        assert pt.rpm > 0.0
        assert pt.cht > 0.0
        assert pt.bus_voltage > 0.0
        assert pt.sensor_trust >= 0.0


def test_master_sil_subsystem_benchmarking():
    """Verifies that desktop host profiling benchmarks all virtual hardware subsystems."""
    sim = MasterSILSimulator(master_seed=42)
    bench = sim.benchmark_sil_subsystems(iterations=50)

    assert bench["iterations"] == 50
    assert "virtual_sensors" in bench["subsystems_us"]
    assert "virtual_adc" in bench["subsystems_us"]
    assert "virtual_can_bus" in bench["subsystems_us"]
    assert "complete_closed_loop_step_ms" in bench
    assert bench["throughput_steps_per_sec"] > 0.0
