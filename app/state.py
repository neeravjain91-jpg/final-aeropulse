from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import time

class EngineRunState(str, Enum):
    ENGINE_OFF = "ENGINE_OFF"
    ENGINE_STARTING = "ENGINE_STARTING"
    ENGINE_RUNNING = "ENGINE_RUNNING"
    ENGINE_STOPPING = "ENGINE_STOPPING"

@dataclass
class EngineStateRecord:
    timestamp: float = field(default_factory=time.time)
    data_source: str = "SIMULATED"  # LIVE, SIMULATED, REPLAY, STATIC
    operating_state: str = "CRUISE"
    engine_run_state: str = "ENGINE_OFF"
    telemetry: Dict[str, float] = field(default_factory=dict)
    physics_expected: Dict[str, float] = field(default_factory=dict)
    residuals: Dict[str, float] = field(default_factory=dict)
    z_scores: Dict[str, float] = field(default_factory=dict)
    residual_slopes: Dict[str, float] = field(default_factory=dict)
    sensor_trust_score: float = 100.0
    suspect_sensors: List[str] = field(default_factory=list)
    ml_health_state: str = "Normal"
    ml_probabilities: Dict[str, float] = field(default_factory=dict)
    anomaly_score: float = 0.0
    is_unknown_anomaly: bool = False
    degradation_severity: float = 0.0
    rul_hours: float = 2200.0
    rul_confidence_interval: tuple[float, float] = (1980.0, 2420.0)
    rul_provenance: str = "SIMULATION-DERIVED"
    mission_risk_index: float = 0.0
    advisory_message: str = "System nominal."
    reason_codes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "data_source": self.data_source,
            "operating_state": self.operating_state,
            "engine_run_state": self.engine_run_state,
            "telemetry": self.telemetry,
            "physics_expected": self.physics_expected,
            "residuals": self.residuals,
            "z_scores": self.z_scores,
            "residual_slopes": self.residual_slopes,
            "sensor_trust_score": round(self.sensor_trust_score, 1),
            "suspect_sensors": self.suspect_sensors,
            "ml_health_state": self.ml_health_state,
            "ml_probabilities": self.ml_probabilities,
            "anomaly_score": round(self.anomaly_score, 4),
            "is_unknown_anomaly": self.is_unknown_anomaly,
            "degradation_severity": round(self.degradation_severity, 3),
            "rul_hours": round(self.rul_hours, 1),
            "rul_confidence_interval": [round(self.rul_confidence_interval[0], 1), round(self.rul_confidence_interval[1], 1)],
            "rul_provenance": self.rul_provenance,
            "mission_risk_index": round(self.mission_risk_index, 1),
            "advisory_message": self.advisory_message,
            "reason_codes": self.reason_codes,
        }

    @classmethod
    def from_analysis(cls, analysis: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> "EngineStateRecord":
        context = context or {}
        twin = analysis.get("twin", {})
        rul = analysis.get("rul", {})
        sensor_health = analysis.get("sensor_health", {})
        risk = analysis.get("mission_risk", {})
        telemetry = analysis.get("telemetry", {})

        return cls(
            timestamp=time.time(),
            data_source=str(context.get("data_source", "SIMULATED")),
            operating_state=str(twin.get("operating_state", telemetry.get("Operating_State", "CRUISE"))),
            engine_run_state=str(telemetry.get("engine_run_state", context.get("engine_run_state", "ENGINE_RUNNING" if telemetry.get("Engine_RPM", 0) > 0 else "ENGINE_OFF"))),
            telemetry=telemetry,
            physics_expected=twin.get("physics_expected", {}),
            residuals=twin.get("residuals", {}),
            z_scores=twin.get("z_scores", {}),
            residual_slopes=twin.get("residual_slopes", {}),
            sensor_trust_score=float(sensor_health.get("overall_trust_score", 100.0)),
            suspect_sensors=[c["name"] for c in sensor_health.get("channels", []) if c.get("status") in ["SUSPECT", "FAILED"]],
            ml_health_state=str(analysis.get("ml_health_state", analysis.get("health_state", "Normal"))),
            ml_probabilities=analysis.get("health_probabilities", {}),
            anomaly_score=float(analysis.get("anomaly_score", 0.0)),
            is_unknown_anomaly=bool(analysis.get("anomaly_flag", False)),
            degradation_severity=float(analysis.get("degradation_severity", telemetry.get("Degradation_Severity", 0.0)) or 0.0),
            rul_hours=float(rul.get("rul_hours", 2200.0) or 0.0),
            rul_confidence_interval=(float(rul.get("rul_lower_hours", 0.0) or 0.0), float(rul.get("rul_upper_hours", 0.0) or 0.0)),
            rul_provenance=str(rul.get("method", "SIMULATION-DERIVED")),
            mission_risk_index=float(risk.get("score", analysis.get("risk_score", 0.0))),
            advisory_message=str(analysis.get("maintenance_advisory", "System nominal.")),
            reason_codes=[f["name"] for f in analysis.get("fault_candidates", [])],
        )
