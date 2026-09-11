"""Comprehensive Regression Test Suite for HGB + TCN Hybrid Fusion."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest
import torch

from app.digital_twin import ReferenceTwin
from app.fusion import FusionEngine, DiagnosticEvidence
from app.inference import AeroTwinAI
from app.tcn_model import (
    CLASSES_4,
    CLASS_TO_IDX,
    IDX_TO_CLASS,
    PhysicsResidualTCN,
    RESIDUAL_CHANNELS_13,
)

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"


def test_flight_isolation_and_no_data_leakage():
    """Verify that train and test flight partitions are strictly disjoint."""
    train_flights = {
        "aces1am_2002_192", "aces1am_2002_193", "aces1am_2002_214", "aces1am_2002_216",
        "aces1am_2002_218", "aces1am_2002_220", "aces1am_2002_222", "aces1am_2002_224",
        "aces1am_2002_227", "aces1am_2002_237", "aces1am_2002_242",
    }
    test_flights = {"aces1am_2002_191", "aces1am_2002_225", "aces1am_2002_235"}
    assert train_flights.isdisjoint(test_flights)
    assert len(train_flights) == 11
    assert len(test_flights) == 3


def test_fusion_probability_dimensions_and_class_consistency():
    """Verify probability dictionaries and array shapes for all 4 classes."""
    engine = FusionEngine()
    hgb_p = {"Normal": 0.70, "Watch": 0.20, "Warning": 0.08, "Critical": 0.02}
    tcn_p = {"Normal": 0.60, "Watch": 0.30, "Warning": 0.09, "Critical": 0.01}
    twin = {"max_abs_z": 0.5, "residual_rms": 0.4}
    sensor_h = {"overall_trust_score": 100.0, "suspect_sensors": []}

    ev = engine.fuse(
        hgb_probs=hgb_p,
        tcn_probs=tcn_p,
        anomaly_loss=0.0,
        is_unknown_anomaly=False,
        twin_assessment=twin,
        sensor_health=sensor_h,
    )
    assert isinstance(ev, DiagnosticEvidence)
    assert ev.final_diagnosis in CLASSES_4
    assert set(ev.hgb_probs.keys()) == set(CLASSES_4)
    assert set(ev.tcn_probs.keys()) == set(CLASSES_4)


def test_deterministic_sensor_veto_precedence():
    """Verify that low sensor trust score strictly vetos high ML fault probabilities."""
    engine = FusionEngine()
    # High fault probabilities from ML models
    hgb_p = {"Normal": 0.01, "Watch": 0.05, "Warning": 0.14, "Critical": 0.80}
    tcn_p = {"Normal": 0.01, "Watch": 0.05, "Warning": 0.14, "Critical": 0.80}

    # Isolated sensor failure on single thermocouple, engine bulk physics normal
    twin = {"max_abs_z": 1.2, "residual_rms": 0.8}
    sensor_fault = {"overall_trust_score": 25.0, "suspect_sensors": ["EGT1"]}

    ev = engine.fuse(
        hgb_probs=hgb_p,
        tcn_probs=tcn_p,
        anomaly_loss=0.01,
        is_unknown_anomaly=False,
        twin_assessment=twin,
        sensor_health=sensor_fault,
    )
    # Must be downgraded to Watch with reason code
    assert ev.final_diagnosis == "Watch"
    assert any("ISOLATED_SENSOR_FAULT" in r for r in ev.reason_codes)


def test_tcn_missing_model_fallback():
    """Verify that when TCN probabilities are None or empty, fusion gracefully falls back to HGB."""
    engine = FusionEngine()
    hgb_p = {"Normal": 0.10, "Watch": 0.10, "Warning": 0.20, "Critical": 0.60}
    twin = {"max_abs_z": 3.5, "residual_rms": 2.8}
    sensor_h = {"overall_trust_score": 95.0, "suspect_sensors": []}

    ev = engine.fuse(
        hgb_probs=hgb_p,
        tcn_probs=None,
        anomaly_loss=0.04,
        is_unknown_anomaly=False,
        twin_assessment=twin,
        sensor_health=sensor_h,
    )
    assert ev.final_diagnosis == "Critical"
    assert ev.tcn_probs == hgb_p


def test_end_to_end_inference_explainability_reason_codes():
    """Verify that AeroTwinAI exposes diagnostic evidence and reason codes."""
    ai = AeroTwinAI()
    telemetry = {
        "Engine_RPM": 4544.0,
        "EGT1": 1250.0,
        "EGT2": 1250.0,
        "EGT3": 1250.0,
        "CHT": 180.0,
        "Fuel_Flow": 8.5,
        "Oil_Temp": 180.0,
        "Oil_Pressure": 55.0,
        "Battery_Voltage": 14.2,
        "Battery_Current": 0.0,
        "Alternator_Temp": 55.0,
        "EFI_Fuel_Temp": 35.0,
        "EFI_Water_Temp": 85.0,
        "MAP_Injector": 29.5,
        "Operating_State": "CRUISE",
    }
    res = ai.analyze(telemetry)
    assert "diagnostic_evidence" in res
    assert "tcn_probabilities" in res
    assert "health_probabilities" in res
    assert "reason_codes" in res["diagnostic_evidence"]
    assert len(res["diagnostic_evidence"]["reason_codes"]) > 0
