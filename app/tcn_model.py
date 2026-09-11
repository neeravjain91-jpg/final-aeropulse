"""Physics-Normalized Residual 1D Temporal Convolutional Network (TCN) for Propulsion Health Diagnostics.

This module implements:
1. Lightweight Causal Dilated 1D TCN Architecture (3 blocks, dilations 1, 2, 4, RF=29s).
2. Clean interface to the existing first-principles ReferenceTwin physics residual engine.
3. Strict 13-channel residual mapping (Battery_Current excluded due to uninformative telemetry).
4. Continuous temporal window extraction enforcing strictly dt=1.0s within flight boundaries.
5. Rolling temporal sequence buffer for streaming inference.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    class _MockNNModule:
        def __init__(self, *args, **kwargs): pass
    class _MockNN:
        Module = _MockNNModule
        Conv1d = object
        BatchNorm1d = object
        ReLU = object
        ELU = object
        Dropout = object
    nn = _MockNN()
    F = None
    TORCH_AVAILABLE = False

# The 13 verified continuous channels (Battery_Current is strictly EXCLUDED)
RESIDUAL_CHANNELS_13: List[str] = [
    "Engine_RPM",
    "EGT1",
    "EGT2",
    "EGT3",
    "CHT",
    "Fuel_Flow",
    "Oil_Temp",
    "Oil_Pressure",
    "Battery_Voltage",
    "Alternator_Temp",
    "EFI_Fuel_Temp",
    "EFI_Water_Temp",
    "MAP_Injector",
]

# Standard 4-state health classification
CLASSES_4: List[str] = ["Normal", "Watch", "Warning", "Critical"]
CLASS_TO_IDX: Dict[str, int] = {c: i for i, c in enumerate(CLASSES_4)}
IDX_TO_CLASS: Dict[int, str] = {i: c for i, c in enumerate(CLASSES_4)}


class CausalConv1d(nn.Module):
    """1D Causal Dilated Convolution with exact left-padding to prevent future leakage."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        dilation: int = 1,
    ):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size=kernel_size,
            padding=self.padding,
            dilation=dilation,
            bias=True,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv(x)
        if self.padding > 0:
            out = out[:, :, :-self.padding]
        return out


