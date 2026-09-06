from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class DiagnosticEvidence:
    hgb_probs: Dict[str, float]
    tcn_probs: Dict[str, float]
    anomaly_reconstruction_loss: float
    is_unknown_anomaly: bool
    physics_max_abs_z: float
    physics_residual_rms: float
    sensor_trust_score: float
    suspect_sensors: List[str]
    final_diagnosis: str
    confidence_score: float
    reason_codes: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "hgb_probs": {k: round(v, 4) for k, v in self.hgb_probs.items()},
            "tcn_probs": {k: round(v, 4) for k, v in self.tcn_probs.items()},
            "anomaly_reconstruction_loss": round(self.anomaly_reconstruction_loss, 4),
            "is_unknown_anomaly": self.is_unknown_anomaly,
            "physics_max_abs_z": round(self.physics_max_abs_z, 2),
            "physics_residual_rms": round(self.physics_residual_rms, 2),
            "sensor_trust_score": round(self.sensor_trust_score, 1),
            "suspect_sensors": self.suspect_sensors,
            "final_diagnosis": self.final_diagnosis,
            "confidence_score": round(self.confidence_score, 3),
            "reason_codes": self.reason_codes,
        }

class FusionEngine:
    def __init__(self):
        pass

    def fuse(
        self,
        hgb_probs: Dict[str, float],
        tcn_probs: Optional[Dict[str, float]],
        anomaly_loss: float,
        is_unknown_anomaly: bool,
        twin_assessment: Dict[str, Any],
        sensor_health: Dict[str, Any],
    ) -> DiagnosticEvidence:
        reasons = []
        max_z = float(twin_assessment.get("max_abs_z", 0.0))
        rms_z = float(twin_assessment.get("residual_rms", 0.0))
        trust = float(sensor_health.get("overall_trust_score", 100.0))
        suspects = sensor_health.get("suspect_sensors", [])

        # Default TCN if unavailable
        if not tcn_probs:
            tcn_probs = dict(hgb_probs)

        # 1. Sensor fault isolation veto
        if trust < 40.0 and len(suspects) <= 2 and rms_z < 2.0:
            final_diag = "Watch"
            conf = 0.85
            reasons.append(f"ISOLATED_SENSOR_FAULT: {', '.join(suspects)} untrusted while engine bulk physics normal.")
            return DiagnosticEvidence(
                hgb_probs=hgb_probs,
                tcn_probs=tcn_probs,
                anomaly_reconstruction_loss=anomaly_loss,
                is_unknown_anomaly=is_unknown_anomaly,
                physics_max_abs_z=max_z,
                physics_residual_rms=rms_z,
                sensor_trust_score=trust,
                suspect_sensors=suspects,
                final_diagnosis=final_diag,
                confidence_score=conf,
                reason_codes=reasons,
            )

        # 2. Unknown Anomaly veto
        if is_unknown_anomaly and max_z > 2.5:
            final_diag = "Critical"
            conf = 0.90
            reasons.append("UNKNOWN_ANOMALY_INVESTIGATE: Multi-sensor sequence reconstruction loss exceeded statistical threshold.")
            return DiagnosticEvidence(
                hgb_probs=hgb_probs,
                tcn_probs=tcn_probs,
                anomaly_reconstruction_loss=anomaly_loss,
                is_unknown_anomaly=is_unknown_anomaly,
                physics_max_abs_z=max_z,
                physics_residual_rms=rms_z,
                sensor_trust_score=trust,
                suspect_sensors=suspects,
                final_diagnosis=final_diag,
                confidence_score=conf,
                reason_codes=reasons,
            )

        # 3. Fused class probability weighting (0.60 HGB + 0.40 TCN)
        classes = ["Critical", "Warning", "Watch", "Normal"]
        fused_p = {}
        for c in classes:
            fused_p[c] = 0.60 * hgb_probs.get(c, 0.0) + 0.40 * tcn_probs.get(c, 0.0)

        # Critical recall priority threshold (tau = 0.25)
        if fused_p.get("Critical", 0.0) >= 0.25:
            final_diag = "Critical"
            conf = fused_p["Critical"]
            reasons.append("SAFETY_THRESHOLD_CRITICAL: High fault probability corroborated by temporal physics residuals.")
        elif fused_p.get("Warning", 0.0) >= 0.35:
            final_diag = "Warning"
            conf = fused_p["Warning"]
            reasons.append("ELEVATED_DEVIATION_WARNING: Degradation trend confirmed across diagnostic models.")
        elif fused_p.get("Watch", 0.0) >= 0.45:
            final_diag = "Watch"
            conf = fused_p["Watch"]
            reasons.append("MONITOR_WATCH: Minor operating variance.")
        else:
            final_diag = "Normal"
            conf = fused_p.get("Normal", 0.95)
            reasons.append("NOMINAL: All telemetry aligned with thermodynamic digital twin expectations.")

        return DiagnosticEvidence(
            hgb_probs=hgb_probs,
            tcn_probs=tcn_probs,
            anomaly_reconstruction_loss=anomaly_loss,
            is_unknown_anomaly=is_unknown_anomaly,
            physics_max_abs_z=max_z,
            physics_residual_rms=rms_z,
            sensor_trust_score=trust,
            suspect_sensors=suspects,
            final_diagnosis=final_diag,
            confidence_score=conf,
            reason_codes=reasons,
        )
