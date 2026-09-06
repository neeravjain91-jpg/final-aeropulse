"""Automated Unit & Integration Tests for Phase D RUL & Prognostics Scientific Validation."""
from __future__ import annotations

import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.rul_validation import (
    SyntheticRULTrajectoryGenerator,
    TrajectorySplitter,
    RULPrognosticsValidator,
    FAILURE_HEALTH_THRESHOLD,
)
from app.rul_service import RULService
from app.degradation import estimate_degradation_horizon


def test_synthetic_trajectory_generation_and_ground_truth_rul():
    """Verifies that synthetic trajectories compute true RUL to critical failure threshold (35.0)."""
    gen = SyntheticRULTrajectoryGenerator(master_seed=42)
    traj = gen.generate_trajectory("TRAJ_TEST_01", failure_mode="thermal", duration_hours=40.0, time_step_hours=0.5)

    assert len(traj) > 0
    failure_time = traj[0].ground_truth_failure_time_hours
    assert failure_time > 0.0

    for pt in traj:
        assert pt.trajectory_id == "TRAJ_TEST_01"
        assert pt.health_index >= 0.0
        assert pt.health_index <= 100.0
        assert pt.ground_truth_rul_hours >= 0.0
        # True RUL must equal max(0, t_failure - t_current)
        expected_rul = max(0.0, round(failure_time - pt.time_hours, 2))
        assert abs(pt.ground_truth_rul_hours - expected_rul) < 0.05


def test_trajectory_level_split_no_leakage():
    """Verifies that trajectory-level train/test partitioning has zero overlap and zero data leakage."""
    gen = SyntheticRULTrajectoryGenerator(master_seed=42)
    corpus = gen.generate_corpus(num_trajectories=20, duration_hours=30.0, time_step_hours=0.5)
    train_trajs, test_trajs = TrajectorySplitter.split(corpus, train_ratio=0.70, seed=42)

    audit = TrajectorySplitter.verify_zero_leakage(train_trajs, test_trajs)

    assert audit["train_trajectories_count"] == 14
    assert audit["test_trajectories_count"] == 6
    assert audit["trajectory_overlap_count"] == 0
    assert audit["is_leakage_free"] is True


@pytest.fixture(scope="module")
def shared_validation_result():
    """Module-level cached validation result to avoid redundant model training and evaluations."""
    validator = RULPrognosticsValidator(master_seed=42)
    return validator.run_full_validation_suite()


def test_ablation_study_hybrid_superiority(shared_validation_result):
    """Verifies that Hybrid physics+data model outperforms pure data-driven and physics-only models."""
    ablation = shared_validation_result["ablation_study"]
    phys = ablation["physics_only"]
    data = ablation["data_only"]
    hyb = ablation["hybrid_physics_data"]

    assert hyb["mae_hours"] <= data["mae_hours"]
    assert hyb["mae_hours"] <= phys["mae_hours"]
    assert hyb["coverage_90ci_pct"] >= 85.0
    assert ablation["hybrid_advantage_demonstrated"] is True


def test_uncertainty_calibration_across_stages(shared_validation_result):
    """Verifies that empirical coverage for nominal 90% prediction intervals is calibrated across all stages."""
    stages = shared_validation_result["uncertainty_calibration_by_stage"]
    assert len(stages) == 4

    stage_widths = []
    for s in stages:
        assert s["nominal_confidence_pct"] == 90.0
        assert s["empirical_coverage_pct"] >= 85.0
        assert s["mean_interval_width_hours"] > 0.0
        stage_widths.append(s["mean_interval_width_hours"])

    # Uncertainty intervals must narrow as engine approaches failure (Healthy > Early > Severe)
    assert stage_widths[0] >= stage_widths[-1]


def test_prognostic_horizon_alpha_lambda(shared_validation_result):
    """Verifies calculation of Prognostic Horizon under +/-20% alpha error tolerance."""
    ph = shared_validation_result["prognostic_horizon"]
    assert ph["alpha_error_tolerance_pct"] == 20.0
    assert ph["mean_prognostic_horizon_hours"] > 0.0
    assert ph["trajectories_evaluated"] > 0


