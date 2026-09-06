import pytest
from app.fusion import FusionEngine, DiagnosticEvidence

def test_fusion_engine_healthy_consensus():
    fe = FusionEngine()
    hgb_p = {"Normal": 0.96, "Watch": 0.03, "Warning": 0.01, "Critical": 0.0}
    tcn_p = {"Normal": 0.94, "Degraded": 0.05, "Critical": 0.01}
    twin = {"max_abs_z": 0.8, "residual_rms": 0.5}
    sh = {"overall_trust_score": 100.0, "suspect_sensors": []}
    
    ev = fe.fuse(hgb_p, tcn_p, anomaly_loss=0.012, is_unknown_anomaly=False, twin_assessment=twin, sensor_health=sh)
    assert ev.final_diagnosis == "Normal"
    assert ev.confidence_score > 0.90
    assert "NOMINAL" in ev.reason_codes[0]

def test_fusion_engine_sensor_veto():
    fe = FusionEngine()
    hgb_p = {"Normal": 0.20, "Watch": 0.30, "Warning": 0.50, "Critical": 0.0}
    tcn_p = {"Normal": 0.30, "Degraded": 0.70, "Critical": 0.0}
    twin = {"max_abs_z": 4.5, "residual_rms": 1.2}
    sh = {"overall_trust_score": 30.0, "suspect_sensors": ["CHT"]}
    
    ev = fe.fuse(hgb_p, tcn_p, anomaly_loss=0.015, is_unknown_anomaly=False, twin_assessment=twin, sensor_health=sh)
    assert ev.final_diagnosis == "Watch"
    assert "ISOLATED_SENSOR_FAULT" in ev.reason_codes[0]

def test_fusion_engine_unknown_anomaly_veto():
    fe = FusionEngine()
    hgb_p = {"Normal": 0.70, "Watch": 0.20, "Warning": 0.10, "Critical": 0.0}
    tcn_p = {"Normal": 0.80, "Degraded": 0.20, "Critical": 0.0}
    twin = {"max_abs_z": 3.8, "residual_rms": 3.1}
    sh = {"overall_trust_score": 100.0, "suspect_sensors": []}
    
    ev = fe.fuse(hgb_p, tcn_p, anomaly_loss=0.85, is_unknown_anomaly=True, twin_assessment=twin, sensor_health=sh)
    assert ev.final_diagnosis == "Critical"
    assert "UNKNOWN_ANOMALY_INVESTIGATE" in ev.reason_codes[0]
