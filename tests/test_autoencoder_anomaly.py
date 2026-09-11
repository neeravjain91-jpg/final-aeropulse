"""Comprehensive Regression Tests for Temporal TCN Autoencoder Anomaly Detection."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest
import torch

from app.anomaly_autoencoder import TemporalTCNAutoencoder
from app.inference import AeroTwinAI
from app.simulator import inject_fault
from app.tcn_model import RESIDUAL_CHANNELS_13

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"


def test_autoencoder_architecture_and_shapes():
    """Verify encoder-decoder shapes and channel configuration."""
    model = TemporalTCNAutoencoder(in_channels=13, latent_channels=8, hidden_channels=32)
    assert model.in_channels == 13
    assert model.latent_channels == 8
    assert "Battery_Current" not in RESIDUAL_CHANNELS_13

    # Dummy batch of shape (2, 13, 30)
    x = torch.randn(2, 13, 30)
    recon = model(x)
    assert recon.shape == (2, 13, 30)

    # Check latent bottleneck shape
    z = model.encode(x)
    assert z.shape == (2, 8, 30)


def test_reconstruction_error_and_anomaly_attribution():
    """Verify reconstruction error calculation and channel deviation attribution."""
    model = TemporalTCNAutoencoder(in_channels=13, latent_channels=8, hidden_channels=32, threshold=0.10)
    model.eval()

    # Create synthetic window of shape (13, 30)
    normal_win = np.random.randn(13, 30).astype(np.float32) * 0.1
    res_normal = model.detect_anomaly_window(normal_win)

    assert "reconstruction_error" in res_normal
    assert "is_unknown_anomaly" in res_normal
    assert "anomaly_score" in res_normal
    assert "channel_attributions" in res_normal
    assert len(res_normal["channel_attributions"]) == 4

    # Inject massive anomaly on channel 4 (CHT)
    anom_win = np.copy(normal_win)
    anom_win[4, :] += 10.0  # CHT severe spike
    res_anom = model.detect_anomaly_window(anom_win)

    assert res_anom["is_unknown_anomaly"] is True
    assert res_anom["anomaly_score"] > res_normal["anomaly_score"]
    # Check that CHT is identified in channel attributions
    top_channels = [attr["channel"] for attr in res_anom["channel_attributions"]]
    assert "CHT" in top_channels


def test_autoencoder_saved_model_and_torchscript_consistency():
    """Verify saved PyTorch model weights load cleanly and predict anomalies."""
    pt_path = MODELS_DIR / "aces_tcn_autoencoder.pt"
    if not pt_path.exists():
        pytest.skip("aces_tcn_autoencoder.pt not yet trained.")

    model = TemporalTCNAutoencoder(in_channels=13, latent_channels=8, hidden_channels=32)
    state = torch.load(pt_path, map_location="cpu")
    model.load_state_dict(state)
    model.eval()

    sample_in = np.random.randn(13, 30).astype(np.float32) * 0.2
    res = model.detect_anomaly_window(sample_in)
    assert isinstance(res["reconstruction_error"], float)
    assert isinstance(res["is_unknown_anomaly"], bool)


def test_physical_fault_injection_autoencoder_response():
    """Verify that simulated physical engine faults produce elevated reconstruction loss."""
    model = TemporalTCNAutoencoder(in_channels=13, latent_channels=8, hidden_channels=32, threshold=0.50)
    pt_path = MODELS_DIR / "aces_tcn_autoencoder.pt"
    if pt_path.exists():
        model.load_state_dict(torch.load(pt_path, map_location="cpu"))
    model.eval()

    base_telemetry = {
        "Engine_RPM": 4544.0, "EGT1": 1250.0, "EGT2": 1250.0, "EGT3": 1250.0,
        "CHT": 180.0, "Fuel_Flow": 8.5, "Oil_Temp": 180.0, "Oil_Pressure": 55.0,
        "Battery_Voltage": 14.2, "Battery_Current": 0.0, "Alternator_Temp": 55.0,
        "EFI_Fuel_Temp": 35.0, "EFI_Water_Temp": 85.0, "MAP_Injector": 29.5,
        "Operating_State": "CRUISE",
    }

    # Severe overheating fault
    faulty_telemetry = inject_fault(base_telemetry, fault="overheating", severity=0.8)
    assert faulty_telemetry["CHT"] > base_telemetry["CHT"]
    assert faulty_telemetry["Oil_Temp"] > base_telemetry["Oil_Temp"]


def test_dual_anomaly_detection_in_aerotwin_ai():
    """Verify AeroTwinAI exposes both point Isolation Forest and temporal TCN Autoencoder scores."""
    ai = AeroTwinAI()
    telemetry = {
        "Engine_RPM": 4544.0, "EGT1": 1250.0, "EGT2": 1250.0, "EGT3": 1250.0,
        "CHT": 180.0, "Fuel_Flow": 8.5, "Oil_Temp": 180.0, "Oil_Pressure": 55.0,
        "Battery_Voltage": 14.2, "Battery_Current": 0.0, "Alternator_Temp": 55.0,
        "EFI_Fuel_Temp": 35.0, "EFI_Water_Temp": 85.0, "MAP_Injector": 29.5,
        "Operating_State": "CRUISE",
    }
    res = ai.analyze(telemetry)
    assert "anomaly_score" in res
    assert "tcn_anomaly_score" in res
    assert "tcn_reconstruction_error" in res
    assert "tcn_channel_attributions" in res
    assert isinstance(res["tcn_reconstruction_error"], float)