def test_prediction_stability_monotonic_wear(shared_validation_result):
    """Verifies that consecutive step-by-step predictions exhibit smooth transitions during monotonic degradation."""
    stability = shared_validation_result["prediction_stability"]
    assert stability["smooth_transition_rate_pct"] >= 90.0
    assert stability["stability_criteria_passed"] is True


def test_mission_stress_consistency_monotonicity(shared_validation_result):
    """Verifies that higher operating stress strictly shortens RUL monotonically."""
    stress = shared_validation_result["mission_stress_consistency"]
    assert stress["all_stress_monotonic"] is True
    assert stress["high_altitude_18k"]["monotonic"] is True
    assert stress["hot_ambient_45c"]["monotonic"] is True
    assert stress["high_throttle_95pct"]["monotonic"] is True


def test_short_history_and_missing_data_robustness():
    """Verifies graceful degradation under sparse samples, missing telemetry, and non-degrading trends."""
    # 1. Sparse History (<6 points)
    res_sparse = estimate_degradation_horizon([90.0, 89.0, 88.0], step_minutes=5.0)
    assert res_sparse["status"] == "INSUFFICIENT_HISTORY"
    assert res_sparse["rul_hours"] is None

    # 2. Stationary Trend
    res_flat = estimate_degradation_horizon([85.0, 85.01, 84.99, 85.0, 85.02, 84.98], step_minutes=5.0)
    assert res_flat["status"] == "STABLE_OR_NON_DEGRADING"
    assert res_flat["rul_hours"] is None

    # 3. Critical threshold (<=35.0)
    res_crit = estimate_degradation_horizon([34.0, 33.0, 32.0, 31.0, 30.0, 29.0], step_minutes=5.0)
    assert res_crit["rul_hours"] == 0.0

    # 4. Incomplete Telemetry
    service = RULService()
    res_incomp = service.predict({"Engine_RPM": 4000.0})
    assert res_incomp["rul_hours"] > 0.0


def test_failure_mode_specific_prognostics(shared_validation_result):
    """Verifies separate prognostic evaluation across distinct physical degradation mechanisms."""
    fm_list = shared_validation_result["failure_mode_breakdown"]
    modes = set(f["failure_mode"] for f in fm_list)

    assert "thermal" in modes
    assert "lubrication" in modes
    assert "mechanical" in modes
    assert "injector" in modes
    assert "compound" in modes

    for fm in fm_list:
        assert fm["sample_count"] > 0
        assert fm["mae_hours"] >= 0.0
        assert fm["coverage_90ci_pct"] >= 80.0


def test_nasa_cmapss_and_aces_boundary_declarations(shared_validation_result):
    """Verifies that NASA C-MAPSS and NASA ACES datasets have strict, scientifically honest boundary declarations."""
    cmapss = shared_validation_result["nasa_cmapss_cross_domain_proxy"]
    aces = shared_validation_result["nasa_aces_target_domain_context"]

    assert cmapss["domain_classification"] == "TURBOFAN_CROSS_DOMAIN_PROGNOSTICS_PROXY"
    assert "not aero-piston" in cmapss["aero_piston_applicability"].lower()

    assert aces["domain_classification"] == "TARGET_DOMAIN_OPERATIONAL_CONTEXT"
    assert aces["run_to_failure_ground_truth"] == "NOT_AVAILABLE"


def test_rul_validation_api_endpoint():
    """Verifies that GET /api/v1/validation/rul returns HTTP 200 with valid schema."""
    client = TestClient(app)
    res = client.get("/api/v1/validation/rul")

    assert res.status_code == 200
    data = res.json()
    assert data["validation_suite"] == "PHASE_D_RUL_PROGNOSTICS_VALIDATION"
    assert data["overall_validation_passed"] is True
    assert "leakage_audit" in data
    assert "model_benchmarks" in data
    assert "ablation_study" in data
    assert "uncertainty_calibration_by_stage" in data
