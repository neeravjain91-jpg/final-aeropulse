"""Virtual Flight Computer and Real-Time Periodic Task Scheduler.

Emulates ARM-class airborne flight computer resource budgets, periodic task queues,
deadline tracking, and overload behavior while measuring actual host desktop execution.
"""
from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class FlightComputerResourceBudget:
    """Configurable resource budget envelope simulating an embedded flight computer."""
    target_hardware_class: str = "ARM_CORTEX_A53_QUAD_CORE_SIMULATION"
    cpu_cycle_budget_ms: float = 10.0  # 10ms cycle for 100 Hz top-level loop
    max_ram_budget_mb: float = 128.0
    watchdog_timeout_ms: float = 200.0
    task_deadline_tolerance_pct: float = 15.0  # Allow 15% deadline jitter before flagging


@dataclass
class VirtualTaskDefinition:
    """Definition and execution profile of a periodic airborne flight computer task."""
    name: str
    frequency_hz: float
    period_ms: float
    budget_execution_time_ms: float  # Configured simulated execution budget
    priority: int  # 1 = Highest (CAN RX), 10 = Lowest (Background GCS)
    last_run_sim_time_ms: float = 0.0
    invocations_total: int = 0
    deadline_misses: int = 0
    actual_measured_latencies_us: List[float] = field(default_factory=list)


@dataclass
class SchedulerExecutionSummary:
    sim_time_ms: float
    tasks_executed: int
    total_deadline_misses: int
    virtual_cpu_utilization_pct: float
    is_overloaded: bool
    actual_desktop_host_step_ms: float
    task_statistics: Dict[str, Dict[str, Any]]


