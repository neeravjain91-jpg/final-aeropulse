"""Comprehensive Test Suite for Physics-Normalized Residual 1D TCN."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest
import torch

from app.digital_twin import ReferenceTwin
from app.fusion import FusionEngine
from app.inference import AeroTwinAI
from app.tcn_model import (
    CLASSES_4,
    CLASS_TO_IDX,
    IDX_TO_CLASS,
    PhysicsResidualTCN,
    RESIDUAL_CHANNELS_13,
    TemporalBlock,
    TemporalSequenceBuffer,
    extract_continuous_residual_windows,
)

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"


def test_channel_specification_excludes_battery_current():
    """Verify strictly 13 channels and that Battery_Current is excluded."""
    assert len(RESIDUAL_CHANNELS_13) == 13
    assert "Battery_Current" not in RESIDUAL_CHANNELS_13
    expected_channels = [
        "Engine_RPM", "EGT1", "EGT2", "EGT3", "CHT", "Fuel_Flow",
        "Oil_Temp", "Oil_Pressure", "Battery_Voltage", "Alternator_Temp",
        "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
    ]
    assert RESIDUAL_CHANNELS_13 == expected_channels


def test_tcn_receptive_field_and_architecture():
    """Verify 3 dilated temporal blocks with receptive field of 29 seconds."""
    model = PhysicsResidualTCN(
        num_inputs=13,
        num_classes=4,
        num_channels=[32, 32, 32],
        kernel_size=3,
        dropout=0.10,
    )
    assert model.receptive_field == 29
    assert len(model.network) == 3


def test_causal_masking_no_future_leakage():
    """Verify strictly causal convolutions by ensuring future modifications do not alter past/present outputs."""
    model = PhysicsResidualTCN(num_inputs=13, num_classes=4, num_channels=[16, 16, 16], kernel_size=3)
    model.eval()

    # Create sequence of length 30
    x1 = torch.randn(1, 13, 30)
    x2 = x1.clone()
    # Modify future element (e.g. index 29)
    # The output at index 15 should remain strictly identical
    with torch.no_grad():
        feat1 = model.network(x1)
        # Modify last 5 timesteps in x2
        x2[:, :, 25:] = torch.randn(1, 13, 5)
        feat2 = model.network(x2)

    # For causal convs, feature at step 20 must be identical in feat1 and feat2
    diff = torch.max(torch.abs(feat1[:, :, 20] - feat2[:, :, 20])).item()
    assert diff < 1e-5, f"Future modification leaked into past timestep! diff={diff}"


def test_temporal_sequence_buffer():
    """Test rolling buffer push, warm-up replication, and timestamp discontinuity reset."""
    buf = TemporalSequenceBuffer(window_size=30, num_channels=13)
    vec1 = np.ones(13, dtype=np.float32) * 1.5

    # Push 1st sample at t=10.0
    w1 = buf.push(vec1, timestamp=10.0)
    assert w1.shape == (13, 30)
    # Replicated causal padding should fill entire buffer with 1.5
    assert np.allclose(w1, 1.5)

    # Push 2nd sample at t=11.0 (valid dt=1.0)
    vec2 = np.ones(13, dtype=np.float32) * 2.5
    w2 = buf.push(vec2, timestamp=11.0)
    assert np.allclose(w2[:, -1], 2.5)
    assert np.allclose(w2[:, :-1], 1.5)

    # Push sample with timestamp discontinuity dt=5.0 -> should reset buffer
    vec3 = np.ones(13, dtype=np.float32) * 3.5
    w3 = buf.push(vec3, timestamp=16.0)
    # After reset, buffer count is 1, so replicated with vec3
    assert np.allclose(w3, 3.5)


def test_tcn_saved_model_and_forward_pass():
    """Verify saved PyTorch model weights load cleanly and predict probabilities."""
    pt_path = MODELS_DIR / "aces_tcn_residual.pt"
    if not pt_path.exists():
        pytest.skip("aces_tcn_residual.pt not yet trained.")

    model = PhysicsResidualTCN(num_inputs=13, num_classes=4, num_channels=[32, 32, 32])
    state_dict = torch.load(pt_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()

    sample_in = np.random.randn(13, 30).astype(np.float32)
    pred_class, probs = model.predict_window_np(sample_in)
    assert pred_class in CLASSES_4
    assert len(probs) == 4
    assert abs(sum(probs.values()) - 1.0) < 1e-4


def test_fusion_engine_sensor_veto():
    """Verify that sensor health fault isolation vetos false alarms."""
    engine = FusionEngine()
    hgb_probs = {"Normal": 0.05, "Watch": 0.10, "Warning": 0.35, "Critical": 0.50}
    tcn_probs = {"Normal": 0.05, "Watch": 0.10, "Warning": 0.35, "Critical": 0.50}

    # Isolated sensor fault (low trust, bulk engine physics normal)
    twin_normal = {"max_abs_z": 1.2, "residual_rms": 1.1}
    sensor_fault = {"overall_trust_score": 30.0, "suspect_sensors": ["EGT1"]}

    evidence = engine.fuse(
        hgb_probs=hgb_probs,
        tcn_probs=tcn_probs,
        anomaly_loss=0.01,
        is_unknown_anomaly=False,
        twin_assessment=twin_normal,
        sensor_health=sensor_fault,
    )
    # Sensor fault veto should downgrade to Watch and isolate sensor
    assert evidence.final_diagnosis == "Watch"
    assert "ISOLATED_SENSOR_FAULT" in evidence.reason_codes[0]


def test_fusion_engine_critical_threshold():
    """Verify tau=0.25 critical recall threshold in FusionEngine."""
    engine = FusionEngine()
    hgb_probs = {"Normal": 0.50, "Watch": 0.20, "Warning": 0.04, "Critical": 0.26}
    tcn_probs = {"Normal": 0.50, "Watch": 0.20, "Warning": 0.04, "Critical": 0.26}
    twin_high = {"max_abs_z": 3.8, "residual_rms": 3.2}
    sensor_healthy = {"overall_trust_score": 98.0, "suspect_sensors": []}

    evidence = engine.fuse(
        hgb_probs=hgb_probs,
        tcn_probs=tcn_probs,
        anomaly_loss=0.05,
        is_unknown_anomaly=False,
        twin_assessment=twin_high,
        sensor_health=sensor_healthy,
    )
    assert evidence.final_diagnosis == "Critical"
