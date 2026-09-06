"""Lightweight 1D Temporal Convolutional Network (TCN) for Propulsion Health Diagnostics."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class CausalConv1d(nn.Module):
    """1D Causal Dilated Convolution with exact left-padding."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, dilation: int = 1):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size=kernel_size,
            padding=self.padding,
            dilation=dilation,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv(x)
        if self.padding > 0:
            out = out[:, :, :-self.padding]
        return out


class TemporalBlock(nn.Module):
    """Residual Dilated Temporal Block with causal receptive field."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, dilation: int = 1, dropout: float = 0.1):
        super().__init__()
        self.conv1 = CausalConv1d(in_channels, out_channels, kernel_size=kernel_size, dilation=dilation)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)

        self.conv2 = CausalConv1d(out_channels, out_channels, kernel_size=kernel_size, dilation=dilation)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)

        self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x if self.downsample is None else self.downsample(x)
        out = self.conv1(x)
        out = self.relu1(out)
        out = self.drop1(out)

        out = self.conv2(out)
        out = self.relu2(out)
        out = self.drop2(out)

        return self.relu(out + residual)


class LightweightTCN(nn.Module):
    """Lightweight Edge-Ready Temporal Convolutional Network for 3-state Health Classification."""

    CLASSES = ["Normal", "Degraded", "Critical"]

    def __init__(
        self,
        num_inputs: int = 14,
        num_classes: int = 3,
        num_channels: List[int] = None,
        kernel_size: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()
        if num_channels is None:
            num_channels = [32, 32, 32]
        layers = []
        in_ch = num_inputs
        for i, out_ch in enumerate(num_channels):
            dilation = 2 ** i
            layers.append(TemporalBlock(in_ch, out_ch, kernel_size=kernel_size, dilation=dilation, dropout=dropout))
            in_ch = out_ch

        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(num_channels[-1], num_classes)
        self.num_inputs = num_inputs
        self.num_classes = num_classes

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass: x is shape (batch_size, num_inputs, seq_len)."""
        y = self.network(x)
        pooled = torch.mean(y, dim=2)
        logits = self.fc(pooled)
        return logits

    def predict_window(self, window_data: np.ndarray) -> Tuple[str, Dict[str, float]]:
        """Predicts class label and probabilities for a given numpy window (seq_len, num_inputs)."""
        self.eval()
        with torch.no_grad():
            if window_data.ndim == 2:
                x = torch.tensor(window_data.T, dtype=torch.float32).unsqueeze(0)
            else:
                x = torch.tensor(window_data, dtype=torch.float32)
            
            logits = self.forward(x)
            probs = F.softmax(logits, dim=1).cpu().numpy()[0]
            pred_idx = int(np.argmax(probs))
            pred_label = self.CLASSES[pred_idx]
            prob_dict = {self.CLASSES[i]: float(probs[i]) for i in range(len(self.CLASSES))}
            return pred_label, prob_dict


def build_sequences(df: Any, window_size: int = 30, step: int = 10, with_physics: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """Extracts sequence windows strictly within flight mission boundaries (zero temporal leakage)."""
    import pandas as pd
    target_map = {"Normal": 0, "Watch": 1, "Warning": 1, "Degraded": 1, "Critical": 2}
    cols = [
        "Engine_RPM", "EGT1", "EGT2", "EGT3", "CHT", "Fuel_Flow",
        "Oil_Temp", "Oil_Pressure", "Battery_Voltage", "Battery_Current",
        "Alternator_Temp", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
    ]
    X_list, y_list = [], []
    if "Flight" in df.columns:
        flights = df["Flight"].unique()
    else:
        flights = ["flight_0"]
        df = df.copy()
        df["Flight"] = "flight_0"
        
    for flight in flights:
        fdf = df[df["Flight"] == flight]
        if len(fdf) < window_size:
            continue
        vals = fdf[[c for c in cols if c in fdf.columns]].fillna(0.0).values
        lbls = fdf["Health_State"].map(lambda x: target_map.get(str(x), 0)).values if "Health_State" in fdf.columns else np.zeros(len(fdf))
        
        mean = np.mean(vals, axis=0, keepdims=True)
        std = np.std(vals, axis=0, keepdims=True) + 1e-6
        norm_vals = (vals - mean) / std
        
        for i in range(0, len(norm_vals) - window_size + 1, step):
            w_x = norm_vals[i : i + window_size].T
            w_y = int(lbls[i + window_size - 1])
            X_list.append(w_x)
            y_list.append(w_y)
            
    if not X_list:
        return np.empty((0, len(cols), window_size), dtype=np.float32), np.empty((0,), dtype=np.int64)
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int64)