class TemporalBlock(nn.Module):
    """Residual Dilated Temporal Block with causal receptive field and BatchNorm."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        dilation: int = 1,
        dropout: float = 0.10,
    ):
        super().__init__()
        self.conv1 = CausalConv1d(in_channels, out_channels, kernel_size=kernel_size, dilation=dilation)
        self.norm1 = nn.BatchNorm1d(out_channels)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)

        self.conv2 = CausalConv1d(out_channels, out_channels, kernel_size=kernel_size, dilation=dilation)
        self.norm2 = nn.BatchNorm1d(out_channels)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)

        self.downsample = (
            nn.Conv1d(in_channels, out_channels, kernel_size=1)
            if in_channels != out_channels
            else None
        )
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x if self.downsample is None else self.downsample(x)

        out = self.conv1(x)
        out = self.norm1(out)
        out = self.relu1(out)
        out = self.drop1(out)

        out = self.conv2(out)
        out = self.norm2(out)
        out = self.relu2(out)
        out = self.drop2(out)

        return self.relu(out + residual)


class PhysicsResidualTCN(nn.Module):
    """Lightweight 1D Temporal Convolutional Network for 4-Class Health State Classification.

    Input tensor shape: (batch_size, 13, 30)
    - 13 physics-normalized residual channels
    - 30 seconds causal sequence window at 1 Hz
    """

    def __init__(
        self,
        num_inputs: int = 13,
        num_classes: int = 4,
        num_channels: Optional[List[int]] = None,
        kernel_size: int = 3,
        dropout: float = 0.10,
    ):
        super().__init__()
        if num_channels is None:
            num_channels = [32, 32, 32]

        self.num_inputs = num_inputs
        self.num_classes = num_classes
        if num_classes == 3:
            self.classes = ["Normal", "Degraded", "Critical"]
        elif num_classes == 4:
            self.classes = CLASSES_4
        else:
            self.classes = [f"Class_{i}" for i in range(num_classes)]

        layers = []
        in_ch = num_inputs
        for i, out_ch in enumerate(num_channels):
            dilation = 2 ** i  # 1, 2, 4
            layers.append(
                TemporalBlock(
                    in_channels=in_ch,
                    out_channels=out_ch,
                    kernel_size=kernel_size,
                    dilation=dilation,
                    dropout=dropout,
                )
            )
            in_ch = out_ch

        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(num_channels[-1], num_classes)

        # Receptive field computation
        self.receptive_field = 1 + sum(2 * (kernel_size - 1) * (2 ** i) for i in range(len(num_channels)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Tensor of shape (batch_size, 13, sequence_length)

        Returns:
            logits: Tensor of shape (batch_size, 4)
        """
        features = self.network(x)
        # Extract features at the most recent causal timestep (last step)
        last_timestep = features[:, :, -1]
        logits = self.fc(last_timestep)
        return logits

    def predict_probabilities(self, x: torch.Tensor) -> torch.Tensor:
        """Computes calibrated Softmax probabilities."""
        logits = self.forward(x)
        return F.softmax(logits, dim=1)

    def predict_window_np(self, window_matrix: np.ndarray) -> Tuple[str, Dict[str, float]]:
        """Inference helper for numpy window array of shape (13, 30) or (30, 13) or (30, num_inputs).

        Returns:
            predicted_class: Name of highest probability health state
            prob_dict: Dictionary mapping class name to float probability
        """
        self.eval()
        with torch.no_grad():
            if window_matrix.ndim == 2 and window_matrix.shape[0] == 30 and window_matrix.shape[1] == self.num_inputs:
                tensor_in = torch.tensor(window_matrix.T, dtype=torch.float32).unsqueeze(0)
            elif window_matrix.ndim == 2 and window_matrix.shape[0] == self.num_inputs and window_matrix.shape[1] == 30:
                tensor_in = torch.tensor(window_matrix, dtype=torch.float32).unsqueeze(0)
            elif window_matrix.ndim == 3 and window_matrix.shape[1] == self.num_inputs:
                tensor_in = torch.tensor(window_matrix, dtype=torch.float32)
            else:
                raise ValueError(
                    f"Expected window matrix with input channels {self.num_inputs}, got shape {window_matrix.shape}"
                )

            probs = self.predict_probabilities(tensor_in).cpu().numpy()[0]
            pred_idx = int(np.argmax(probs))
            pred_class = self.classes[pred_idx]
            prob_dict = {self.classes[i]: float(probs[i]) for i in range(len(self.classes))}
            return pred_class, prob_dict

    def predict_window(self, window_matrix: np.ndarray) -> Tuple[str, Dict[str, float]]:
        """Compatibility alias for predict_window_np."""
        return self.predict_window_np(window_matrix)


# Backward compatibility alias
LightweightTCN = PhysicsResidualTCN


class TemporalSequenceBuffer:
    """Rolling temporal sequence buffer for causal sliding-window inference.

    Maintains the most recent W=30 samples of 13-channel physics-normalized residuals.
    """

    def __init__(self, window_size: int = 30, num_channels: int = 13):
        self.window_size = window_size
        self.num_channels = num_channels
        self.buffer = np.zeros((window_size, num_channels), dtype=np.float32)
        self.count = 0
        self.last_timestamp: Optional[float] = None

    def push(self, residual_vector_13: Union[List[float], np.ndarray], timestamp: Optional[float] = None) -> np.ndarray:
        """Pushes a 13-channel residual vector into the buffer.

        If a timestamp discontinuity is detected (dt != 1.0s), the buffer resets.

        Returns:
            Current window array of shape (13, 30) ready for TCN inference.
        """
        vec = np.asarray(residual_vector_13, dtype=np.float32).ravel()
        if len(vec) != self.num_channels:
            raise ValueError(f"Expected 13 residual elements, received {len(vec)}")

        if timestamp is not None and self.last_timestamp is not None:
            dt = timestamp - self.last_timestamp
            if dt != 1.0:
                self.buffer.fill(0.0)
                self.count = 0

        self.last_timestamp = timestamp

        self.buffer[:-1] = self.buffer[1:]
        self.buffer[-1] = vec
        self.count += 1

        if self.count < self.window_size:
            replicated = np.copy(self.buffer)
            pad_len = self.window_size - self.count
            first_valid = self.buffer[-self.count]
            replicated[:pad_len] = first_valid
            return replicated.T

        return self.buffer.T  # (13, 30)


