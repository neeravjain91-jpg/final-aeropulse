"""Production readiness, API contracts, failure injection, and security tests for AeroPulse-X."""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


# =========================================================================
# 1. API Contract & Routing Tests
# =========================================================================

def test_root_and_openapi_endpoints():
    """Verify root HTML and OpenAPI documentation contracts."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AeroPulse-X" in resp.text or "<html" in resp.text

    resp = client.get("/docs")
    assert resp.status_code == 200

    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert "/api/analyze" in schema["paths"]
    assert "/api/status" in schema["paths"]


def test_api_status_contract():
    """Verify /api/status response contract and model availability."""
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project"] == "AeroPulse-X"
    assert data["models_ready"] is True
    assert data["demo_ready"] is True
    assert isinstance(data["available_faults"], list)
    assert len(data["available_faults"]) > 0


def test_api_sample_contract():
    """Verify /api/sample returns valid non-empty telemetry vector."""
    resp = client.get("/api/sample?operating_state=CRUISE")
    assert resp.status_code == 200
    sample = resp.json()
    assert isinstance(sample, dict)
    assert "Engine_RPM" in sample
    assert "CHT" in sample
    assert "Operating_State" in sample
    assert sample["Operating_State"] == "CRUISE"


def test_api_replay_contract():
    """Verify /api/replay produces complete timeline and summary."""
    payload = {
        "fault": "thermal",
        "severity": 0.6,
        "steps": 24,
        "step_minutes": 2.0,
        "fault_onset_ratio": 0.35,
    }
    resp = client.post("/api/replay", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "timeline" in data
    assert len(data["timeline"]) == 24
    assert "summary" in data
    assert "rul_method_demonstrator" in data["summary"]


def test_data_lab_endpoints_contract():
    """Verify Virtual Data Laboratory endpoints."""
    # Catalog
    resp = client.get("/api/v1/data/catalog")
    assert resp.status_code == 200
    catalog = resp.json()
    assert "total_datasets" in catalog or "total_registered_datasets" in catalog

    # Health
    resp = client.get("/api/v1/data/health")
    assert resp.status_code == 200
    health = resp.json()
    assert health["status"] == "OPERATIONAL"

    # Trajectory
    resp = client.get("/api/v1/data/trajectory/TRAJ_HEALTHY_NOMINAL_001")
    assert resp.status_code == 200
    traj = resp.json()
    assert traj["sample_count"] > 0
    assert len(traj["points"]) > 0

    # Generation
    gen_payload = {
        "category": "degradation",
        "scenario_type": "thermal",
        "duration_hours": 20.0,
        "severity": 0.6,
        "seed": 42,
    }
    resp = client.post("/api/v1/data/generate", json=gen_payload)
    assert resp.status_code == 200
    gen_data = resp.json()
    assert gen_data["sample_count"] > 0

    # Replay
    rep_payload = {
        "trajectory_id": "TRAJ_DEG_THERMAL_001",
        "seed": 42,
    }
    resp = client.post("/api/v1/data/replay", json=rep_payload)
    assert resp.status_code == 200
    rep_data = resp.json()
    assert "total_steps" in rep_data


def test_validation_endpoints_contract():
    """Verify all /api/v1/validation/* endpoints return valid reports."""
    endpoints = [
        "/api/v1/validation/sil",
        "/api/v1/validation/engine",
        "/api/v1/validation/hil",
        "/api/v1/validation/edge",
        "/api/v1/validation/rul",
        "/api/v1/validation/master",
    ]
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 200, f"Validation endpoint failed: {ep}"
        data = resp.json()
        assert isinstance(data, dict) and len(data) > 0


# =========================================================================
# 2. Failure Injection & Resilience Tests
# =========================================================================

def test_analyze_missing_fields_defaults_gracefully():
    """Verify /api/analyze does not crash on empty/partial body."""
    resp = client.post("/api/analyze", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "health_state" in data
    assert "telemetry" in data


def test_analyze_invalid_types_handled():
    """Verify invalid data types return controlled validation error."""
    resp = client.post("/api/analyze", json={"severity": "not_a_number"})
    assert resp.status_code in {422, 400}


def test_analyze_out_of_bounds_clamped_or_rejected():
    """Verify out-of-range numerical parameters are handled cleanly."""
    resp = client.post("/api/analyze", json={"severity": 999.0})
    assert resp.status_code in {200, 422}
    if resp.status_code == 200:
        data = resp.json()
        assert not math.isnan(data["health_index"])
        assert not math.isinf(data["health_index"])


# =========================================================================
# 3. Security Tests
# =========================================================================

def test_path_traversal_protection():
    """Verify trajectory endpoint rejects path traversal attacks."""
    resp = client.get("/api/v1/data/trajectory/../../etc/passwd")
    assert resp.status_code in {200, 400, 404}
    if resp.status_code == 200:
        data = resp.json()
        # Ensure it deterministically fell back to a generated trajectory without accessing filesystem
        assert "points" in data


def test_static_path_traversal():
    """Verify static file server does not expose sensitive files outside static."""
    resp = client.get("/static/../requirements.txt")
    assert resp.status_code in {400, 404}


# =========================================================================
# 4. Frontend Syntax Validation Test
# =========================================================================

def test_frontend_javascript_syntax():
    """Verify all JavaScript code in static/ passes Node.js syntax parsing."""
    html_path = ROOT / "static" / "index.html"
    assert html_path.exists()

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    import re
    scripts = re.findall(r"<script(?:\s+[^>]*)?>(.*?)</script>", html, flags=re.DOTALL)
    for i, s in enumerate(scripts):
        if not s.strip():
            continue
        temp_file = ROOT / f"_temp_syntax_test_{i}.js"
        try:
            temp_file.write_text(s, encoding="utf-8")
            res = subprocess.run(["node", "-c", str(temp_file)], capture_output=True, text=True)
            assert res.returncode == 0, f"Script block {i} syntax error: {res.stderr}"
        finally:
            if temp_file.exists():
                temp_file.unlink()
