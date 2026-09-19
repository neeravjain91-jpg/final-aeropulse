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
from sklearn.preprocessing import OneHotEncoder

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
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
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


def benchmark_model(name, model, train, test, features) -> dict:
    pipe = make_pipeline(model, features)
    t0 = time.perf_counter()
    pipe.fit(train[features], train["Health_State"])
    fit_seconds = time.perf_counter() - t0

    t1 = time.perf_counter()
    pred = pipe.predict(test[features])
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

    results = []
    for name, model in {**models, **optional}.items():
        if model is None:
            results.append({"model": name, "status": "NOT_INSTALLED"})
            continue
        try:
            results.append(benchmark_model(name, model, train, test, features))
        except Exception as exc:
            results.append({"model": name, "status": "FAILED", "error": repr(exc)})

    output = {
        "benchmark": "AeroPulse-X leakage-safe health classifier comparison",
        "dataset": str(source),
        "dataset_rows": int(len(df)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_flights": sorted(train_groups),
        "test_flights": sorted(test_groups),
        "features": features,
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