def extract_continuous_residual_windows(
    df: Any,
    reference_twin: Any,
    window_size: int = 30,
    step: int = 1,
    train_stats: Optional[Dict[str, Dict[str, float]]] = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Extracts strictly continuous sequence windows (dt=1.0s) partitioned by Flight."""
    X_list: List[np.ndarray] = []
    y_list: List[int] = []

    flights = sorted(df["Flight"].unique())
    total_continuous_blocks = 0

    for flight in flights:
        fdf = df[df["Flight"] == flight].sort_values("GPS_Time").reset_index(drop=True)
        if len(fdf) < window_size:
            continue

        times = fdf["GPS_Time"].values
        diffs = np.diff(times)
        split_indices = np.where(diffs != 1.0)[0] + 1
        blocks = np.split(fdf, split_indices)

        for block in blocks:
            if len(block) < window_size:
                continue

            total_continuous_blocks += 1

            residuals_block = np.zeros((len(block), len(RESIDUAL_CHANNELS_13)), dtype=np.float32)

            for row_idx in range(len(block)):
                row_dict = block.iloc[row_idx].to_dict()
                state = str(row_dict.get("Operating_State", "CRUISE"))
                exp_dict = reference_twin.expected(state)

                for ch_idx, ch in enumerate(RESIDUAL_CHANNELS_13):
                    obs = float(row_dict.get(ch, exp_dict.get(ch, 0.0)))
                    exp = float(exp_dict.get(ch, 0.0))

                    if train_stats and ch in train_stats:
                        std = max(train_stats[ch]["std"], 1e-4)
                    else:
                        ref_std = reference_twin.stats.get(state, reference_twin.stats["_GLOBAL_"])
                        std = max(float(ref_std[ch]["std"]), 1e-4)

                    residuals_block[row_idx, ch_idx] = (obs - exp) / std

            labels_block = [CLASS_TO_IDX.get(str(s), 0) for s in block["Health_State"].values]

            for w_start in range(0, len(block) - window_size + 1, step):
                w_end = w_start + window_size
                window_x = residuals_block[w_start:w_end].T  # Shape (13, 30)
                window_y = labels_block[w_end - 1]

                X_list.append(window_x)
                y_list.append(window_y)

    if not X_list:
        return (
            np.empty((0, len(RESIDUAL_CHANNELS_13), window_size), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
            {"total_windows": 0, "continuous_blocks": 0},
        )

    X_arr = np.array(X_list, dtype=np.float32)
    y_arr = np.array(y_list, dtype=np.int64)

    metadata = {
        "total_windows": len(X_arr),
        "continuous_blocks": total_continuous_blocks,
        "window_size": window_size,
        "channels": RESIDUAL_CHANNELS_13,
        "classes": CLASSES_4,
    }

    return X_arr, y_arr, metadata


def build_sequences(
    df: Any,
    window_size: int = 30,
    step: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """Backward compatibility wrapper for sequence building."""
    from .digital_twin import ReferenceTwin
    twin = ReferenceTwin()
    X, y, _ = extract_continuous_residual_windows(df, twin, window_size=window_size, step=step)
    return X, y
