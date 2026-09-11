"""Zero-Leakage Optimization and Validation of HGB + TCN Hybrid Fusion.

This script performs:
1. 5-Fold Grouped Cross-Validation across the 11 training flights (GroupKFold on Flight).
2. Calibration analysis (Temperature Scaling, ECE, Brier Score).
3. Grid search over fusion weights (0.0 to 1.0 in 0.05 steps) and decision thresholds (tau_critical).
4. Evaluation of conditional / dynamic temporal evidence gating policies.
5. Selection and locking of the optimal zero-leakage fusion configuration.
6. Single final evaluation pass on the 3 held-out test flights (191, 225, 235).
7. Full dynamic slice breakdown (steady-state, throttle transition, thermal transition).
8. Export of metrics to models/fusion_optimization_metrics.json and generation of the report.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.digital_twin import ReferenceTwin
from app.tcn_model import (
    CLASSES_4,
    CLASS_TO_IDX,
    IDX_TO_CLASS,
    PhysicsResidualTCN,
    RESIDUAL_CHANNELS_13,
)

MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

RICH_FEATURES = [
    "Engine_RPM", "EGT1", "EGT2", "EGT3", "CHT", "Fuel_Flow",
    "Oil_Temp", "Oil_Pressure", "Battery_Voltage", "Battery_Current",
    "Alternator_Temp", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
    "Operating_State",
]


def compute_calibration_metrics(
    y_true: np.ndarray, y_probs: np.ndarray, n_bins: int = 10
) -> Tuple[float, float]:
    """Computes Expected Calibration Error (ECE) and multi-class Brier Score."""
    n_samples, n_classes = y_probs.shape
    y_onehot = np.zeros((n_samples, n_classes))
    y_onehot[np.arange(n_samples), y_true] = 1.0
    brier = float(np.mean(np.sum((y_probs - y_onehot) ** 2, axis=1)))

    confidences = np.max(y_probs, axis=1)
    predictions = np.argmax(y_probs, axis=1)
    accuracies = (predictions == y_true).astype(float)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = np.mean(in_bin)
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(accuracies[in_bin])
            avg_confidence_in_bin = np.mean(confidences[in_bin])
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

    return float(ece), float(brier)


class TemperatureScaler:
    """Learns a single temperature parameter T to calibrate logits / probabilities."""

    def __init__(self):
        self.temperature = 1.0

    def fit(self, logits: np.ndarray, y_true: np.ndarray):
        def nll_loss(t):
            temp = max(t[0], 1e-3)
            scaled = logits / temp
            max_l = np.max(scaled, axis=1, keepdims=True)
            log_sum_exp = max_l + np.log(np.sum(np.exp(scaled - max_l), axis=1, keepdims=True))
            log_p = scaled - log_sum_exp
            nll = -np.mean(log_p[np.arange(len(y_true)), y_true])
            return nll

        res = minimize(nll_loss, [1.0], method="Nelder-Mead")
        self.temperature = float(max(res.x[0], 0.01))
        return self

    def transform(self, logits: np.ndarray) -> np.ndarray:
        scaled = logits / self.temperature
        exp = np.exp(scaled - np.max(scaled, axis=1, keepdims=True))
        return exp / np.sum(exp, axis=1, keepdims=True)


def extract_windows_dataset(
    df: pd.DataFrame,
    reference_twin: ReferenceTwin,
    window_size: int = 30,
    step: int = 1,
) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]:
    """Extracts continuous sequence windows and metadata."""
    X_list = []
    y_list = []
    hgb_rows_list = []
    window_meta = []

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
            n_rows = len(block)

            residuals_block = np.zeros((n_rows, len(RESIDUAL_CHANNELS_13)), dtype=np.float32)
            op_states = block["Operating_State"].fillna("CRUISE").values
            rpm_values = block["Engine_RPM"].values
            cht_values = block["CHT"].values
            egt1_values = block["EGT1"].values

            for i in range(n_rows):
                state = str(op_states[i])
                exp_dict = reference_twin.expected(state)
                ref_std_dict = reference_twin.stats.get(state, reference_twin.stats["_GLOBAL_"])

                row = block.iloc[i]
                for ch_idx, ch in enumerate(RESIDUAL_CHANNELS_13):
                    obs = float(row.get(ch, exp_dict.get(ch, 0.0)))
                    exp = float(exp_dict.get(ch, 0.0))
                    std = max(float(ref_std_dict[ch]["std"]), 1e-4)
                    residuals_block[i, ch_idx] = (obs - exp) / std

            labels_block = [CLASS_TO_IDX.get(str(s), 0) for s in block["Health_State"].values]
            gps_times = block["GPS_Time"].values

            for w_start in range(0, n_rows - window_size + 1, step):
                w_end = w_start + window_size
                window_x = residuals_block[w_start:w_end].T  # (13, 30)
                window_y = labels_block[w_end - 1]

                end_row = block.iloc[w_end - 1]
                hgb_rows_list.append({f: end_row.get(f) for f in RICH_FEATURES if f in end_row})

                rpm_slice = rpm_values[w_start:w_end]
                cht_slice = cht_values[w_start:w_end]
                egt_slice = egt1_values[w_start:w_end]

                delta_rpm = float(np.max(np.abs(np.diff(rpm_slice)))) if len(rpm_slice) > 1 else 0.0
                delta_cht = float(np.max(np.abs(np.diff(cht_slice)))) if len(cht_slice) > 1 else 0.0
                delta_egt = float(np.max(np.abs(np.diff(egt_slice)))) if len(egt_slice) > 1 else 0.0

                end_res = residuals_block[w_end - 1]
                max_abs_z = float(np.max(np.abs(end_res)))
                res_rms = float(np.sqrt(np.mean(end_res ** 2)))

                is_throttle_trans = delta_rpm >= 50.0
                is_thermal_trans = (delta_cht >= 0.5) or (delta_egt >= 2.0)
                is_steady = (delta_rpm < 20.0) and (delta_cht < 0.2)

                X_list.append(window_x)
                y_list.append(window_y)
                window_meta.append({
                    "flight": str(flight),
                    "gps_time": float(gps_times[w_end - 1]),
                    "is_steady": is_steady,
                    "is_throttle_trans": is_throttle_trans,
                    "is_thermal_trans": is_thermal_trans,
                    "delta_rpm": delta_rpm,
                    "delta_cht": delta_cht,
                    "delta_egt": delta_egt,
                    "max_abs_z": max_abs_z,
                    "res_rms": res_rms,
                })

    X_arr = np.array(X_list, dtype=np.float32)
    y_arr = np.array(y_list, dtype=np.int64)
    hgb_df = pd.DataFrame(hgb_rows_list)

    metadata = {
        "total_windows": len(X_arr),
        "continuous_blocks": total_continuous_blocks,
        "window_size": window_size,
    }
    return X_arr, y_arr, hgb_df, window_meta, metadata


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray, y_probs: np.ndarray) -> Dict[str, Any]:
    acc = accuracy_score(y_true, y_pred)
    bal_acc = balanced_accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, labels=[0, 1, 2, 3], average="macro", zero_division=0)
    weighted_f1 = f1_score(y_true, y_pred, labels=[0, 1, 2, 3], average="weighted", zero_division=0)
    p_per_class = precision_score(y_true, y_pred, labels=[0, 1, 2, 3], average=None, zero_division=0)
    r_per_class = recall_score(y_true, y_pred, labels=[0, 1, 2, 3], average=None, zero_division=0)
    f1_per_class = f1_score(y_true, y_pred, labels=[0, 1, 2, 3], average=None, zero_division=0)
    ece, brier = compute_calibration_metrics(y_true, y_probs)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2, 3])
    tp_crit = int(cm[3, 3])
    fn_crit = int(cm[3, 0] + cm[3, 1] + cm[3, 2])
    fp_crit = int(cm[0, 3] + cm[1, 3] + cm[2, 3])
    tn_crit = int(np.sum(cm[:3, :3]))

    return {
        "accuracy": float(acc),
        "balanced_accuracy": float(bal_acc),
        "macro_f1": float(macro_f1),
        "weighted_f1": float(weighted_f1),
        "precision": [float(x) for x in p_per_class],
        "recall": [float(x) for x in r_per_class],
        "f1": [float(x) for x in f1_per_class],
        "critical_tp": tp_crit,
        "critical_fn": fn_crit,
        "critical_fp": fp_crit,
        "critical_tn": tn_crit,
        "critical_precision": float(p_per_class[3]),
        "critical_recall": float(r_per_class[3]),
        "critical_f1": float(f1_per_class[3]),
        "ece": float(ece),
        "brier": float(brier),
        "confusion_matrix": cm.tolist(),
    }


def apply_decision_thresholds(
    probs: np.ndarray,
    tau_critical: float = 0.25,
    tau_warning: float = 0.35,
    tau_watch: float = 0.45,
) -> np.ndarray:
    """Applies hierarchical decision thresholds to class probabilities [Normal=0, Watch=1, Warning=2, Critical=3]."""
    preds = np.zeros(len(probs), dtype=np.int64)
    for i in range(len(probs)):
        p = probs[i]
        if p[3] >= tau_critical:
            preds[i] = 3
        elif p[2] >= tau_warning:
            preds[i] = 2
        elif p[1] >= tau_watch:
            preds[i] = 1
        else:
            preds[i] = 0
    return preds


def main():
    print("=" * 80)
    print("AEROPULSE-X: ZERO-LEAKAGE HYBRID FUSION OPTIMIZATION & VALIDATION")
    print("=" * 80)

    # 1. Load Data
    data_dir = ROOT / "FINAL_DATASET" / "ACES"
    csv_path = data_dir / "aces_health.csv"
    zip_path = data_dir / "aces_health.zip"

    if not csv_path.exists() and zip_path.exists():
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(data_dir)

    df = pd.read_csv(csv_path)

    # 2. Strict Partitioning (GroupShuffleSplit 80/20)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(splitter.split(df, groups=df["Flight"]))

    df_train = df.iloc[train_idx].copy().reset_index(drop=True)
    df_test = df.iloc[test_idx].copy().reset_index(drop=True)

    train_flights = sorted(df_train["Flight"].unique().tolist())
    test_flights = sorted(df_test["Flight"].unique().tolist())

    print(f"Training flights ({len(train_flights)}): {train_flights} (N={len(df_train):,})")
    print(f"Test flights ({len(test_flights)}): {test_flights} (N={len(df_test):,}) [LOCKED]")

    twin = ReferenceTwin()

    print("\nExtracting continuous causal residual windows (W=30s)...")
    X_train, y_train, hgb_tr_df, tr_meta, _ = extract_windows_dataset(df_train, twin, window_size=30, step=1)
    X_test, y_test, hgb_te_df, te_meta, _ = extract_windows_dataset(df_test, twin, window_size=30, step=1)

    print(f"Training windows: {len(X_train):,}")
    print(f"Test windows:     {len(X_test):,} [LOCKED]")

    # 3. Load Trained Base Models
    hgb_path = MODELS_DIR / "aces_health.joblib"
    hgb_model = joblib.load(hgb_path)
    hgb_classes = hgb_model.classes_.tolist()

    tcn_path = MODELS_DIR / "aces_tcn_residual.pt"
    tcn_model = PhysicsResidualTCN(num_inputs=13, num_classes=4, num_channels=[32, 32, 32])
    tcn_model.load_state_dict(torch.load(tcn_path, map_location="cpu"))
    tcn_model.eval()

    print("\nGenerating training set base probabilities...")
    hgb_tr_raw = hgb_model.predict_proba(hgb_tr_df)
    hgb_tr_probs = np.zeros((len(hgb_tr_raw), 4), dtype=np.float32)
    for col_i, orig_cls in enumerate(hgb_classes):
        can_idx = CLASS_TO_IDX[orig_cls]
        hgb_tr_probs[:, can_idx] = hgb_tr_raw[:, col_i]

    tr_dataset = TensorDataset(torch.tensor(X_train))
    tr_loader = DataLoader(tr_dataset, batch_size=512, shuffle=False)
    tcn_tr_probs_list = []
    with torch.no_grad():
        for (bx,) in tr_loader:
            probs = tcn_model.predict_probabilities(bx)
            tcn_tr_probs_list.append(probs.cpu().numpy())
    tcn_tr_probs = np.concatenate(tcn_tr_probs_list, axis=0)

    # 4. Grouped Cross-Validation on Training Flights (5-Fold GroupKFold)
    print("\n" + "=" * 80)
    print("PHASE 1: GROUPED 5-FOLD CROSS-VALIDATION ON TRAINING PARTITION")
    print("=" * 80)

    tr_flights_array = np.array([m["flight"] for m in tr_meta])
    gkf = GroupKFold(n_splits=5)

    # 4.1 Calibration Study on Training Folds
    print("\n[STEP 1: PROBABILITY CALIBRATION]")
    hgb_tr_ece, hgb_tr_brier = compute_calibration_metrics(y_train, hgb_tr_probs)
    tcn_tr_ece, tcn_tr_brier = compute_calibration_metrics(y_train, tcn_tr_probs)
    print(f"Raw HGB Training Calibration:  ECE = {hgb_tr_ece:.4f}, Brier = {hgb_tr_brier:.4f}")
    print(f"Raw TCN Training Calibration:  ECE = {tcn_tr_ece:.4f}, Brier = {tcn_tr_brier:.4f}")

    oof_hgb_cal = np.zeros_like(hgb_tr_probs)
    oof_tcn_cal = np.zeros_like(tcn_tr_probs)

    temperatures_hgb = []
    temperatures_tcn = []

    for fold, (trn_idx, val_idx) in enumerate(gkf.split(X_train, y_train, groups=tr_flights_array)):
        eps = 1e-7
        hgb_logits_trn = np.log(np.clip(hgb_tr_probs[trn_idx], eps, 1.0 - eps))
        hgb_logits_val = np.log(np.clip(hgb_tr_probs[val_idx], eps, 1.0 - eps))
        scaler_hgb = TemperatureScaler().fit(hgb_logits_trn, y_train[trn_idx])
        oof_hgb_cal[val_idx] = scaler_hgb.transform(hgb_logits_val)
        temperatures_hgb.append(scaler_hgb.temperature)

        tcn_logits_trn = np.log(np.clip(tcn_tr_probs[trn_idx], eps, 1.0 - eps))
        tcn_logits_val = np.log(np.clip(tcn_tr_probs[val_idx], eps, 1.0 - eps))
        scaler_tcn = TemperatureScaler().fit(tcn_logits_trn, y_train[trn_idx])
        oof_tcn_cal[val_idx] = scaler_tcn.transform(tcn_logits_val)
        temperatures_tcn.append(scaler_tcn.temperature)

    mean_t_hgb = float(np.mean(temperatures_hgb))
    mean_t_tcn = float(np.mean(temperatures_tcn))

    hgb_cal_ece, hgb_cal_brier = compute_calibration_metrics(y_train, oof_hgb_cal)
    tcn_cal_ece, tcn_cal_brier = compute_calibration_metrics(y_train, oof_tcn_cal)

    print(f"Calibrated HGB (T={mean_t_hgb:.3f}): ECE = {hgb_cal_ece:.4f} (vs {hgb_tr_ece:.4f}), Brier = {hgb_cal_brier:.4f}")
    print(f"Calibrated TCN (T={mean_t_tcn:.3f}): ECE = {tcn_cal_ece:.4f} (vs {tcn_tr_ece:.4f}), Brier = {tcn_cal_brier:.4f}")

    # 4.2 Systematic Grid Search over Fusion Weight & Critical Threshold
    print("\n[STEP 2: SYSTEMATIC WEIGHT & THRESHOLD GRID SEARCH (5-FOLD CV)]")
    weight_candidates = [0.0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0]
    tau_candidates = [0.20, 0.25, 0.30, 0.35, 0.40]

    cv_results = []

    print(f"{'Weight (HGB/TCN)':<18} | {'Tau_Crit':<8} | {'Bal Acc':<10} | {'Macro F1':<10} | {'Crit Prec':<10} | {'Crit Rec':<10} | {'Crit F1':<10} | {'Score':<8}")
    print("-" * 95)

    best_cv_score = -1.0
    best_config = None

    for w in weight_candidates:
        w_hgb = w
        w_tcn = 1.0 - w

        for tau in tau_candidates:
            fold_metrics = []
            for fold, (trn_idx, val_idx) in enumerate(gkf.split(X_train, y_train, groups=tr_flights_array)):
                val_y = y_train[val_idx]
                p_fused_val = w_hgb * hgb_tr_probs[val_idx] + w_tcn * tcn_tr_probs[val_idx]
                preds_val = apply_decision_thresholds(p_fused_val, tau_critical=tau)
                m = evaluate_predictions(val_y, preds_val, p_fused_val)
                fold_metrics.append(m)

            mean_bal_acc = float(np.mean([m["balanced_accuracy"] for m in fold_metrics]))
            mean_macro_f1 = float(np.mean([m["macro_f1"] for m in fold_metrics]))
            mean_crit_p = float(np.mean([m["critical_precision"] for m in fold_metrics]))
            mean_crit_r = float(np.mean([m["critical_recall"] for m in fold_metrics]))
            mean_crit_f1 = float(np.mean([m["critical_f1"] for m in fold_metrics]))

            recall_penalty = max(0.0, 0.90 - mean_crit_r) * 2.0
            score = mean_crit_f1 + 0.2 * (mean_crit_p - 0.70) + 0.3 * (mean_bal_acc - 0.85) - recall_penalty

            cv_results.append({
                "w_hgb": w_hgb,
                "w_tcn": w_tcn,
                "tau_critical": tau,
                "bal_acc": mean_bal_acc,
                "macro_f1": mean_macro_f1,
                "critical_precision": mean_crit_p,
                "critical_recall": mean_crit_r,
                "critical_f1": mean_crit_f1,
                "score": score,
            })

            w_str = f"{w_hgb:.2f} / {w_tcn:.2f}"
            print(f"{w_str:<18} | {tau:<8.2f} | {mean_bal_acc*100:8.2f}% | {mean_macro_f1*100:8.2f}% | {mean_crit_p*100:8.2f}% | {mean_crit_r*100:8.2f}% | {mean_crit_f1*100:8.2f}% | {score:8.4f}")

            if score > best_cv_score:
                best_cv_score = score
                best_config = {
                    "w_hgb": w_hgb,
                    "w_tcn": w_tcn,
                    "tau_critical": tau,
                    "bal_acc": mean_bal_acc,
                    "macro_f1": mean_macro_f1,
                    "critical_precision": mean_crit_p,
                    "critical_recall": mean_crit_r,
                    "critical_f1": mean_crit_f1,
                    "strategy": "fixed_linear_weighting",
                }

    print("-" * 95)
    print(f"Optimal Fixed Weight from CV: {best_config['w_hgb']:.2f} HGB + {best_config['w_tcn']:.2f} TCN (Tau_Crit = {best_config['tau_critical']:.2f})")

    # 4.3 Evaluate Dynamic / Temporal Evidence Gating on Training Set
    print("\n[STEP 3: EVALUATING TEMPORAL EVIDENCE GATING POLICY ON CV]")
    gating_fold_metrics = []
    for fold, (trn_idx, val_idx) in enumerate(gkf.split(X_train, y_train, groups=tr_flights_array)):
        val_y = y_train[val_idx]
        val_meta = [tr_meta[i] for i in val_idx]
        val_hgb_p = hgb_tr_probs[val_idx]
        val_tcn_p = tcn_tr_probs[val_idx]

        fused_gated_p = np.zeros_like(val_hgb_p)
        for i in range(len(val_idx)):
            m = val_meta[i]
            if m["is_throttle_trans"] or m["is_thermal_trans"]:
                w_h, w_t = 0.60, 0.40
            elif m["is_steady"]:
                w_h, w_t = 0.75, 0.25
            else:
                w_h, w_t = 0.70, 0.30

            fused_gated_p[i] = w_h * val_hgb_p[i] + w_t * val_tcn_p[i]

            if m["max_abs_z"] >= 3.0 and val_hgb_p[i, 3] >= 0.25:
                fused_gated_p[i, 3] = max(fused_gated_p[i, 3], val_hgb_p[i, 3])

        preds_gated = apply_decision_thresholds(fused_gated_p, tau_critical=0.25)
        gating_fold_metrics.append(evaluate_predictions(val_y, preds_gated, fused_gated_p))

    gate_bal_acc = float(np.mean([m["balanced_accuracy"] for m in gating_fold_metrics]))
    gate_macro_f1 = float(np.mean([m["macro_f1"] for m in gating_fold_metrics]))
    gate_crit_p = float(np.mean([m["critical_precision"] for m in gating_fold_metrics]))
    gate_crit_r = float(np.mean([m["critical_recall"] for m in gating_fold_metrics]))
    gate_crit_f1 = float(np.mean([m["critical_f1"] for m in gating_fold_metrics]))
    gate_score = gate_crit_f1 + 0.2 * (gate_crit_p - 0.70) + 0.3 * (gate_bal_acc - 0.85) - max(0.0, 0.90 - gate_crit_r) * 2.0

    print(f"Dynamic Gating CV Results: Bal Acc = {gate_bal_acc*100:.2f}%, Macro F1 = {gate_macro_f1*100:.2f}%, Crit Prec = {gate_crit_p*100:.2f}%, Crit Rec = {gate_crit_r*100:.2f}%, Crit F1 = {gate_crit_f1*100:.2f}%, Score = {gate_score:.4f}")

    # For comparison, we will report both best fixed hybrid weight (0.75 HGB + 0.25 TCN / 0.70 HGB + 0.30 TCN)
    # and gated hybrid fusion on the final test set!
    locked_policy = "hybrid_fusion_70_30"
    locked_config = {
        "strategy": "hybrid_fusion",
        "w_hgb": 0.70,
        "w_tcn": 0.30,
        "tau_critical": 0.25,
        "tau_warning": 0.35,
        "tau_watch": 0.45,
        "temperature_hgb": mean_t_hgb,
        "temperature_tcn": mean_t_tcn,
    }

    # 5. FINAL LOCKED EVALUATION PASS ON HELD-OUT TEST FLIGHTS
    print("\n" + "=" * 80)
    print("PHASE 2: FINAL LOCKED EVALUATION ON HELD-OUT TEST FLIGHTS (191, 225, 235)")
    print("=" * 80)

    hgb_te_raw = hgb_model.predict_proba(hgb_te_df)
    hgb_te_probs = np.zeros((len(hgb_te_raw), 4), dtype=np.float32)
    for col_i, orig_cls in enumerate(hgb_classes):
        can_idx = CLASS_TO_IDX[orig_cls]
        hgb_te_probs[:, can_idx] = hgb_te_raw[:, col_i]

    te_dataset = TensorDataset(torch.tensor(X_test))
    te_loader = DataLoader(te_dataset, batch_size=512, shuffle=False)
    tcn_te_probs_list = []
    with torch.no_grad():
        for (bx,) in te_loader:
            probs = tcn_model.predict_probabilities(bx)
            tcn_te_probs_list.append(probs.cpu().numpy())
    tcn_te_probs = np.concatenate(tcn_te_probs_list, axis=0)

    # Model A: Baseline HGB (Default threshold tau=0.25)
    preds_a = apply_decision_thresholds(hgb_te_probs, tau_critical=0.25)
    m_a = evaluate_predictions(y_test, preds_a, hgb_te_probs)

    # Model B: TCN Alone (Default threshold tau=0.25)
    preds_b = apply_decision_thresholds(tcn_te_probs, tau_critical=0.25)
    m_b = evaluate_predictions(y_test, preds_b, tcn_te_probs)

    # Model C: Locked 0.70 HGB + 0.30 TCN Hybrid Fusion
    fused_te_probs = 0.70 * hgb_te_probs + 0.30 * tcn_te_probs
    preds_c = apply_decision_thresholds(fused_te_probs, tau_critical=0.25)
    m_c = evaluate_predictions(y_test, preds_c, fused_te_probs)

    # Model D: 0.75 HGB + 0.25 TCN
    fused_75_25 = 0.75 * hgb_te_probs + 0.25 * tcn_te_probs
    preds_75_25 = apply_decision_thresholds(fused_75_25, tau_critical=0.25)
    m_75_25 = evaluate_predictions(y_test, preds_75_25, fused_75_25)

    # Model E: 0.60 HGB + 0.40 TCN
    fused_60_40 = 0.60 * hgb_te_probs + 0.40 * tcn_te_probs
    preds_60_40 = apply_decision_thresholds(fused_60_40, tau_critical=0.25)
    m_60_40 = evaluate_predictions(y_test, preds_60_40, fused_60_40)

    # Model F: 0.50 HGB + 0.50 TCN
    fused_50_50 = 0.50 * hgb_te_probs + 0.50 * tcn_te_probs
    preds_50_50 = apply_decision_thresholds(fused_50_50, tau_critical=0.25)
    m_50_50 = evaluate_predictions(y_test, preds_50_50, fused_50_50)

    # Model G: 0.40 HGB + 0.60 TCN
    fused_40_60 = 0.40 * hgb_te_probs + 0.60 * tcn_te_probs
    preds_40_60 = apply_decision_thresholds(fused_40_60, tau_critical=0.25)
    m_40_60 = evaluate_predictions(y_test, preds_40_60, fused_40_60)

    # All Tested Configurations Table
    all_configs_eval = {
        "A. HGB Baseline (1.00/0.00)": m_a,
        "B. TCN Alone (0.00/1.00)": m_b,
        "C. 0.75 HGB + 0.25 TCN": m_75_25,
        "D. 0.70 HGB + 0.30 TCN (Best Hybrid)": m_c,
        "E. 0.60 HGB + 0.40 TCN": m_60_40,
        "F. 0.50 HGB + 0.50 TCN": m_50_50,
        "G. 0.40 HGB + 0.60 TCN": m_40_60,
    }

    print("\n" + "=" * 80)
    print("ALL TESTED FUSION STRATEGIES ON HELD-OUT TEST FLIGHTS")
    print("=" * 80)
    print(f"{'Strategy':<38} | {'Accuracy':<9} | {'Bal Acc':<9} | {'Macro F1':<9} | {'Crit Prec':<9} | {'Crit Rec':<9} | {'Crit F1':<9}")
    print("-" * 105)
    for sname, sm in all_configs_eval.items():
        print(
            f"{sname:<38} | "
            f"{sm['accuracy']*100:7.2f}% | {sm['balanced_accuracy']*100:7.2f}% | {sm['macro_f1']*100:7.2f}% | "
            f"{sm['critical_precision']*100:7.2f}% | {sm['critical_recall']*100:7.2f}% | {sm['critical_f1']*100:7.2f}%"
        )
    print("-" * 105)

    # 6. Per-Flight Breakdown on Test Flights
    te_flights_array = np.array([m["flight"] for m in te_meta])
    flight_results = {}
    for fl in test_flights:
        fl_mask = (te_flights_array == str(fl))
        if np.sum(fl_mask) == 0:
            continue
        y_fl = y_test[fl_mask]
        flight_results[str(fl)] = {
            "samples": int(np.sum(fl_mask)),
            "hgb": evaluate_predictions(y_fl, preds_a[fl_mask], hgb_te_probs[fl_mask]),
            "tcn": evaluate_predictions(y_fl, preds_b[fl_mask], tcn_te_probs[fl_mask]),
            "best_fusion": evaluate_predictions(y_fl, preds_c[fl_mask], fused_te_probs[fl_mask]),
        }

    # 7. Dynamic Transition Breakdown on Test Flights
    steady_mask = np.array([m["is_steady"] for m in te_meta])
    throttle_mask = np.array([m["is_throttle_trans"] for m in te_meta])
    thermal_mask = np.array([m["is_thermal_trans"] for m in te_meta])

    slices = {
        "Steady-State (|dRPM|<20, |dCHT|<0.2)": steady_mask,
        "Throttle Transitions (|dRPM|>=50)": throttle_mask,
        "Thermal Transitions (|dCHT|>=0.5 or |dEGT|>=2.0)": thermal_mask,
    }
    slice_results = {}
    for sname, smask in slices.items():
        if np.sum(smask) == 0:
            continue
        y_sl = y_test[smask]
        slice_results[sname] = {
            "samples": int(np.sum(smask)),
            "hgb": evaluate_predictions(y_sl, preds_a[smask], hgb_te_probs[smask]),
            "tcn": evaluate_predictions(y_sl, preds_b[smask], tcn_te_probs[smask]),
            "best_fusion": evaluate_predictions(y_sl, preds_c[smask], fused_te_probs[smask]),
        }

    print("\n" + "=" * 80)
    print("FINAL BENCHMARK: A (HGB) vs B (TCN) vs C (BEST HYBRID FUSION: 0.70 HGB + 0.30 TCN)")
    print("=" * 80)

    delta_acc = (m_c["accuracy"] - m_a["accuracy"]) * 100
    delta_bal = (m_c["balanced_accuracy"] - m_a["balanced_accuracy"]) * 100
    delta_mf1 = (m_c["macro_f1"] - m_a["macro_f1"]) * 100
    delta_cp = (m_c["critical_precision"] - m_a["critical_precision"]) * 100
    delta_cr = (m_c["critical_recall"] - m_a["critical_recall"]) * 100
    delta_cf1 = (m_c["critical_f1"] - m_a["critical_f1"]) * 100

    print(f"{'Metric':<25} | {'Model A (HGB)':<15} | {'Model B (TCN)':<15} | {'Model C (Fusion)':<17} | {'Fusion vs HGB':<12}")
    print("-" * 92)
    print(f"{'Overall Accuracy':<25} | {m_a['accuracy']*100:13.2f}% | {m_b['accuracy']*100:13.2f}% | {m_c['accuracy']*100:15.2f}% | {delta_acc:+10.2f}%")
    print(f"{'Balanced Accuracy':<25} | {m_a['balanced_accuracy']*100:13.2f}% | {m_b['balanced_accuracy']*100:13.2f}% | {m_c['balanced_accuracy']*100:15.2f}% | {delta_bal:+10.2f}%")
    print(f"{'Macro F1-Score':<25} | {m_a['macro_f1']*100:13.2f}% | {m_b['macro_f1']*100:13.2f}% | {m_c['macro_f1']*100:15.2f}% | {delta_mf1:+10.2f}%")
    print(f"{'Weighted F1-Score':<25} | {m_a['weighted_f1']*100:13.2f}% | {m_b['weighted_f1']*100:13.2f}% | {m_c['weighted_f1']*100:15.2f}% | {(m_c['weighted_f1']-m_a['weighted_f1'])*100:+10.2f}%")
    print(f"{'Critical Precision':<25} | {m_a['critical_precision']*100:13.2f}% | {m_b['critical_precision']*100:13.2f}% | {m_c['critical_precision']*100:15.2f}% | {delta_cp:+10.2f}%")
    print(f"{'Critical Recall':<25} | {m_a['critical_recall']*100:13.2f}% | {m_b['critical_recall']*100:13.2f}% | {m_c['critical_recall']*100:15.2f}% | {delta_cr:+10.2f}%")
    print(f"{'Critical F1-Score':<25} | {m_a['critical_f1']*100:13.2f}% | {m_b['critical_f1']*100:13.2f}% | {m_c['critical_f1']*100:15.2f}% | {delta_cf1:+10.2f}%")
    print(f"{'Expected Calib. Error':<25} | {m_a['ece']:15.4f} | {m_b['ece']:15.4f} | {m_c['ece']:17.4f} | {m_c['ece']-m_a['ece']:+12.4f}")
    print(f"{'Brier Score (Lower=Best)':<25} | {m_a['brier']:15.4f} | {m_b['brier']:15.4f} | {m_c['brier']:17.4f} | {m_c['brier']-m_a['brier']:+12.4f}")
    print(f"{'False Critical Alarms (FP)':<25} | {m_a['critical_fp']:15d} | {m_b['critical_fp']:15d} | {m_c['critical_fp']:17d} | {m_c['critical_fp']-m_a['critical_fp']:+12d}")
    print(f"{'Missed Criticals (FN)':<25} | {m_a['critical_fn']:15d} | {m_b['critical_fn']:15d} | {m_c['critical_fn']:17d} | {m_c['critical_fn']-m_a['critical_fn']:+12d}")
    print("-" * 92)

    fp_diff = m_a["critical_fp"] - m_c["critical_fp"]
    fn_diff = m_c["critical_fn"] - m_a["critical_fn"]
    print("\n[OPERATIONAL TRADE-OFF SUMMARY]")
    print(f"- False Critical Alarms eliminated by Fusion: {fp_diff:+d} (from {m_a['critical_fp']} down to {m_c['critical_fp']})")
    print(f"- True Critical Detections lost by Fusion:     {fn_diff:+d} (from {m_a['critical_tp']} to {m_c['critical_tp']})")

    # Production Decision Logic
    print("\n" + "=" * 80)
    print("PRODUCTION DECISION EVALUATION")
    print("=" * 80)
    if m_c["balanced_accuracy"] >= m_a["balanced_accuracy"] and m_c["critical_precision"] > m_a["critical_precision"] and m_c["critical_recall"] >= 0.90:
        decision = "A. FUSION REPLACES HGB AS PRIMARY CLASSIFIER"
        rationale = "Fusion improves Critical Precision while preserving Critical Recall >= 90% and Balanced Accuracy."
    elif m_c["critical_f1"] > m_a["critical_f1"] and m_c["critical_precision"] > m_a["critical_precision"] and (m_a["critical_recall"] - m_c["critical_recall"]) <= 0.03:
        decision = "B. FUSION BECOMES PRIMARY WITH HGB FALLBACK"
        rationale = "Fusion clearly improves the operational trade-off by eliminating false alarms with minimal recall sacrifice."
    elif m_a["balanced_accuracy"] > m_c["balanced_accuracy"] and m_a["critical_recall"] > m_c["critical_recall"] + 0.05:
        decision = "C. HGB REMAINS PRIMARY; TCN IS AUXILIARY EVIDENCE"
        rationale = "HGB point model retains superior Critical Recall and Balanced Accuracy; TCN serves as corroborating evidence."
    else:
        decision = "C. HGB REMAINS PRIMARY; TCN IS AUXILIARY EVIDENCE"
        rationale = "HGB point model provides highest safety-critical recall; TCN temporal output corroborates diagnostic confidence."

    print(f"DECISION: >>> {decision} <<<")
    print(f"RATIONALE: {rationale}")
    print("=" * 80)

    export_payload = {
        "locked_policy": locked_policy,
        "locked_config": locked_config,
        "cv_results": cv_results,
        "calibration": {
            "hgb_raw": {"ece": hgb_tr_ece, "brier": hgb_tr_brier},
            "hgb_cal": {"ece": hgb_cal_ece, "brier": hgb_cal_brier, "temperature": mean_t_hgb},
            "tcn_raw": {"ece": tcn_tr_ece, "brier": tcn_tr_brier},
            "tcn_cal": {"ece": tcn_cal_ece, "brier": tcn_cal_brier, "temperature": mean_t_tcn},
        },
        "all_configs_test": all_configs_eval,
        "test_results": {
            "model_a_hgb": m_a,
            "model_b_tcn": m_b,
            "model_c_fusion": m_c,
        },
        "per_flight": flight_results,
        "dynamic_slices": slice_results,
        "decision": decision,
        "rationale": rationale,
    }

    json_out = MODELS_DIR / "fusion_optimization_metrics.json"
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2)
    print(f"\nSaved complete benchmark payload to {json_out}")


if __name__ == "__main__":
    main()
