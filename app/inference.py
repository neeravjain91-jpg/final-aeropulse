from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import numpy as np
import pandas as pd
import torch

from .advisory import fault_advisory, maintenance_advice
from .anomaly_autoencoder import TemporalTCNAutoencoder
from .config import MODEL_DIR
from .digital_twin import PARAMS, ReferenceTwin
from .fusion import FusionEngine, DiagnosticEvidence
from .rul_service import RULService
from .sensor_health import assess_sensor_health
from .tcn_model import (
    CLASSES_4,
    CLASS_TO_IDX,
    IDX_TO_CLASS,
    PhysicsResidualTCN,
    RESIDUAL_CHANNELS_13,
    TemporalSequenceBuffer,
)

HEALTH_ORDER = {
    "Normal": 0,
    "Watch": 1,
    "Warning": 2,
    "Critical": 3,
}


class AeroTwinAI:
    def __init__(self):
        # 1. Point Machine Learning Models (Authoritative Fallback)
        self.health = joblib.load(
            MODEL_DIR / "aces_health.joblib"
        )
        self.anomaly = joblib.load(
            MODEL_DIR / "aces_anomaly.joblib"
        )

        # 2. Physics Reference Twin & RUL Service
        self.twin = ReferenceTwin()
        self.rul = RULService()

        # 3. Hybrid Diagnostic Fusion Engine (0.70 HGB + 0.30 TCN)
        self.fusion = FusionEngine(w_hgb=0.70, w_tcn=0.30)

        # 4. Temporal Sequence Buffer (13 channels, W=30s, dt=1.0s)
        self.tcn_buffer = TemporalSequenceBuffer(window_size=30, num_channels=13)

        # 5. Temporal 1D TCN Diagnostic Model
        self.tcn: PhysicsResidualTCN | None = None
        pt_path = MODEL_DIR / "aces_tcn_residual.pt"
        if pt_path.exists():
            try:
                self.tcn = PhysicsResidualTCN(num_inputs=13, num_classes=4, num_channels=[32, 32, 32])
                state_dict = torch.load(pt_path, map_location="cpu")
                self.tcn.load_state_dict(state_dict)
                self.tcn.eval()
            except Exception:
                self.tcn = None

        # 6. Temporal TCN Autoencoder for Unknown Anomaly Detection
        self.autoencoder: TemporalTCNAutoencoder | None = None
        ae_path = MODEL_DIR / "aces_tcn_autoencoder.pt"
        if ae_path.exists():
            try:
                self.autoencoder = TemporalTCNAutoencoder(in_channels=13, latent_channels=8, hidden_channels=32)
                ae_state = torch.load(ae_path, map_location="cpu")
                self.autoencoder.load_state_dict(ae_state)
                self.autoencoder.eval()
            except Exception:
                self.autoencoder = None

    def analyze(
        self,
        telemetry: dict,
        context: dict | None = None,
    ) -> Dict[str, Any]:
        columns = PARAMS + ["Operating_State"]

        missing = [column for column in columns if column not in telemetry]
        if missing:
            raise ValueError(f"Missing telemetry fields: {missing}")

        # ---------------------------------------------------------
        # 1. POINT ML HEALTH CLASSIFICATION (Model A: HGB Baseline)
        # ---------------------------------------------------------
        health_frame = pd.DataFrame([{column: telemetry[column] for column in columns}])
        hgb_raw_probs = self.health.predict_proba(health_frame)[0]
        hgb_classes = self.health.classes_

        hgb_probabilities = {str(label): float(val) for label, val in zip(hgb_classes, hgb_raw_probs)}
        raw_prediction = str(hgb_classes[int(np.argmax(hgb_raw_probs))])

        if hgb_probabilities.get("Critical", 0.0) >= 0.25:
            hgb_prediction = "Critical"
        elif hgb_probabilities.get("Warning", 0.0) >= 0.35 and raw_prediction == "Watch":
            hgb_prediction = "Warning"
        else:
            hgb_prediction = raw_prediction

        # ---------------------------------------------------------
        # 2. POINT ANOMALY DETECTION (Model D: Isolation Forest)
        # ---------------------------------------------------------
        anomaly_frame = pd.DataFrame([{parameter: telemetry[parameter] for parameter in PARAMS}])
        iso_anomaly_score = float(-self.anomaly.decision_function(anomaly_frame)[0])

        # ---------------------------------------------------------
        # 3. FIRST-PRINCIPLES DIGITAL TWIN (Physics Residuals)
        # ---------------------------------------------------------
        twin = self.twin.compare(telemetry, context=context)

        # ---------------------------------------------------------
        # 4. SENSOR HEALTH & INTEGRITY ASSESSMENT
        # ---------------------------------------------------------
        sensor_health = assess_sensor_health(telemetry, twin)

        # ---------------------------------------------------------
        # 5. TEMPORAL DL CLASSIFIER & AUTOENCODER
        # ---------------------------------------------------------
        state = str(telemetry.get("Operating_State", "CRUISE"))
        exp_dict = twin.get("expected", {})
        ref_std_dict = self.twin.stats.get(state, self.twin.stats["_GLOBAL_"])

        # Construct 13-channel physics-normalized residual vector
        res_vec = []
        for ch in RESIDUAL_CHANNELS_13:
            obs = float(telemetry.get(ch, exp_dict.get(ch, 0.0)))
            exp = float(exp_dict.get(ch, 0.0))
            std = max(float(ref_std_dict.get(ch, {}).get("std", 1.0)), 1e-4)
            res_vec.append((obs - exp) / std)

        # Rolling causal sequence buffer push
        gps_t = telemetry.get("GPS_Time")
        window_matrix = self.tcn_buffer.push(res_vec, timestamp=gps_t)

        tcn_probabilities: Dict[str, float] = dict(hgb_probabilities)
        tcn_prediction = hgb_prediction

        if self.tcn is not None:
            try:
                tcn_pred_class, tcn_prob_dict = self.tcn.predict_window_np(window_matrix)
                tcn_probabilities = tcn_prob_dict
                tcn_prediction = tcn_pred_class
            except Exception:
                pass

        # Temporal TCN Autoencoder Evaluation
        tcn_recon_error = 0.0
        tcn_anomaly_score = 0.0
        tcn_is_anomaly = False
        tcn_attributions = []

        if self.autoencoder is not None:
            try:
                ae_res = self.autoencoder.detect_anomaly_window(window_matrix)
                tcn_recon_error = ae_res["reconstruction_error"]
                tcn_anomaly_score = ae_res["anomaly_score"]
                tcn_is_anomaly = ae_res["is_unknown_anomaly"]
                tcn_attributions = ae_res["channel_attributions"]
            except Exception:
                pass

        # Combined Anomaly Flag
        anomaly_flag = (
            (iso_anomaly_score > 0.005 or tcn_is_anomaly)
            and float(twin["residual_rms"]) >= 2.0
        )

        # ---------------------------------------------------------
        # 6. OPTIMIZED ZERO-LEAKAGE HYBRID FUSION
        # ---------------------------------------------------------
        diagnostic_evidence = self.fusion.fuse(
            hgb_probs=hgb_probabilities,
            tcn_probs=tcn_probabilities,
            anomaly_loss=max(iso_anomaly_score, tcn_anomaly_score * 0.1),
            is_unknown_anomaly=anomaly_flag,
            twin_assessment=twin,
            sensor_health=sensor_health,
        )

        # ---------------------------------------------------------
        # 7. FAULT ADVISORY & EVIDENCE ATTRIBUTION
        # ---------------------------------------------------------
        findings = fault_advisory(telemetry, twin, sensor_health)

        # ---------------------------------------------------------
        # 8. BASE HEALTH INDEX CALCULATION
        # ---------------------------------------------------------
        base_health_index = (
            100.0
            - HEALTH_ORDER.get(diagnostic_evidence.final_diagnosis, 1) * 18.0
            - min(float(twin["residual_rms"]), 12.0) * 4.0
            - max(0.0, 100.0 - sensor_health["overall_trust_score"]) * 0.10
        )
        base_health_index = max(0.0, min(100.0, base_health_index))

        # Degradation Penalty
        degradation_severity = max(0.0, min(1.0, float(telemetry.get("Degradation_Severity", 0.0))))
        degradation_penalty = degradation_severity * 45.0
        health_index_value = max(0.0, min(100.0, base_health_index - degradation_penalty))

        # Fused Health State Thresholds
        if health_index_value >= 85:
            fused_state = "Normal"
        elif health_index_value >= 65:
            fused_state = "Watch"
        elif health_index_value >= 40:
            fused_state = "Warning"
        else:
            fused_state = "Critical"

        confidence = float(diagnostic_evidence.confidence_score)

        # ---------------------------------------------------------
        # 9. RUL PREDICTION
        # ---------------------------------------------------------
        rul = self.rul.predict(telemetry, context=context)

        # ---------------------------------------------------------
        # 10. EXPLAINABILITY & UNCERTAINTY
        # ---------------------------------------------------------
        fused_probs = diagnostic_evidence.hgb_probs  # or fused p
        sorted_probs = sorted(hgb_probabilities.values(), reverse=True)
        top1 = sorted_probs[0] if len(sorted_probs) > 0 else 1.0
        top2 = sorted_probs[1] if len(sorted_probs) > 1 else 0.0
        margin = top1 - top2

        if top1 >= 0.80 and margin >= 0.40:
            confidence_level = "HIGH"
        elif top1 >= 0.60:
            confidence_level = "MODERATE"
        else:
            confidence_level = "AMBIGUOUS"

        deviations = twin.get("deviations", {})
        top_deviations = sorted(
            [
                {
                    "channel": channel,
                    "z_score": round(info.get("z_score", 0.0), 2),
                    "measured": round(info.get("measured", 0.0), 2),
                    "expected": round(info.get("expected", 0.0), 2),
                    "delta": round(info.get("delta", 0.0), 2),
                }
                for channel, info in deviations.items()
                if abs(info.get("z_score", 0.0)) >= 1.5
            ],
            key=lambda x: abs(x["z_score"]),
            reverse=True,
        )[:5]

        # ---------------------------------------------------------
        # 11. RESPONSE PAYLOAD
        # ---------------------------------------------------------
        return {
            "health_state": fused_state,
            "ml_health_state": hgb_prediction,
            "tcn_health_state": tcn_prediction,
            "health_confidence": round(confidence, 4),
            "health_probabilities": hgb_probabilities,
            "tcn_probabilities": tcn_probabilities,
            "diagnostic_evidence": diagnostic_evidence.as_dict(),
            "health_index": round(health_index_value, 1),
            "base_health_index": round(base_health_index, 1),
            "degradation_severity": round(degradation_severity, 4),
            "degradation_penalty": round(degradation_penalty, 2),
            "anomaly_score": round(iso_anomaly_score, 4),
            "tcn_anomaly_score": round(tcn_anomaly_score, 4),
            "tcn_reconstruction_error": round(tcn_recon_error, 5),
            "tcn_channel_attributions": tcn_attributions,
            "anomaly_flag": anomaly_flag,
            "twin": twin,
            "sensor_health": sensor_health,
            "rul": rul,
            "fault_candidates": [
                {
                    "name": name,
                    "severity": severity,
                    "evidence": evidence,
                }
                for name, severity, evidence in findings
            ],
            "maintenance_advisory": maintenance_advice(findings, sensor_health),
            "explainability": {
                "dominant_deviations": top_deviations,
                "diagnostic_summary": (
                    f"State '{fused_state}' driven by Hybrid AI Fusion ({confidence_level} confidence, top prob {round(top1*100, 1)}%) "
                    + (f"with significant residual deviations on: {', '.join([d['channel'] for d in top_deviations])}." if top_deviations else "with nominal physics residuals.")
                ),
            },
            "uncertainty": {
                "confidence_level": confidence_level,
                "probability_margin": round(margin, 4),
                "top_probability": round(top1, 4),
            },
            "telemetry": telemetry,
            "disclaimer": (
                "Prototype decision-support output; not an airworthiness or flight-safety determination."
            ),
        }
