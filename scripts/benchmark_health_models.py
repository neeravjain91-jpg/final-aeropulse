"""Leakage-safe health-model benchmark for AeroPulse-X.

This benchmark is deliberately separate from the runtime inference path.
It evaluates models on the same held-out flight groups and reports only
metrics that can be reproduced from the supplied ACES dataset.

Usage:
    python scripts/benchmark_health_models.py --data-dir FINAL_DATASET
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, LabelEncoder

ROOT = Path(__file__).resolve().parents[1]

BASE_FEATURES = [
    "Engine_RPM", "EGT1", "EGT2", "EGT3", "CHT", "Fuel_Flow",
    "Oil_Temp", "Oil_Pressure", "Battery_Voltage", "Battery_Current",
    "Alternator_Temp", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
    "Operating_State",
]

FORBIDDEN_FEATURES = {
    "Health_State", "Degradation_Severity", "fault_severity",
    "Fault_Severity", "true_RUL", "true_failure_time",
    "RUL", "predicted_RUL", "RUL_lower", "RUL_upper",
    "Robust_Anomaly_Score", "Robust_Max_Deviation",
}


def locate_aces(data_dir: Path) -> Path:
    candidates = [
        data_dir / "ACES" / "aces_health.csv",
        data_dir / "aces_health.csv",
        ROOT / "FINAL_DATASET" / "ACES" / "aces_health.csv",
        ROOT / "data_sample" / "aces_demo.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "ACES dataset not found. Expected FINAL_DATASET/ACES/aces_health.csv "
        "or data_sample/aces_demo.csv."
    )


def load_dataset(data_dir: Path) -> tuple[pd.DataFrame, Path]:
    path = locate_aces(data_dir)
    df = pd.read_csv(path)
    if "Health_State" not in df.columns:
        raise ValueError("Dataset must contain Health_State.")
    if "Flight" not in df.columns:
        raise ValueError(
            "Dataset must contain Flight so evaluation can use flight-level "
            "holdout rather than a leaking row-level split."
        )
    return df, path


def validate_feature_contract(df: pd.DataFrame, features: list[str]) -> None:
    overlap = sorted(set(features) & FORBIDDEN_FEATURES)
    if overlap:
        raise AssertionError(f"Forbidden target/derived fields in features: {overlap}")

    forbidden_present = sorted(
        (set(df.columns) & FORBIDDEN_FEATURES) - {"Health_State"}
    )
    # Presence is acceptable; use is forbidden.
    if "Health_State" not in df.columns:
        raise AssertionError("Target column missing.")


def make_pipeline(model, features: list[str]) -> Pipeline:
    numeric = [f for f in features if f != "Operating_State"]
    categorical = ["Operating_State"] if "Operating_State" in features else []
    transformers = [
        (
            "num",
            Pipeline([("impute", SimpleImputer(strategy="median"))]),
            numeric,
        )
    ]
    if categorical:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical,
            )
        )
    pre = ColumnTransformer(transformers, remainder="drop")
    return Pipeline([("pre", pre), ("model", model)])


def critical_metrics(y_true, pred) -> dict:
    report = classification_report(
        y_true, pred, output_dict=True, zero_division=0
    )
    critical = report.get("Critical", {})
    return {
        "critical_precision": float(critical.get("precision", 0.0)),
        "critical_recall": float(critical.get("recall", 0.0)),
        "critical_f1": float(critical.get("f1-score", 0.0)),
        "per_class_f1": {
            str(k): float(v.get("f1-score", 0.0))
            for k, v in report.items()
            if isinstance(v, dict) and "f1-score" in v
        },
    }



def engineer_temporal_physics_features(df: pd.DataFrame, train: pd.DataFrame, test: pd.DataFrame, base_features: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Add leakage-safe temporal derivatives and train-only healthy-reference residuals.

    Temporal features are computed within Flight using prior/current rows only.
    Physics residuals are standardized against Normal samples from the training
    flights only, grouped by Operating_State where possible. No target-derived
    fields are used.
    """
    work = df.copy()
    numeric = [f for f in base_features if f != "Operating_State" and f in work.columns]
    if "Flight" not in work.columns:
        raise ValueError("Flight is required for temporal feature engineering.")

    # Preserve dataset order within each flight; ACES telemetry is sequential.
    temporal_names: list[str] = []
    for col in numeric:
        g = work.groupby("Flight", sort=False)[col]
        prev = g.shift(1)
        delta = work[col] - prev
        name = f"d_{col}"
        work[name] = delta.replace([np.inf, -np.inf], np.nan)
        temporal_names.append(name)
        # Short causal trend: current value minus 5-sample causal mean.
        causal_mean = g.transform(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
        trend_name = f"trend5_{col}"
        work[trend_name] = (work[col] - causal_mean).replace([np.inf, -np.inf], np.nan)
        temporal_names.append(trend_name)

    # Train-only healthy reference, with operating-state conditioning.
    train_ids = set(train.index)
    normal_train = train[train["Health_State"].astype(str).str.lower().eq("normal")]
    global_stats = {}
    for col in numeric:
        med = float(normal_train[col].median())
        mad = float((normal_train[col] - med).abs().median())
        scale = max(1.4826 * mad, float(normal_train[col].std()), 1e-3)
        global_stats[col] = (med, scale)

    residual_names: list[str] = []
    state_stats: dict[tuple[str, str], tuple[float, float]] = {}
    if "Operating_State" in base_features:
        for state, grp in normal_train.groupby("Operating_State", dropna=False):
            key_state = str(state)
            for col in numeric:
                med = float(grp[col].median())
                mad = float((grp[col] - med).abs().median())
                scale = max(1.4826 * mad, float(grp[col].std()), 1e-3)
                state_stats[(key_state, col)] = (med, scale)

    for col in numeric:
        def residual(row):
            key = (str(row["Operating_State"]), col) if "Operating_State" in base_features else None
            med, scale = state_stats.get(key, global_stats[col]) if key is not None else global_stats[col]
            return (float(row[col]) - med) / scale
        rname = f"physres_{col}"
        work[rname] = work.apply(residual, axis=1).replace([np.inf, -np.inf], np.nan)
        residual_names.append(rname)

    engineered = temporal_names + residual_names
    train_out = work.loc[train.index].copy()
    test_out = work.loc[test.index].copy()
    return train_out, test_out, engineered

def benchmark_model(name, model, train, test, features) -> dict:
    pipe = make_pipeline(model, features)
    y_train = train["Health_State"]
    y_test = test["Health_State"]
    label_encoder = None
    if name == "XGBoost":
        # XGBoost's multiclass objective requires contiguous integer labels.
        # Encode only the target; all telemetry feature columns remain unchanged.
        label_encoder = LabelEncoder().fit(y_train)
        y_train = label_encoder.transform(y_train)
    t0 = time.perf_counter()
    pipe.fit(train[features], y_train)
    fit_seconds = time.perf_counter() - t0

    t1 = time.perf_counter()
    pred = pipe.predict(test[features])
    if label_encoder is not None:
        pred = label_encoder.inverse_transform(pred.astype(int))
    inference_seconds = time.perf_counter() - t1

    result = {
        "model": name,
        "accuracy": float(accuracy_score(test["Health_State"], pred)),
        "balanced_accuracy": float(
            balanced_accuracy_score(test["Health_State"], pred)
        ),
        "macro_f1": float(
            f1_score(test["Health_State"], pred, average="macro", zero_division=0)
        ),
        "weighted_f1": float(
            f1_score(test["Health_State"], pred, average="weighted", zero_division=0)
        ),
        "fit_seconds": round(fit_seconds, 4),
        "prediction_seconds_total": round(inference_seconds, 4),
        "prediction_ms_per_sample": round(
            inference_seconds / max(len(test), 1) * 1000.0, 6
        ),
        "confusion_matrix": confusion_matrix(
            test["Health_State"], pred, labels=sorted(test["Health_State"].unique())
        ).tolist(),
    }
    result.update(critical_metrics(test["Health_State"], pred))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(ROOT / "FINAL_DATASET"))
    parser.add_argument("--test-size", type=float, default=0.20)
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    df, source = load_dataset(data_dir)

    features = [f for f in BASE_FEATURES if f in df.columns]
    missing = [f for f in BASE_FEATURES if f not in df.columns]
    if missing:
        raise ValueError(f"Required ACES features missing: {missing}")

    validate_feature_contract(df, features)

    # Deterministic flight-level split. No row from a held-out flight can enter
    # training, preprocessing, model fitting, or healthy-reference fitting.
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=args.test_size, random_state=42
    )
    train_idx, test_idx = next(splitter.split(df, groups=df["Flight"]))
    train = df.iloc[train_idx].copy()
    test = df.iloc[test_idx].copy()

    train_groups = set(train["Flight"].astype(str))
    test_groups = set(test["Flight"].astype(str))
    if train_groups & test_groups:
        raise AssertionError("Flight-level leakage detected.")

    models = {
        "HGB": HistGradientBoostingClassifier(
            max_iter=150, learning_rate=0.10, max_leaf_nodes=31,
            min_samples_leaf=20, l2_regularization=1.0,
            class_weight="balanced", random_state=42,
        ),
        "ExtraTrees": ExtraTreesClassifier(
            n_estimators=300, min_samples_leaf=2,
            class_weight="balanced", random_state=42, n_jobs=-1,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=2,
            class_weight="balanced", random_state=42, n_jobs=-1,
        ),
    }

    # Optional stronger tabular learners. They are not runtime dependencies;
    # the benchmark records them as unavailable if the package is absent.
    optional = {}
    try:
        from xgboost import XGBClassifier
        optional["XGBoost"] = XGBClassifier(
            n_estimators=400, max_depth=6, learning_rate=0.05,
            subsample=0.85, colsample_bytree=0.85,
            objective="multi:softprob", eval_metric="mlogloss",
            tree_method="hist", random_state=42, n_jobs=-1,
        )
    except ImportError:
        optional["XGBoost"] = None

    try:
        from lightgbm import LGBMClassifier
        optional["LightGBM"] = LGBMClassifier(
            n_estimators=400, learning_rate=0.05, num_leaves=31,
            subsample=0.85, colsample_bytree=0.85,
            random_state=42, verbosity=-1,
        )
    except ImportError:
        optional["LightGBM"] = None

    try:
        from catboost import CatBoostClassifier
        optional["CatBoost"] = CatBoostClassifier(
            iterations=400, depth=7, learning_rate=0.05,
            loss_function="MultiClass", verbose=False, random_seed=42,
        )
    except ImportError:
        optional["CatBoost"] = None

    train_aug, test_aug, engineered = engineer_temporal_physics_features(df, train, test, features)
    feature_sets = {
        "baseline": features,
        "temporal": features + [f for f in engineered if f.startswith("d_") or f.startswith("trend5_")],
        "physics_residual": features + [f for f in engineered if f.startswith("physres_")],
        "temporal_plus_physics": features + engineered,
    }

    results = []
    for feature_set_name, feature_set in feature_sets.items():
        for name, model in {**models, **optional}.items():
            if model is None:
                results.append({"feature_set": feature_set_name, "model": name, "status": "NOT_INSTALLED"})
                continue
            try:
                result = benchmark_model(name, model, train_aug, test_aug, feature_set)
                result["feature_set"] = feature_set_name
                result["feature_count"] = len(feature_set)
                results.append(result)
            except Exception as exc:
                results.append({"feature_set": feature_set_name, "model": name, "status": "FAILED", "error": repr(exc)})

    output = {
        "benchmark": "AeroPulse-X leakage-safe health classifier comparison",
        "dataset": str(source),
        "dataset_rows": int(len(df)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_flights": sorted(train_groups),
        "test_flights": sorted(test_groups),
        "features": features,
        "engineered_features": engineered,
        "feature_set_names": list(feature_sets),
        "forbidden_feature_contract": sorted(FORBIDDEN_FEATURES),
        "results": results,
        "method_note": (
            "Metrics are descriptive measurements on this held-out ACES split. "
            "They do not establish generalization to another aircraft, engine, "
            "or run-to-failure RUL accuracy."
        ),
    }

    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    path = out / "health_model_benchmark.json"
    path.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
    print(f"REPORT={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
