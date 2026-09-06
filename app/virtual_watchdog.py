"""Virtual Hardware Watchdog & System Supervisor.

Monitors subsystem heartbeats, detects process stalls / CAN silence / deadline misses,
and executes deterministic autonomic recovery actions.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class WatchdogRecoveryAction(str, Enum):
    NO_ACTION = "NO_ACTION"
    RESTART_VIRTUAL_TASK = "RESTART_VIRTUAL_TASK"
    RESET_VIRTUAL_SUBSYSTEM = "RESET_VIRTUAL_SUBSYSTEM"
    ENTER_DEGRADED_MODE = "ENTER_DEGRADED_MODE"
    PRESERVE_LAST_SAFE_STATE = "PRESERVE_LAST_SAFE_STATE"


@dataclass
class WatchdogHeartbeatChannel:
    name: str
    timeout_limit_ms: float
    last_ping_ms: float = 0.0
    consecutive_timeouts: int = 0
    consecutive_errors: int = 0
    is_active: bool = True


@dataclass
class WatchdogStatus:
    timestamp_ms: float
    all_healthy: bool
    triggered_channels: List[str]
    active_recovery_action: WatchdogRecoveryAction
    recovery_events_total: int
    diagnostics_log: List[str]


class VirtualWatchdog:
    """
    Simulates an airborne hardware watchdog microcontroller supervising
    the Flight Computer, Virtual ECU, CAN bus, and Edge analytics tasks.
    """

    def __init__(self):
        self.channels: Dict[str, WatchdogHeartbeatChannel] = {
            "ECU_HEARTBEAT": WatchdogHeartbeatChannel("ECU_HEARTBEAT", timeout_limit_ms=100.0),
            "CAN_BUS_ACTIVITY": WatchdogHeartbeatChannel("CAN_BUS_ACTIVITY", timeout_limit_ms=50.0),
            "EDGE_NODE_HEARTBEAT": WatchdogHeartbeatChannel("EDGE_NODE_HEARTBEAT", timeout_limit_ms=150.0),
            "TELEMETRY_STREAM": WatchdogHeartbeatChannel("TELEMETRY_STREAM", timeout_limit_ms=300.0),
        }
        self.recovery_events_total: int = 0
        self.diagnostics_log: List[str] = []
        self.last_safe_state: Dict[str, Any] = {}
        self.sim_time_ms: float = 0.0

    def ping(self, channel_name: str, sim_time_ms: Optional[float] = None) -> None:
        """Called by a virtual subsystem to kick/refresh its watchdog timer."""
        now_ms = sim_time_ms if sim_time_ms is not None else self.sim_time_ms
        if channel_name in self.channels:
            ch = self.channels[channel_name]
            ch.last_ping_ms = now_ms
            ch.consecutive_timeouts = 0
            ch.consecutive_errors = 0

    def record_error(self, channel_name: str) -> None:
        """Record a frame or execution error on a monitored channel."""
        if channel_name in self.channels:
            self.channels[channel_name].consecutive_errors += 1

    def store_safe_state(self, state: Dict[str, Any]) -> None:
        """Caches the latest validated safe state for fallback recovery."""
        self.last_safe_state = dict(state)

    def evaluate(self, sim_time_ms: float) -> WatchdogStatus:
        """
        Evaluates watchdog channels against timeout limits and triggers appropriate recovery.
        """
        self.sim_time_ms = sim_time_ms
        triggered: List[str] = []
        recovery_action = WatchdogRecoveryAction.NO_ACTION

        for name, ch in self.channels.items():
            if not ch.is_active:
                continue

            elapsed_ms = self.sim_time_ms - ch.last_ping_ms
            if elapsed_ms > ch.timeout_limit_ms:
                ch.consecutive_timeouts += 1
                triggered.append(f"{name}_TIMEOUT_{elapsed_ms:.1f}ms")
            elif ch.consecutive_errors >= 5:
                triggered.append(f"{name}_CONSECUTIVE_ERRORS_{ch.consecutive_errors}")

        all_healthy = len(triggered) == 0

        if not all_healthy:
            self.recovery_events_total += 1
            # Determine appropriate recovery escalation
            max_timeouts = max(ch.consecutive_timeouts for ch in self.channels.values())
            if max_timeouts >= 5:
                recovery_action = WatchdogRecoveryAction.PRESERVE_LAST_SAFE_STATE
                msg = f"Watchdog escalated to PRESERVE_LAST_SAFE_STATE due to {triggered}"
            elif max_timeouts >= 3:
                recovery_action = WatchdogRecoveryAction.ENTER_DEGRADED_MODE
                msg = f"Watchdog escalated to ENTER_DEGRADED_MODE due to {triggered}"
            elif max_timeouts >= 2:
                recovery_action = WatchdogRecoveryAction.RESET_VIRTUAL_SUBSYSTEM
                msg = f"Watchdog executing RESET_VIRTUAL_SUBSYSTEM due to {triggered}"
            else:
                recovery_action = WatchdogRecoveryAction.RESTART_VIRTUAL_TASK
                msg = f"Watchdog executing RESTART_VIRTUAL_TASK due to {triggered}"

            self.diagnostics_log.append(msg)
            if len(self.diagnostics_log) > 50:
                self.diagnostics_log.pop(0)

        return WatchdogStatus(
            timestamp_ms=round(self.sim_time_ms, 2),
            all_healthy=all_healthy,
            triggered_channels=triggered,
            active_recovery_action=recovery_action,
            recovery_events_total=self.recovery_events_total,
            diagnostics_log=list(self.diagnostics_log[-10:]),
        )

    def reset(self) -> None:
        self.sim_time_ms = 0.0
        self.recovery_events_total = 0
        self.diagnostics_log.clear()
        for ch in self.channels.values():
            ch.last_ping_ms = 0.0
            ch.consecutive_timeouts = 0
            ch.consecutive_errors = 0
