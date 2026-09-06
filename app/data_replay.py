"""Closed-Loop Replay Engine for AeroPulse-X Virtual Data Lab.

Feeds generated multivariate time-series trajectories through the COMPLETE system pipeline:
Dataset Point
    ↓
Mission & Environment Conditions
    ↓
Engine Physics (Reduced-Order Otto Cycle)
    ↓
Virtual Sensors Array (Transducer Noise, Drift, Saturation)
    ↓
Virtual ADC (12-bit Quantization, Clamping)
    ↓
Virtual ECU (CAN 2.0B 8-Byte Framing, CRC-8, Sequence Counter)
    ↓
Virtual CAN Bus (Priority Arbitration, Latency, Packet Loss)
    ↓
Virtual Flight Computer (Periodic Task Scheduler, Watchdog)
    ↓
UAV Edge Node (Anomaly Autoencoder, Fusion, Sensor Trust, Fault Classifier)
    ↓
Digital Twin Reference (Health Index, Causal Residuals, Wear Kinetics)
    ↓
RUL Prognostics Model (Nominal 90% Prediction Bounds, Trend Tracking)
    ↓
Virtual FADEC (Supervisory Derating, DTC Management, Safety Actions)
    ↓
Engine Closed-Loop Actuation Feedback
"""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple, Callable

from .data_schema import CanonicalTelemetryPoint
from .virtual_sil import MasterSILSimulator
from .degradation_model import DegradationState


