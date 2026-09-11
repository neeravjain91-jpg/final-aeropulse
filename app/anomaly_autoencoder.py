"""Temporal TCN Autoencoder for Unsupervised Anomaly Detection.

This module implements a 1D Dilated Causal Convolutional Autoencoder for unsupervised
anomaly detection and novel fault identification from physics-normalized residuals.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn

from app.tcn_model import CausalConv1d, RESIDUAL_CHANNELS_13


class TemporalTCNAutoencoder(nn.Module):
    """1D Dilated Causal Convolutional Autoencoder for Physics-Residual Anomaly Detection.

    Learns the manifold of nominal flight physics residuals. During flight,
    unmodeled mechanical faults, rapid sensor drift, or zero-day anomalies
    produce elevated reconstruction errors.
    """

    def __init__(
        self,
        in_channels: int = 13,
        latent_channels: int = 8,
        hidden_channels: int = 32,
        kernel_size: int = 3,
        threshold: float = 0.66747,
        latent_dim: Optional[int] = None,
        **kwargs: Any,
    ):
        super().__init__()
        if latent_dim is not None:
            latent_channels = latent_dim

        self.in_channels = in_channels
        self.latent_channels = latent_channels
        self.latent_dim = latent_channels
        self.hidden_channels = hidden_channels
        self.kernel_size = kernel_size
        self.threshold = threshold

        # Encoder: in_channels -> hidden_channels (d=1) -> hidden_channels//2 (d=2) -> latent_channels (d=4)
        mid_channels = max(8, hidden_channels // 2)
        self.enc_conv1 = CausalConv1d(in_channels, hidden_channels, kernel_size=kernel_size, dilation=1)
        self.enc_norm1 = nn.BatchNorm1d(hidden_channels)
        self.enc_relu1 = nn.ReLU()

        self.enc_conv2 = CausalConv1d(hidden_channels, mid_channels, kernel_size=kernel_size, dilation=2)
        self.enc_norm2 = nn.BatchNorm1d(mid_channels)
        self.enc_relu2 = nn.ReLU()

        self.enc_conv3 = CausalConv1d(mid_channels, latent_channels, kernel_size=kernel_size, dilation=4)
        self.enc_norm3 = nn.BatchNorm1d(latent_channels)
        self.enc_relu3 = nn.ReLU()

        # Decoder: latent_channels -> mid_channels (d=4) -> hidden_channels (d=2) -> in_channels (d=1)
        self.dec_conv1 = CausalConv1d(latent_channels, mid_channels, kernel_size=kernel_size, dilation=4)
        self.dec_norm1 = nn.BatchNorm1d(mid_channels)
        self.dec_relu1 = nn.ReLU()

        self.dec_conv2 = CausalConv1d(mid_channels, hidden_channels, kernel_size=kernel_size, dilation=2)
        self.dec_norm2 = nn.BatchNorm1d(hidden_channels)
        self.dec_relu2 = nn.ReLU()

        self.dec_conv3 = CausalConv1d(hidden_channels, in_channels, kernel_size=kernel_size, dilation=1)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        out = self.enc_relu1(self.enc_norm1(self.enc_conv1(x)))
        out = self.enc_relu2(self.enc_norm2(self.enc_conv2(out)))
        out = self.enc_relu3(self.enc_norm3(self.enc_conv3(out)))
        return out

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        out = self.dec_relu1(self.dec_norm1(self.dec_conv1(z)))
        out = self.dec_relu2(self.dec_norm2(self.dec_conv2(out)))
        out = self.dec_conv3(out)
        return out

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encode(x)
        reconstructed = self.decode(z)
        return reconstructed

    def compute_reconstruction_error(
        self, x: torch.Tensor, metric: str = "mse"
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Computes window reconstruction loss and per-channel reconstruction losses."""
        reconstructed = self.forward(x)
        if metric == "mae":
            diff = torch.abs(x - reconstructed)
        else:
            diff = (x - reconstructed) ** 2

        # Mean across time dimension (axis 2) -> (batch, num_channels)
        channel_losses = torch.mean(diff, dim=2)
        # Mean across channels -> (batch,)
        window_losses = torch.mean(channel_losses, dim=1)
        return window_losses, channel_losses

    def detect_anomaly_window(
        self, window_matrix: np.ndarray, channel_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Inference helper for evaluating a residual sequence window."""
        if channel_names is None:
            channel_names = RESIDUAL_CHANNELS_13

        self.eval()
        with torch.no_grad():
            if window_matrix.ndim == 2:
                if window_matrix.shape[1] == self.in_channels:
                    tensor_in = torch.tensor(window_matrix.T, dtype=torch.float32).unsqueeze(0)
                elif window_matrix.shape[0] == self.in_channels:
                    tensor_in = torch.tensor(window_matrix, dtype=torch.float32).unsqueeze(0)
                else:
                    tensor_in = torch.tensor(window_matrix.T, dtype=torch.float32).unsqueeze(0)
            elif window_matrix.ndim == 3:
                tensor_in = torch.tensor(window_matrix, dtype=torch.float32)
            else:
                raise ValueError(f"Invalid input shape: {window_matrix.shape}")

            window_loss_t, ch_loss_t = self.compute_reconstruction_error(tensor_in, metric="mse")
            error = float(window_loss_t.cpu().numpy()[0])
            ch_losses = ch_loss_t.cpu().numpy()[0]

            is_anomaly = bool(error > self.threshold)
            normalized_score = float(min(1.0, max(0.0, error / (self.threshold * 2.0))))

            top_ch_indices = np.argsort(ch_losses)[::-1][:min(4, len(ch_losses))]
            channel_attributions = [
                {
                    "channel": channel_names[i] if i < len(channel_names) else f"ch_{i}",
                    "reconstruction_loss": round(float(ch_losses[i]), 5),
                }
                for i in top_ch_indices
            ]

            assessment = "UNKNOWN_ANOMALY_INVESTIGATE" if is_anomaly else "NOMINAL_PHYSICS_RECONSTRUCTION"

            return {
                "reconstruction_error": round(error, 5),
                "threshold": round(self.threshold, 5),
                "is_unknown_anomaly": is_anomaly,
                "anomaly_score": round(normalized_score, 4),
                "channel_attributions": channel_attributions,
                "assessment": assessment,
            }

    def detect_anomaly(self, sequence: np.ndarray, channel_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Backward compatibility alias for detect_anomaly_window."""
        return self.detect_anomaly_window(sequence, channel_names=channel_names)


# Backward compatibility alias
TemporalConvAutoencoder = TemporalTCNAutoencoder
