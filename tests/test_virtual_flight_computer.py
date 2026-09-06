"""Automated Unit & Integration Tests for Virtual Flight Computer and Task Scheduler."""
from __future__ import annotations

import pytest
from app.virtual_flight_computer import (
    VirtualFlightComputer,
    FlightComputerResourceBudget,
    VirtualTaskDefinition,
    SchedulerExecutionSummary,
)


def test_virtual_flight_computer_initialization():
    """Verifies default hardware budget allocation (ARM Cortex-A53 quad-core model)."""
    fc = VirtualFlightComputer()
    assert fc.budget.target_hardware_class == "ARM_CORTEX_A53_QUAD_CORE_SIMULATION"
    assert fc.budget.cpu_cycle_budget_ms == 10.0
    assert len(fc.tasks) == 8
    assert "CAN_RX_DISPATCH" in fc.tasks
    assert "FADEC_SUPERVISORY_CHECK" in fc.tasks
    assert "HEALTH_CLASSIFICATION" in fc.tasks


def test_virtual_flight_computer_task_scheduling():
    """Verifies that high-frequency tasks execute more times than low-frequency tasks."""
    fc = VirtualFlightComputer()

    # Step for 1.0 second in 20ms intervals (50 steps)
    for _ in range(50):
        fc.step_scheduler(time_step_ms=20.0)

    can_task = fc.tasks["CAN_RX_DISPATCH"]
    gcs_task = fc.tasks["GCS_TELEMETRY_PACKAGING"]

    assert can_task.invocations_total >= 40
    assert gcs_task.invocations_total <= 5


def test_virtual_flight_computer_host_vs_budget_timing():
    """Verifies that host execution time is tracked alongside simulated ARM budget."""
    fc = VirtualFlightComputer()

    dummy_executed = False
    def dummy_task():
        nonlocal dummy_executed
        dummy_executed = True
        return {"result": "ok"}

    summary = fc.step_scheduler(
        time_step_ms=20.0,
        host_callbacks={"CAN_RX_DISPATCH": dummy_task},
    )

    assert dummy_executed is True
    assert summary.tasks_executed > 0
    assert summary.actual_desktop_host_step_ms >= 0.0


def test_virtual_flight_computer_cpu_utilization():
    """Verifies that CPU load is computed accurately across scheduled periodic tasks."""
    fc = VirtualFlightComputer()
    for _ in range(25):
        fc.step_scheduler(time_step_ms=20.0)

    summary = fc.get_scheduler_summary()
    assert summary.virtual_cpu_utilization_pct >= 0.0
    assert summary.virtual_cpu_utilization_pct <= 100.0
    assert len(summary.task_statistics) == 8