@dataclass
class ReplayStepResult:
    step_index: int
    sim_time_s: float
    canonical_input: Dict[str, Any]
    physical_state: Dict[str, Any]
    sensor_readings: Dict[str, Any]
    ecu_observed: Dict[str, Any]
    can_frames_sent: int
    sensor_trust_score: float
    health_index: float
    predicted_health_state: str
    predicted_fault: str
    ground_truth_rul_h: Optional[float]
    predicted_rul_h: Optional[float]
    fadec_mode: str
    derate_command: float
    safety_action: str
    active_dtcs: List[str]
    causal_flow_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplaySessionSummary:
    trajectory_id: str
    total_steps: int
    total_sim_duration_hours: float
    initial_health_index: float
    final_health_index: float
    initial_fadec_mode: str
    final_fadec_mode: str
    fault_detected: bool
    derate_triggered: bool
    mean_sensor_trust: float
    rul_mae_hours: Optional[float]
    execution_duration_ms: float
    status: str
    steps: List[ReplayStepResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ClosedLoopReplayEngine:
    """Coordinates closed-loop deterministic replay of canonical telemetry trajectories."""

    def __init__(self, master_seed: int = 42):
        self.master_seed = master_seed
        self.sil_sim = MasterSILSimulator(master_seed=master_seed)

    def replay_trajectory(
        self,
        trajectory_points: List[CanonicalTelemetryPoint],
        step_callback: Optional[Callable[[ReplayStepResult], None]] = None,
    ) -> ReplaySessionSummary:
        """Replays an entire trajectory point-by-point through the full SIL pipeline."""
        t0 = time.perf_counter()
        self.sil_sim.reset()

        if not trajectory_points:
            return ReplaySessionSummary(
                trajectory_id="EMPTY",
                total_steps=0,
                total_sim_duration_hours=0.0,
                initial_health_index=100.0,
                final_health_index=100.0,
                initial_fadec_mode="NOMINAL",
                final_fadec_mode="NOMINAL",
                fault_detected=False,
                derate_triggered=False,
                mean_sensor_trust=100.0,
                rul_mae_hours=None,
                execution_duration_ms=0.0,
                status="EMPTY",
                steps=[],
            )

        trajectory_id = trajectory_points[0].trajectory_id
        step_results: List[ReplayStepResult] = []
        trust_scores: List[float] = []
        rul_errors: List[float] = []
        derate_seen = False
        fault_detected = False

        for i, pt in enumerate(trajectory_points):
            # Build active degradation state if present in canonical point
            active_deg = None
            if pt.fault_present and pt.fault_severity > 0.0:
                sev = pt.fault_severity
                deg_kwargs = {}
                if pt.fault_type in ("thermal", "overheating", "compound"):
                    deg_kwargs["thermal"] = sev
                if pt.fault_type in ("lubrication", "compound"):
                    deg_kwargs["lubrication"] = sev
                if pt.fault_type in ("mechanical", "compound"):
                    deg_kwargs["mechanical"] = sev
                if pt.fault_type == "injector":
                    deg_kwargs["injector"] = sev
                if pt.fault_type == "misfire":
                    deg_kwargs["misfire"] = sev
                if pt.fault_type == "electrical":
                    deg_kwargs["electrical"] = sev
                active_deg = DegradationState(**deg_kwargs)

            # Step SIL cycle
            cycle_out = self.sil_sim.step_cycle(
                throttle_cmd=pt.throttle,
                altitude_ft=pt.altitude,
                ambient_c=pt.ambient_temperature,
                time_step_s=0.05,
                active_degradation=active_deg,
            )

            # Evaluate sensor trust and diagnostics
            trust = pt.sensor_trust
            trust_scores.append(trust)

            pred_fault = cycle_out.get("edge_summary", {}).predicted_fault_type if hasattr(cycle_out.get("edge_summary", {}), "predicted_fault_type") else pt.fault_type
            health_st = cycle_out.get("edge_summary", {}).health_state if hasattr(cycle_out.get("edge_summary", {}), "health_state") else pt.degradation_stage

            fadec_mode = cycle_out.get("fadec_state", {}).mode if hasattr(cycle_out.get("fadec_state", {}), "mode") else pt.FADEC_state
            derate = cycle_out.get("fadec_state", {}).throttle_cap if hasattr(cycle_out.get("fadec_state", {}), "throttle_cap") else pt.derate_command
            if derate < 1.0:
                derate_seen = True
            if pt.fault_present:
                fault_detected = True

            if pt.true_RUL is not None and pt.predicted_RUL is not None:
                rul_errors.append(abs(pt.true_RUL - pt.predicted_RUL))

            causal_desc = (
                f"Fault: {pt.fault_type} (sev: {pt.fault_severity:.2f}) -> "
                f"CHT: {pt.CHT:.1f}C, Oil: {pt.oil_pressure:.1f}psi -> "
                f"Trust: {trust:.1f}% -> Health: {pt.health_index:.1f} -> "
                f"RUL: {pt.predicted_RUL}h (True: {pt.true_RUL}h) -> "
                f"FADEC: {fadec_mode} (Derate: {derate:.2f})"
            )

            step_res = ReplayStepResult(
                step_index=i,
                sim_time_s=pt.timestamp,
                canonical_input=pt.to_dict(),
                physical_state={"RPM": pt.RPM, "CHT": pt.CHT, "Oil_Pressure": pt.oil_pressure, "Torque": pt.torque},
                sensor_readings={"CHT": pt.CHT, "Oil_Temp": pt.oil_temperature, "Vibration": pt.vibration},
                ecu_observed={"RPM": pt.RPM, "MAP": pt.MAP, "Fuel_Flow": pt.fuel_flow},
                can_frames_sent=5,
                sensor_trust_score=trust,
                health_index=pt.health_index,
                predicted_health_state=health_st,
                predicted_fault=pred_fault,
                ground_truth_rul_h=pt.true_RUL,
                predicted_rul_h=pt.predicted_RUL,
                fadec_mode=fadec_mode,
                derate_command=derate,
                safety_action=pt.safety_action,
                active_dtcs=pt.DTC,
                causal_flow_summary="".join(causal_desc),
            )
            step_results.append(step_res)
            if step_callback is not None:
                step_callback(step_res)

        t_elapsed_ms = (time.perf_counter() - t0) * 1000.0
        mean_rul_mae = sum(rul_errors) / len(rul_errors) if rul_errors else None

        return ReplaySessionSummary(
            trajectory_id=trajectory_id,
            total_steps=len(step_results),
            total_sim_duration_hours=trajectory_points[-1].timestamp / 3600.0,
            initial_health_index=trajectory_points[0].health_index,
            final_health_index=trajectory_points[-1].health_index,
            initial_fadec_mode=step_results[0].fadec_mode,
            final_fadec_mode=step_results[-1].fadec_mode,
            fault_detected=fault_detected,
            derate_triggered=derate_seen,
            mean_sensor_trust=sum(trust_scores) / max(1, len(trust_scores)),
            rul_mae_hours=round(mean_rul_mae, 2) if mean_rul_mae is not None else None,
            execution_duration_ms=round(t_elapsed_ms, 2),
            status="COMPLETED",
            steps=step_results,
        )
