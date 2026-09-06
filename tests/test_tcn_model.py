import pytest
import numpy as np
import torch
from app.tcn_model import LightweightTCN, CausalConv1d, TemporalBlock


def test_causal_conv_preserves_length():
    conv = CausalConv1d(in_channels=4, out_channels=8, kernel_size=3, dilation=2)
    x = torch.randn(2, 4, 30)
    out = conv(x)
    assert out.shape == (2, 8, 30)


def test_temporal_block_residual_connection():
    block = TemporalBlock(in_channels=16, out_channels=16, kernel_size=3, dilation=1)
    x = torch.randn(2, 16, 30)
    out = block(x)
    assert out.shape == (2, 16, 30)


def test_tcn_forward_pass_and_predict_window():
    tcn = LightweightTCN(num_inputs=14, num_classes=3, num_channels=[16, 16], kernel_size=3)
    window = np.random.randn(30, 14).astype(np.float32)
    label, probs = tcn.predict_window(window)
    
    assert label in ["Normal", "Degraded", "Critical"]
    assert len(probs) == 3
    assert abs(sum(probs.values()) - 1.0) < 1e-4
    assert all(0.0 <= p <= 1.0 for p in probs.values())
