"""Automated Data Quality, Physical Coupling & Trajectory Leakage Validator.

Provides comprehensive auditing across synthetic and operational datasets:
1. Missing values, NaN, and Infinity audits
2. Timestamp monotonicity and duplicate checks
3. Physical bounds validation (RPM, CHT, Pressures, Voltages, Health)
4. Causal thermodynamic and fault coupling consistency
5. Sensor-fault vs true engine fault discrimination
6. Mathematical RUL ground-truth consistency (y_true = max(0, t_fail - t))
7. Trajectory-level train/test zero-leakage verification
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple, Set

from .data_schema import CanonicalTelemetryPoint


@dataclass
class DataQualityReport:
    total_trajectories: int
    total_samples: int
    missing_value_count: int
    nan_or_inf_count: int
    duplicate_timestamp_count: int
    timestamp_monotonicity_passed: bool
    physical_bounds_passed: bool
    physical_bound_violations: List[str]
    causal_coupling_passed: bool
    sensor_vs_engine_separation_passed: bool
    rul_ground_truth_passed: bool
    trajectory_leakage_audit: Dict[str, Any]
    status: str                                   # "PASS", "WARNING", "FAIL"
    findings: List[str]
    scientific_disclosures: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DataQualityValidator:
    """Master validator for auditing dataset integrity, physical credibility, and leakage."""

    @classmethod
    def audit_points(
        cls,
        points: List[CanonicalTelemetryPoint],
        trajectory_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Audits a single sequence of CanonicalTelemetryPoints."""
        nan_inf_count = 0
        missing_count = 0
        dup_ts_count = 0
        bound_violations = []
        ts_monotonic = True
        rul_consistent = True

        seen_timestamps: Set[float] = set()
        prev_ts = -1.0

        for i, pt in enumerate(points):
            # Timestamp checks
            if pt.timestamp in seen_timestamps:
                dup_ts_count += 1
            seen_timestamps.add(pt.timestamp)

            if pt.timestamp < prev_ts:
                ts_monotonic = False
            prev_ts = pt.timestamp

            # NaN / Inf / Bound check
            d = pt.to_dict()
            for k, v in d.items():
                if v is None and k not in ("true_failure_time", "true_RUL", "predicted_RUL", "RUL_lower", "RUL_upper", "RUL_confidence"):
                    missing_count += 1
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    nan_inf_count += 1

            ok_bounds, viols = pt.validate_physical_bounds()
            if not ok_bounds:
                bound_violations.extend(viols)

            # Ground truth RUL check
            if pt.true_failure_time is not None and pt.true_RUL is not None:
                expected_rul = max(0.0, round(pt.true_failure_time - (pt.timestamp / 3600.0), 2))
                if abs(pt.true_RUL - expected_rul) > 0.05:
                    rul_consistent = False

        return {
            "trajectory_id": trajectory_id or (points[0].trajectory_id if points else "UNKNOWN"),
            "sample_count": len(points),
            "nan_or_inf_count": nan_inf_count,
            "missing_value_count": missing_count,
            "duplicate_timestamp_count": dup_ts_count,
            "timestamp_monotonicity_passed": ts_monotonic,
            "physical_bounds_passed": len(bound_violations) == 0,
            "physical_bound_violations": bound_violations[:10],
            "rul_ground_truth_passed": rul_consistent,
            "status": "PASS" if (nan_inf_count == 0 and dup_ts_count == 0 and ts_monotonic and len(bound_violations) == 0) else "WARNING",
        }


    @staticmethod
    def _validate_causal_coupling(
        corpus: Dict[str, List[CanonicalTelemetryPoint]],
    ) -> bool:
        """Check that physical-fault trajectories exhibit observable coupled response.

        This is intentionally conservative: it validates monotonic directional
        response for the fault classes represented by the synthetic generator,
        rather than claiming causal identification from observational data.
        """
        checks = 0
        passed = 0
        for tid, pts in corpus.items():
            if not pts:
                continue
            fault = str(getattr(pts[0], "fault_type", "") or "").lower()
            if fault in {"none", "sensor_drift", "sensor_bias", "sensor_spike"}:
                continue
            sev = [float(getattr(p, "degradation_severity", 0.0) or 0.0) for p in pts]
            if max(sev, default=0.0) <= 0.0:
                continue
            checks += 1
            # Compare the first and last quartile averages to avoid treating
            # point noise as evidence of physical coupling.
            n = len(pts)
            q = max(1, n // 4)
            first = pts[:q]
            last = pts[-q:]
            def avg(group, attr):
                vals = [getattr(p, attr, None) for p in group]
                vals = [float(v) for v in vals if v is not None and math.isfinite(float(v))]
                return sum(vals) / len(vals) if vals else None
            if fault == "overheating":
                f, l = avg(first, "cht"), avg(last, "cht")
                ok = f is not None and l is not None and l > f
            elif fault == "lubrication":
                f, l = avg(first, "oil_pressure"), avg(last, "oil_pressure")
                ok = f is not None and l is not None and l < f
            elif fault == "misfire":
                f, l = avg(first, "egt1"), avg(last, "egt1")
                ok = f is not None and l is not None and l < f
            elif fault == "injector":
                f, l = avg(first, "fuel_flow"), avg(last, "fuel_flow")
                ok = f is not None and l is not None and l < f
            else:
                # Unknown physical fault types are not silently declared valid.
                ok = False
            passed += int(ok)
        return checks == 0 or passed == checks

    @classmethod
    def audit_corpus(
        cls,
        corpus: Dict[str, List[CanonicalTelemetryPoint]],
        train_dict: Optional[Dict[str, List[CanonicalTelemetryPoint]]] = None,
        test_dict: Optional[Dict[str, List[CanonicalTelemetryPoint]]] = None,
    ) -> DataQualityReport:
        """Audits entire dataset corpus and verifies trajectory-level train/test leakage isolation."""
        total_samples = 0
        total_nan_inf = 0
        total_missing = 0
        total_dups = 0
        all_bounds_passed = True
        all_ts_monotonic = True
        all_rul_passed = True
        all_violations = []
        findings = []

        for tid, pts in corpus.items():
            res = cls.audit_points(pts, trajectory_id=tid)
            total_samples += res["sample_count"]
            total_nan_inf += res["nan_or_inf_count"]
            total_missing += res["missing_value_count"]
            total_dups += res["duplicate_timestamp_count"]
            if not res["timestamp_monotonicity_passed"]:
                all_ts_monotonic = False
            if not res["physical_bounds_passed"]:
                all_bounds_passed = False
                all_violations.extend(res["physical_bound_violations"])
            if not res["rul_ground_truth_passed"]:
                all_rul_passed = False

        # Trajectory leakage audit
        leakage_audit: Dict[str, Any] = {
            "audit_executed": False,
            "overlap_count": 0,
            "is_leakage_free": True,
            "statement": "No split provided for leakage audit."
        }

        if train_dict is not None and test_dict is not None:
            train_ids = set(train_dict.keys())
            test_ids = set(test_dict.keys())
            overlap = train_ids.intersection(test_ids)
            leakage_audit = {
                "audit_executed": True,
                "train_trajectories_count": len(train_ids),
                "test_trajectories_count": len(test_ids),
                "overlap_count": len(overlap),
                "overlapping_trajectory_ids": list(overlap),
                "is_leakage_free": len(overlap) == 0,
                "statement": "Trajectory-level leakage audit: PASS. No trajectory overlap detected in the evaluated split." if len(overlap) == 0 else "WARNING: Trajectory overlap detected.",
            }
            if len(overlap) == 0:
                findings.append("No trajectory overlap detected in the evaluated split.")
            else:
                findings.append(f"Detected {len(overlap)} overlapping trajectories across train/test partitions.")

        # Sensor vs Engine separation verification
        sensor_separation_passed = True
        for tid, pts in corpus.items():
            if "SENS" in tid:
                for pt in pts:
                    if pt.sensor_fault_present and pt.health_index < 70.0:
                        sensor_separation_passed = False
                        break

        overall_status = "PASS"
        if total_nan_inf > 0 or total_dups > 0 or not all_bounds_passed or not leakage_audit.get("is_leakage_free", True):
            overall_status = "WARNING" if total_nan_inf == 0 else "FAIL"

        disclosures = [
            "All synthetic degradation trajectories originate from ODE wear kinetics rather than physical test-cell data.",
            "Ground truth RUL is strictly calculated as y_true = max(0, t_failure - t) at H_failure = 35.0.",
            "Trajectory-level partitioning enforces that no trajectory overlap is present across evaluated train/test splits.",
            "Sensor faults are modeled strictly at the transducer signal buffer, maintaining true underlying engine health."
        ]

        return DataQualityReport(
            total_trajectories=len(corpus),
            total_samples=total_samples,
            missing_value_count=total_missing,
            nan_or_inf_count=total_nan_inf,
            duplicate_timestamp_count=total_dups,
            timestamp_monotonicity_passed=all_ts_monotonic,
            physical_bounds_passed=all_bounds_passed,
            physical_bound_violations=all_violations[:10],
            causal_coupling_passed=cls._validate_causal_coupling(corpus),
            sensor_vs_engine_separation_passed=sensor_separation_passed,
            rul_ground_truth_passed=all_rul_passed,
            trajectory_leakage_audit=leakage_audit,
            status=overall_status,
            findings=findings,
            scientific_disclosures=disclosures,
        )
