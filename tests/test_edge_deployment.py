"""Automated verification suite for AeroPulse-X edge deployment infrastructure."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.edge import UAVEdgeNode, EdgeHealthSummary
from app.can_bus import CANBusInterface, CANFrame


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_edge_deployment_files_exist():
    """Verify all embedded deployment assets are present and non-empty."""
    deploy_dir = REPO_ROOT / "deploy" / "edge"
    assert deploy_dir.exists() and deploy_dir.is_dir()

    required_files = [
        "requirements-edge.txt",
        "edge_config.json",
        "start_edge_node.sh",
        "health_check.sh",
        "README.md",
    ]

    for fname in required_files:
        fpath = deploy_dir / fname
        assert fpath.exists(), f"Missing deployment file: {fname}"
        assert fpath.stat().st_size > 0, f"Empty deployment file: {fname}"


def test_edge_config_schema():
    """Verify edge_config.json contains mandatory runtime parameters."""
    cfg_file = REPO_ROOT / "deploy" / "edge" / "edge_config.json"
    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    assert "node_id" in cfg
    assert "drone_id" in cfg
    assert "can_transport" in cfg
    assert cfg["can_transport"]["bitrate"] == 500000
    assert "runtime" in cfg
    assert cfg["runtime"]["telemetry_rate_hz"] >= 20.0
    assert "thresholds" in cfg
    assert cfg["thresholds"]["sensor_trust_min_pass"] == 50.0


def test_requirements_edge_minimal():
    """Verify edge requirements exclude heavy machine learning training packages."""
    req_file = REPO_ROOT / "deploy" / "edge" / "requirements-edge.txt"
    lines = [line.strip().lower() for line in req_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]
    content = " ".join(lines)

    # Must contain essential runtimes
    assert "numpy" in content
    assert "fastapi" in content
    assert "uvicorn" in content

    # Must NOT contain heavy desktop/training packages
    assert "torch" not in content
    assert "tensorflow" not in content
    assert "scikit-learn" not in content


def test_edge_node_can_frame_processing():
    """Verify UAVEdgeNode can ingest and process raw CAN 2.0B frame lists."""
    node = UAVEdgeNode()
    can = CANBusInterface()

    sample = dict(node.twin.expected("CRUISE"))
    sample.update({
        "Operating_State": "CRUISE",
        "Load": 0.60,
        "Vibration": 1.25,
    })

    frames = can.encode_telemetry(sample)
    summary = node.process_can_frames(frames)

    assert isinstance(summary, EdgeHealthSummary)
    assert summary.health_state == "Normal"
    assert summary.anomaly_detected is False
    assert summary.sensor_trust_score >= 80.0
    assert summary.edge_latency_ms < 5.0
    assert summary.stage_latencies_us is not None


def test_edge_malformed_telemetry_resilience():
    """Verify UAVEdgeNode gracefully handles nulls, NaNs, and missing fields."""
    node = UAVEdgeNode()

    # Missing all standard fields
    empty_summary = node.process_telemetry({})
    assert empty_summary.health_state is not None
    assert empty_summary.edge_latency_ms < 5.0

    # Injected NaNs and None
    corrupt_sample = {
        "Engine_RPM": float("nan"),
        "CHT": None,
        "Oil_Temp": "INVALID_STR",
        "Fuel_Flow": float("inf"),
        "Operating_State": "UNKNOWN_STATE",
    }
    corrupt_summary = node.process_telemetry(corrupt_sample)
    assert corrupt_summary.health_state is not None
    assert corrupt_summary.local_safety_action is not None


def test_edge_validation_api_endpoint():
    """Verify GET /api/v1/validation/edge returns compliant status and hardware info."""
    client = TestClient(app)
    response = client.get("/api/v1/validation/edge")

    assert response.status_code == 200
    data = response.json()
    assert "hardware" in data
    assert "machine" in data["hardware"]
    assert "hardware_classification" in data["hardware"]
    assert "complete_pipeline_latency_ms" in data
    assert "mean" in data["complete_pipeline_latency_ms"]
    assert "throughput_samples_per_sec" in data
    assert "desktop_benchmark_status" in data
    assert data["desktop_benchmark_status"] == "PASS"
    assert "embedded_benchmark_status" in data
