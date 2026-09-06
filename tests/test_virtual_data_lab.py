"""Automated Unit and Integration Tests for AeroPulse-X Virtual Data Laboratory."""
from __future__ import annotations

import pytest
import math
from fastapi.testclient import TestClient

from app.main import app
from app.data_schema import CanonicalTelemetryPoint, SCHEMA_VERSION
from app.dataset_registry import DatasetRegistry
from app.data_engine import VirtualDataLabEngine, FAILURE_HEALTH_THRESHOLD
from app.data_validator import DataQualityValidator
from app.data_replay import ClosedLoopReplayEngine


@pytest.fixture(scope="module")
def shared_data_lab_engine():
    return VirtualDataLabEngine(master_seed=42)


def test_canonical_schema_fields_and_bounds():
    """1. Verifies that CanonicalTelemetryPoint contains all required fields and validates physical limits."""
    pt = CanonicalTelemetryPoint(
        timestamp=100.0,
        trajectory_id="TRAJ_TEST_SCHEMA_01",
        RPM=4650.0,
        throttle=0.65,
        health_index=95.0,
        true_RUL=25.0,
        true_failure_time=30.0,
    )
    d = pt.to_dict()
    assert d["schema_version"] == "2.0.0"
    assert d["trajectory_id"] == "TRAJ_TEST_SCHEMA_01"
    assert d["RPM"] == 4650.0
    assert "CHT" in d
    assert "oil_pressure" in d
    assert "bus_voltage" in d
    assert "CAN_CRC_status" in d
    assert "flight_computer_state" in d

    valid, viols = pt.validate_physical_bounds()
    assert valid is True
    assert len(viols) == 0


def test_healthy_trajectory_generation(shared_data_lab_engine):
    """2. Verifies healthy trajectory generation across 8 flight phases with temporal continuity."""
    traj = shared_data_lab_engine.generate_healthy_trajectory(
        trajectory_id="TRAJ_HEALTHY_TEST",
        duration_hours=4.0,
        time_step_hours=0.05,
        seed=42,
    )
    assert len(traj) > 0
    phases_seen = set(pt.mission_phase for pt in traj)
    assert "STARTUP" in phases_seen
    assert "TAKEOFF" in phases_seen
    assert "CRUISE" in phases_seen
    assert "LANDING" in phases_seen

    for pt in traj:
        assert pt.health_index >= 90.0
        assert pt.fault_present is False
        assert pt.sensor_trust >= 95.0
        assert pt.ECU_state == "ACTIVE_RUN"


def test_progressive_degradation_trajectories(shared_data_lab_engine):
    """3. Verifies progressive wear degradation across all 7 failure modes down to H=35.0."""
    modes = ["thermal", "lubrication", "mechanical", "injector", "misfire", "electrical", "compound"]
    for m in modes:
        traj = shared_data_lab_engine.generate_degradation_trajectory(
            trajectory_id=f"TRAJ_DEG_{m.upper()}_TEST",
            failure_mode=m,
            duration_hours=35.0,
            seed=42,
        )
        assert len(traj) > 0
        t_fail = traj[0].true_failure_time
        assert t_fail is not None
        assert t_fail > 0.0

        # Check degradation down to critical
        final_pt = traj[-1]
        assert final_pt.health_index <= 50.0
        assert final_pt.degradation_severity > 0.0
        assert final_pt.fault_type == m


def test_physically_coupled_fault_dynamics(shared_data_lab_engine):
    """4. Verifies causal thermodynamic and mechanical coupling for specific faults."""
    traj_therm = shared_data_lab_engine.generate_degradation_trajectory(
        trajectory_id="TRAJ_THERM_TEST",
        failure_mode="thermal",
        duration_hours=35.0,
        seed=42,
    )
    # Thermal wear causes CHT to rise
    assert traj_therm[-1].CHT > traj_therm[0].CHT

    traj_lub = shared_data_lab_engine.generate_degradation_trajectory(
        trajectory_id="TRAJ_LUB_TEST",
        failure_mode="lubrication",
        duration_hours=35.0,
        seed=42,
    )
    # Lubrication wear causes oil pressure to drop and vibration to rise
    assert traj_lub[-1].oil_pressure < traj_lub[0].oil_pressure
    assert traj_lub[-1].vibration > traj_lub[0].vibration


