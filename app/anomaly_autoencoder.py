"""Lightweight Temporal Autoencoder for Unsupervised Unknown Anomaly Detection."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn


class TemporalConvAutoencoder(nn.Module):
    """1D Convolutional Autoencoder for sequence reconstruction and out-of-distribution anomaly detection."""

    def __init__(self, in_channels: int = 14, latent_dim: int = 8):
        super().__init__()
        self.in_channels = in_channels
        self.latent_dim = latent_dim

        self.encoder = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, latent_dim, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm1d(latent_dim),
            nn.ReLU(),
        )

        self.decoder = nn.Sequential(
            nn.ConvTranspose1d(latent_dim, 32, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.ConvTranspose1d(32, in_channels, kernel_size=3, stride=2, padding=1, output_padding=1),
        )

        self.threshold = 0.05

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.encoder(x)
        reconstruction = self.decoder(latent)
        if reconstruction.shape[2] != x.shape[2]:
            reconstruction = reconstruction[:, :, :x.shape[2]]
        return reconstruction

    def compute_reconstruction_error(self, x: torch.Tensor) -> float:
        """Computes MSE between x and reconstructed x."""
        self.eval()
        with torch.no_grad():
            x_recon = self.forward(x)
            diff = (x - x_recon) ** 2
            mse = torch.mean(diff).item()
            return float(mse)

    def detect_anomaly(self, window_data: np.ndarray) -> Dict[str, Any]:
        """Evaluates a telemetry window and determines whether an unknown anomaly is present."""
        self.eval()
        with torch.no_grad():
            if window_data.ndim == 2:
                x = torch.tensor(window_data.T, dtype=torch.float32).unsqueeze(0)
            else:
                x = torch.tensor(window_data, dtype=torch.float32)

            error = self.compute_reconstruction_error(x)
            is_anomaly = bool(error > self.threshold)
            score = float(min(1.0, error / (self.threshold * 2.5)))

            return {
                "reconstruction_error": round(error, 5),
                "threshold": round(self.threshold, 5),
                "is_unknown_anomaly": is_anomaly,
                "anomaly_score": round(score, 4),
                "assessment": "UNKNOWN_ANOMALY_INVESTIGATE" if is_anomaly else "WITHIN_NORMAL_ENVELOPE",
            }