class VirtualFlightComputer:
    """
    Virtual Flight Computer coordinating scheduled execution of UAV digital twin analytics.
    """

    def __init__(self, budget: Optional[FlightComputerResourceBudget] = None):
        self.budget = budget or FlightComputerResourceBudget()
        self.tasks: Dict[str, VirtualTaskDefinition] = {
            "CAN_RX_DISPATCH": VirtualTaskDefinition("CAN_RX_DISPATCH", 100.0, 10.0, budget_execution_time_ms=0.5, priority=1),
            "TELEMETRY_VALIDATION": VirtualTaskDefinition("TELEMETRY_VALIDATION", 50.0, 20.0, budget_execution_time_ms=0.8, priority=2),
            "SENSOR_TRUST_ASSESSMENT": VirtualTaskDefinition("SENSOR_TRUST_ASSESSMENT", 50.0, 20.0, budget_execution_time_ms=1.2, priority=3),
            "DIGITAL_TWIN_RESIDUAL": VirtualTaskDefinition("DIGITAL_TWIN_RESIDUAL", 20.0, 50.0, budget_execution_time_ms=1.5, priority=4),
            "FADEC_SUPERVISORY_CHECK": VirtualTaskDefinition("FADEC_SUPERVISORY_CHECK", 20.0, 50.0, budget_execution_time_ms=1.0, priority=5),
            "HEALTH_CLASSIFICATION": VirtualTaskDefinition("HEALTH_CLASSIFICATION", 10.0, 100.0, budget_execution_time_ms=0.5, priority=6),
            "PROGNOSTIC_RUL_UPDATE": VirtualTaskDefinition("PROGNOSTIC_RUL_UPDATE", 2.0, 500.0, budget_execution_time_ms=3.0, priority=7),
            "GCS_TELEMETRY_PACKAGING": VirtualTaskDefinition("GCS_TELEMETRY_PACKAGING", 5.0, 200.0, budget_execution_time_ms=2.0, priority=8),
        }
        self.sim_time_ms: float = 0.0
        self.overload_multiplier: float = 1.0

    def set_overload_multiplier(self, multiplier: float = 1.0) -> None:
        """Inject task burst or artificial workload multiplier to test overload behavior."""
        self.overload_multiplier = max(0.1, multiplier)

    def execute_scheduled_tasks(
        self,
        sim_time_ms: float,
        task_handlers: Optional[Dict[str, Callable[[], Any]]] = None,
    ) -> SchedulerExecutionSummary:
        """
        Executes ready periodic tasks whose periods have elapsed since their last execution.
        Measures real desktop execution time and compares against simulated ARM task budgets.
        """
        self.sim_time_ms = sim_time_ms
        host_start_ns = time.perf_counter_ns()

        tasks_to_run: List[VirtualTaskDefinition] = []
        for task in sorted(self.tasks.values(), key=lambda t: t.priority):
            if self.sim_time_ms - task.last_run_sim_time_ms >= task.period_ms:
                tasks_to_run.append(task)

        simulated_cpu_busy_ms = 0.0
        handlers = task_handlers or {}

        for task in tasks_to_run:
            t0_ns = time.perf_counter_ns()

            # Execute real python logic if handler provided
            if task.name in handlers:
                try:
                    handlers[task.name]()
                except Exception:
                    pass

            actual_us = (time.perf_counter_ns() - t0_ns) / 1000.0
            task.actual_measured_latencies_us.append(actual_us)
            if len(task.actual_measured_latencies_us) > 1000:
                task.actual_measured_latencies_us.pop(0)

            # Simulated task execution cost under configured budget
            sim_cost_ms = task.budget_execution_time_ms * self.overload_multiplier
            simulated_cpu_busy_ms += sim_cost_ms

            # Check deadline miss
            if sim_cost_ms > (task.period_ms * (1.0 + self.budget.task_deadline_tolerance_pct / 100.0)):
                task.deadline_misses += 1

            task.invocations_total += 1
            task.last_run_sim_time_ms = self.sim_time_ms

        host_total_ms = (time.perf_counter_ns() - host_start_ns) / 1_000_000.0

        # Calculate simulated virtual CPU utilization
        cycle_budget = self.budget.cpu_cycle_budget_ms
        util_pct = min(100.0, round((simulated_cpu_busy_ms / max(1e-3, cycle_budget)) * 100.0, 1))
        is_overloaded = util_pct >= 95.0 or any(t.deadline_misses > 0 for t in self.tasks.values())

        total_deadline_misses = sum(t.deadline_misses for t in self.tasks.values())

        stats = {}
        for name, t in self.tasks.items():
            mean_us = (
                round(sum(t.actual_measured_latencies_us) / len(t.actual_measured_latencies_us), 2)
                if t.actual_measured_latencies_us
                else 0.0
            )
            stats[name] = {
                "invocations": t.invocations_total,
                "deadline_misses": t.deadline_misses,
                "actual_mean_latency_us": mean_us,
                "simulated_budget_ms": t.budget_execution_time_ms,
                "frequency_hz": t.frequency_hz,
            }

        return SchedulerExecutionSummary(
            sim_time_ms=round(self.sim_time_ms, 2),
            tasks_executed=len(tasks_to_run),
            total_deadline_misses=total_deadline_misses,
            virtual_cpu_utilization_pct=util_pct,
            is_overloaded=is_overloaded,
            actual_desktop_host_step_ms=round(host_total_ms, 4),
            task_statistics=stats,
        )

    def step_scheduler(
        self,
        time_step_ms: float = 20.0,
        host_callbacks: Optional[Dict[str, Callable[[], Any]]] = None,
    ) -> SchedulerExecutionSummary:
        """Advances simulation clock and executes scheduled periodic tasks."""
        self.sim_time_ms += time_step_ms
        return self.execute_scheduled_tasks(sim_time_ms=self.sim_time_ms, task_handlers=host_callbacks)

    def get_scheduler_summary(self) -> SchedulerExecutionSummary:
        """Returns the most recent execution and utilization summary."""
        return self.execute_scheduled_tasks(sim_time_ms=self.sim_time_ms)

    def reset(self) -> None:
        self.sim_time_ms = 0.0
        self.overload_multiplier = 1.0
        for t in self.tasks.values():
            t.last_run_sim_time_ms = 0.0
            t.invocations_total = 0
            t.deadline_misses = 0
            t.actual_measured_latencies_us.clear()