def test_sensor_fault_isolation(shared_data_lab_engine):
    """5. Verifies that transducer sensor faults do NOT alter underlying engine health."""
    traj_sens = shared_data_lab_engine.generate_sensor_fault_trajectory(
        trajectory_id="TRAJ_SENS_TEST",
        sensor_fault_type="bias",
        target_sensor="CHT",
        duration_hours=3.0,
        fault_onset_hours=1.0,
        severity=0.8,
        seed=42,
    )
    pre_fault = [p for p in traj_sens if p.timestamp < 3600.0]
    post_fault = [p for p in traj_sens if p.timestamp >= 7200.0]

    assert len(pre_fault) > 0 and len(post_fault) > 0
    assert pre_fault[0].sensor_fault_present is False
    assert post_fault[-1].sensor_fault_present is True
    assert post_fault[-1].sensor_trust < 50.0
    # Underlying engine physics remains healthy!
    assert post_fault[-1].health_index >= 90.0


def test_rul_ground_truth_exactness(shared_data_lab_engine):
    """6. Verifies mathematical RUL ground truth formula: y_true = max(0, t_fail - t)."""
    traj = shared_data_lab_engine.generate_degradation_trajectory(
        trajectory_id="TRAJ_RUL_GT_TEST",
        failure_mode="mechanical",
        duration_hours=30.0,
        seed=42,
    )
    t_fail = traj[0].true_failure_time
    for pt in traj:
        t_h = pt.timestamp / 3600.0
        expected = max(0.0, round(t_fail - t_h, 2))
        assert abs(pt.true_RUL - expected) < 0.05


def test_can_and_flight_computer_traces(shared_data_lab_engine):
    """7. Verifies virtual CAN framing and flight computer scheduler metrics."""
    traj = shared_data_lab_engine.generate_healthy_trajectory("TRAJ_CAN_TEST", duration_hours=1.0, seed=42)
    for pt in traj:
        assert pt.CAN_DLC == 8
        assert pt.CAN_CRC_status == "VALID"
        assert pt.flight_computer_state == "OPERATIONAL"
        assert pt.watchdog_state == "HEALTHY"


def test_deterministic_seed_reproducibility(shared_data_lab_engine):
    """8. Verifies identical random seeds generate bitwise-identical trajectories."""
    traj1 = shared_data_lab_engine.generate_degradation_trajectory("TRAJ_DETERM_01", failure_mode="thermal", seed=12345)
    traj2 = shared_data_lab_engine.generate_degradation_trajectory("TRAJ_DETERM_01", failure_mode="thermal", seed=12345)
    assert len(traj1) == len(traj2)
    for p1, p2 in zip(traj1, traj2):
        assert p1.CHT == p2.CHT
        assert p1.oil_pressure == p2.oil_pressure
        assert p1.health_index == p2.health_index
        assert p1.true_RUL == p2.true_RUL


def test_data_quality_corpus_auditor(shared_data_lab_engine):
    """9. Verifies automated data-quality validator reports PASS on generated corpus."""
    corpus = shared_data_lab_engine.generate_master_corpus(
        num_healthy=5,
        num_degradation=10,
        num_sensor_faults=4,
        num_missions=3,
        num_can_faults=0,
        master_seed=42,
    )
    train_d, test_d = VirtualDataLabEngine.split_corpus_trajectories(corpus, train_ratio=0.70, seed=42)
    report = DataQualityValidator.audit_corpus(corpus=corpus, train_dict=train_d, test_dict=test_d)

    assert report.total_trajectories == 22
    assert report.total_samples > 0
    assert report.nan_or_inf_count == 0
    assert report.duplicate_timestamp_count == 0
    assert report.timestamp_monotonicity_passed is True
    assert report.physical_bounds_passed is True
    assert report.trajectory_leakage_audit["is_leakage_free"] is True
    assert report.status == "PASS"


