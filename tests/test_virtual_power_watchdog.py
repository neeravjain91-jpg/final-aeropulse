"""Automated Unit & Integration Tests for Virtual Power Distribution and Watchdog Supervisor."""
from __future__ import annotations

import pytest
from app.virtual_power import VirtualPowerSubsystem, PowerBusState
from app.virtual_watchdog import (
    VirtualWatchdog,
    WatchdogRecoveryAction,
    WatchdogStatus,
)


def test_virtual_power_nominal_voltage():
    """Verifies that power subsystem supplies nominal ~28.0V DC bus voltage at cruise RPM."""
    power = VirtualPowerSubsystem()
    state = power.step_power(engine_rpm=3000.0, load_current_a=15.0, time_step_s=1.0)

    assert state.bus_voltage_v > 26.0
    assert state.bus_voltage_v < 29.5
    assert state.battery_charge_pct > 90.0


def test_virtual_power_alternator_degradation():
    """Verifies that alternator failure leads to battery discharge and bus undervoltage."""
    power = VirtualPowerSubsystem()
    power.inject_alternator_failure(severity=1.0)  # Full alternator failure

    # Run for 100 seconds to discharge battery
    for _ in range(100):
        state = power.step_power(engine_rpm=3000.0, load_current_a=25.0, time_step_s=1.0)

    assert state.bus_voltage_v < 26.0
    assert state.battery_charge_pct < 100.0


def test_virtual_power_brownout_injection():
    """Verifies that transient voltage sag drops voltage below critical threshold."""
    power = VirtualPowerSubsystem()
    power.inject_transient_sag(voltage_drop_v=10.0, duration_s=2.0)

    state = power.step_power(engine_rpm=3000.0, load_current_a=10.0, time_step_s=0.5)
    assert state.bus_voltage_v <= 20.0
    assert state.is_brownout is True


def test_virtual_watchdog_heartbeat_nominal():
    """Verifies that healthy tasks reporting regular heartbeats keep watchdog state healthy."""
    watchdog = VirtualWatchdog()

    # Feed heartbeat on all channels at 20ms intervals
    for t_ms in range(0, 80, 20):
        for ch in watchdog.channels:
            watchdog.ping(ch, sim_time_ms=float(t_ms))
        status = watchdog.evaluate(sim_time_ms=float(t_ms))
        assert status.all_healthy is True
        assert status.active_recovery_action == WatchdogRecoveryAction.NO_ACTION


def test_virtual_watchdog_timeout_and_tiered_recovery():
    """Verifies that missing heartbeats escalate through recovery actions."""
    watchdog = VirtualWatchdog()

    # Ping at t=0
    for ch in watchdog.channels:
        watchdog.ping(ch, sim_time_ms=0.0)

    # Advance time beyond timeout (t=120ms) without pinging ECU
    status1 = watchdog.evaluate(sim_time_ms=120.0)
    assert status1.all_healthy is False
    assert status1.active_recovery_action in [
        WatchdogRecoveryAction.RESTART_VIRTUAL_TASK,
        WatchdogRecoveryAction.RESET_VIRTUAL_SUBSYSTEM,
    ]

    # Advance further without pinging to trigger degraded mode or safe state
    for t_ms in range(200, 600, 50):
        status_deg = watchdog.evaluate(sim_time_ms=float(t_ms))

    assert status_deg.active_recovery_action in [
        WatchdogRecoveryAction.ENTER_DEGRADED_MODE,
        WatchdogRecoveryAction.PRESERVE_LAST_SAFE_STATE,
    ]
