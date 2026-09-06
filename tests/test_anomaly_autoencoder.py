import pytest
import numpy as np
import torch
from app.anomaly_autoencoder import TemporalConvAutoencoder


def test_autoencoder_reconstruction_shape():
    ae = TemporalConvAutoencoder(in_channels=14, latent_dim=8)
    x = torch.randn(2, 14, 32)
    recon = ae(x)
    assert recon.shape == (2, 14, 32)


def test_autoencoder_anomaly_detection_logic():
    ae = TemporalConvAutoencoder(in_channels=14, latent_dim=8)
    ae.threshold = 0.50
    
    clean_seq = np.zeros((32, 14), dtype=np.float32)
    res_clean = ae.detect_anomaly(clean_seq)
    assert "reconstruction_error" in res_clean
    assert "is_unknown_anomaly" in res_clean
    assert "assessment" in res_clean
    
    extreme_seq = np.ones((32, 14), dtype=np.float32) * 50.0
    res_extreme = ae.detect_anomaly(extreme_seq)
    assert res_extreme["is_unknown_anomaly"] is True
    assert res_extreme["assessment"] == "UNKNOWN_ANOMALY_INVESTIGATE"