def test_trajectory_level_split_no_leakage(shared_data_lab_engine):
    """10. Verifies trajectory-level train/test partitioning has zero cross-contamination."""
    corpus = shared_data_lab_engine.generate_master_corpus(num_healthy=6, num_degradation=8, num_can_faults=0, master_seed=42)
    train_d, test_d = VirtualDataLabEngine.split_corpus_trajectories(corpus, train_ratio=0.65, seed=42)
    overlap = set(train_d.keys()).intersection(set(test_d.keys()))
    assert len(overlap) == 0


def test_closed_loop_pipeline_replay(shared_data_lab_engine):
    """11. Verifies complete closed-loop replay through the SIL digital twin pipeline."""
    traj = shared_data_lab_engine.generate_degradation_trajectory("TRAJ_REPLAY_TEST", failure_mode="thermal", duration_hours=5.0, seed=42)
    replay_engine = ClosedLoopReplayEngine(master_seed=42)
    summary = replay_engine.replay_trajectory(traj)

    assert summary.status == "COMPLETED"
    assert summary.total_steps == len(traj)
    assert summary.final_health_index <= summary.initial_health_index
    assert len(summary.steps) == len(traj)
    assert "Fault:" in summary.steps[0].causal_flow_summary


def test_dataset_registry_catalog():
    """12. Verifies dataset registry catalog metadata and domain disclosures."""
    reg = DatasetRegistry()
    summary = reg.get_summary()
    assert summary["total_datasets"] == 5
    assert summary["primary_datasets"] == 1
    assert summary["operational_context_datasets"] == 1
    assert summary["cross_domain_proxies"] == 3

    aces = reg.get("NASA_ACES")
    assert aces is not None
    assert aces.domain == "GENERAL_AVIATION_PISTON_TELEMETRY"
    assert aces.ground_truth_available is False
    assert "Altus II" in aces.purpose
    assert "NO run-to-failure RUL" in aces.limitations[0]


def test_materialized_corpus_statistics(shared_data_lab_engine):
    """13. Verifies actual empirical counts of materialized benchmark corpus."""
    stats = shared_data_lab_engine.get_materialized_corpus_statistics(master_seed=42)
    assert stats["generator_status"] == "MATERIALIZED_DETERMINISTIC_CORPUS"
    assert stats["healthy_trajectory_count"] == 20
    assert stats["progressive_degradation_trajectory_count"] == 35
    assert stats["compound_fault_trajectory_count"] == 5
    assert stats["sensor_fault_trajectory_count"] == 15
    assert stats["mission_scenario_count"] == 10
    assert stats["can_fault_scenario_count"] == 10
    assert stats["total_trajectory_count"] == 90
    assert stats["total_telemetry_sample_count"] > 4000
    assert stats["leakage_audit_result"] == "Trajectory-level leakage audit: PASS"


def test_data_lab_api_endpoints():
    """14. Verifies all 8 FastAPI Data Lab endpoints return HTTP 200 OK."""
    client = TestClient(app)
    # 1. Catalog
    res = client.get("/api/v1/data/catalog")
    assert res.status_code == 200
    assert res.json()["total_datasets"] == 5

    # 2. Health
    res = client.get("/api/v1/data/health")
    assert res.status_code == 200
    assert res.json()["status"] == "OPERATIONAL"

    # 3. Trajectory Fetch
    res = client.get("/api/v1/data/trajectory/TRAJ_HEALTHY_001")
    assert res.status_code == 200
    assert res.json()["sample_count"] > 0

    # 4. Generate Data
    res = client.post("/api/v1/data/generate", json={"category": "degradation", "scenario_type": "thermal", "duration_hours": 10.0})
    assert res.status_code == 200
    assert res.json()["sample_count"] > 0

    # 5. Quality Audit
    res = client.get("/api/v1/data/quality")
    assert res.status_code == 200
    assert res.json()["status"] == "PASS"

    # 6. Statistics
    res = client.get("/api/v1/data/statistics")
    assert res.status_code == 200
    assert "metrics" in res.json()

    # 7. Ground Truth
    res = client.get("/api/v1/data/ground-truth/TRAJ_DEG_THERMAL_001")
    assert res.status_code == 200
    assert res.json()["failure_health_threshold"] == 35.0

    # 8. Replay
    res = client.post("/api/v1/data/replay", json={"trajectory_id": "TRAJ_HEALTHY_001"})
    assert res.status_code == 200
    assert res.json()["status"] == "COMPLETED"
