from __future__ import annotations

import asyncio
import json

from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import (
    DATA_SAMPLE_DIR,
    MODEL_DIR,
    PROJECT_NAME,
    PROJECT_VERSION,
    REQUIRED_MODEL_FILES,
    STATIC_DIR,
)
from .engine_model import ReducedOrderPistonEngine
from .inference import AeroTwinAI
from .mission_whatif import MissionScenario
from .mission_whatif_rul import MissionWhatIfRUL
from .navigation import (
    DEFAULT_MISSION_WAYPOINTS,
    PRESET_MISSIONS,
    MissionWaypoint,
    SimulatedGPSSource,
)
from .replay import run_replay
from .risk import mission_risk
from .simulator import FAULTS, inject_fault, mission_adjust
from .telemetry import telemetry_from_engine
from .uav_mission import UAVMissionSimulator
from .vibration import VibrationAI, load_demo as load_vibration_demo
from .validation import AeroPulseValidator


_GPS = SimulatedGPSSource()


app = FastAPI(
    title=f"{PROJECT_NAME} / AeroTwin-MALE",
    version=PROJECT_VERSION,
    description=(
        "SIH26054 mission-aware Digital Twin demonstrator "
        "for UAV piston-engine health monitoring."
    ),
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


_ai = None
_ai_error = None
_vibration_ai = None
_vibration_demo = None
_demo = None

_ENGINE = ReducedOrderPistonEngine()


def _load_assets() -> None:
    global _ai, _ai_error, _vibration_ai, _vibration_demo, _demo

    # Auto-bootstrap model assets if missing
    try:
        from scripts.train_models import main as train_models_main
        train_models_main()
    except Exception as exc:
        pass

    try:
        _ai = AeroTwinAI()
        _ai_error = None
    except Exception as exc:
        _ai = None
        _ai_error = str(exc)

    try:
        _vibration_ai = VibrationAI()
    except Exception:
        _vibration_ai = None

    _vibration_demo = load_vibration_demo()

    path = DATA_SAMPLE_DIR / "aces_demo.csv"

    if path.exists():
        _demo = pd.read_csv(path)
    else:
        _demo = None


_load_assets()


class Scenario(BaseModel):
    fault: str = "none"
    severity: float = Field(0.6, ge=0, le=1)
    altitude_ft: float = Field(8000, ge=0, le=60000)
    ambient_c: float = Field(35, ge=-60, le=80)
    duration_h: float = Field(6, gt=0, le=48)
    rapid_throttle: bool = False
    operating_state: str = "CRUISE"
    simulation_mode: str = "automatic"
    waypoints: Optional[List[Dict[str, Any]]] = None
    preset: Optional[str] = None


class FlightPlanRequest(BaseModel):
    waypoints: List[Dict[str, Any]] = Field(default_factory=list)
    ground_temp_c: float = 30.0
    hot_weather_bias: float = 0.0


class ReplayScenario(Scenario):
    steps: int = Field(48, ge=12, le=180)
    step_minutes: float = Field(5.0, ge=0.5, le=60)
    fault_onset_ratio: float = Field(0.35, ge=0, le=0.95)


class WhatIfRequest(BaseModel):
    baseline: Scenario
    alternative: Scenario


class LiveMissionConfig(Scenario):
    steps: int = Field(120, ge=12, le=360)
    playback_interval_s: float = Field(0.25, ge=0.05, le=2.0)
    fault_onset_ratio: float = Field(0.35, ge=0, le=0.95)

    max_altitude_ft: float = Field(
        20000,
        ge=3000,
        le=60000,
    )

    cruise_altitude_ft: float = Field(
        8000,
        ge=1000,
        le=60000,
    )

    hot_weather: bool = False
    mission_mode: str = "standard"


Scenario.model_rebuild()
FlightPlanRequest.model_rebuild()
ReplayScenario.model_rebuild()
WhatIfRequest.model_rebuild()
LiveMissionConfig.model_rebuild()


def _require_ai() -> AeroTwinAI:
    if _ai is None:
        raise HTTPException(
            503,
            detail={
                "message": (
                    "Model assets are not ready. "
                    "Train the models first."
                ),
                "command": (
                    'python scripts/train_models.py '
                    '--data-dir "C:\\path\\to\\FINAL_DATASET"'
                ),
                "error": _ai_error,
            },
        )

    return _ai


def _require_demo() -> pd.DataFrame:
    if _demo is None or _demo.empty:
        raise HTTPException(
            503,
            detail={
                "message": (
                    "Demo telemetry sample is missing."
                ),
                "command": (
                    'python scripts/train_models.py '
                    '--data-dir "C:\\path\\to\\FINAL_DATASET"'
                ),
            },
        )

    return _demo


def _clean_row(row: dict) -> dict:
    row = dict(row)

    row.pop("Robust_Anomaly_Score", None)
    row.pop("Health_State", None)

    return {
        key: (
            str(value)
            if key == "Operating_State"
            else float(value)
        )
        for key, value in row.items()
    }


def _base_sample(
    operating_state: str,
) -> tuple[dict, str | None]:

    candidates = _require_demo()

    if "Health_State" in candidates.columns:
        normal = candidates[
            candidates["Health_State"] == "Normal"
        ]

        if not normal.empty:
            candidates = normal

    state_rows = candidates[
        candidates["Operating_State"].astype(str)
        == str(operating_state)
    ]

    if not state_rows.empty:
        candidates = state_rows

    if "Robust_Anomaly_Score" in candidates.columns:
        candidates = candidates.sort_values(
            "Robust_Anomaly_Score"
        )

    row = candidates.iloc[0].to_dict()

    source = (
        str(row.get("Health_State"))
        if "Health_State" in row
        else None
    )

    return _clean_row(row), source


def _mission_scenario(
    model: Scenario,
    name: str,
):
    return MissionScenario(
        name=name,
        altitude_ft=model.altitude_ft,
        ambient_c=model.ambient_c,
        duration_h=model.duration_h,
        rapid_throttle=model.rapid_throttle,
    )


def _round_telemetry(data: dict) -> dict:
    result = {}

    for key, value in data.items():

        if isinstance(value, bool):
            result[key] = value

        elif isinstance(value, (int, float)):
            result[key] = round(
                float(value),
                4,
            )

        else:
            result[key] = value

    return result


def _build_live_engine_data(
    mission_point,
) -> dict:
    """
    Generate engine telemetry from the reduced-order
    piston-engine model.

    This is the simulation equivalent of an engine ECU
    producing sensor values.
    """

    throttle = max(
        0.0,
        min(
            1.0,
            float(
                mission_point.throttle
            ),
        ),
    )

    load = max(
        0.05,
        min(
            1.15,
            float(
                mission_point.load
            ),
        ),
    )

    phase = str(getattr(mission_point, "mission_phase", "CRUISE")).upper()

    if phase in ["GROUND", "PREFLIGHT", "OFF", "STATIONARY"]:
        run_state = "ENGINE_OFF"
        rpm = 0.0
    elif phase in ["STARTING", "CRANKING", "IGNITION"]:
        run_state = "ENGINE_STARTING"
        rpm = 800.0
    elif phase in ["STOPPING", "COOLDOWN", "SHUTDOWN"]:
        run_state = "ENGINE_STOPPING"
        rpm = 400.0
    else:
        run_state = "ENGINE_RUNNING"
        rpm = 3000.0 * (
            0.92 + 0.12 * throttle
        )

    if run_state == "ENGINE_OFF":
        data = _ENGINE.simulate(
            rpm=0.0,
            throttle=0.0,
            altitude_ft=float(
                mission_point.altitude_ft
            ),
            ambient_c=float(
                mission_point.ambient_c
            ),
            load=0.0,
        )
        data["Engine_RPM"] = 0.0
        data["Fuel_Flow"] = 0.0
        data["Brake_Power_kW"] = 0.0
        data["Indicated_Power_kW"] = 0.0
        data["Vibration"] = 0.0
        data["engine_run_state"] = "ENGINE_OFF"
        return data

    data = _ENGINE.simulate(
        rpm=rpm,
        throttle=throttle,
        altitude_ft=float(
            mission_point.altitude_ft
        ),
        ambient_c=float(
            mission_point.ambient_c
        ),
        load=load,
    )
    if run_state in ["ENGINE_STARTING", "ENGINE_STOPPING"]:
        data["Engine_RPM"] = round(rpm, 1)
        data["Brake_Power_kW"] = 0.0
    data["engine_run_state"] = run_state
    return data


def _apply_live_fault(
    telemetry: dict,
    config: LiveMissionConfig,
    step: int,
) -> tuple[dict, float]:

    fault = str(
        config.fault
    ).lower()

    if fault == "none":
        return telemetry, 0.0

    total_steps = int(
        config.steps
    )

    onset_step = int(
        total_steps
        * float(
            config.fault_onset_ratio
        )
    )

    if step < onset_step:
        return telemetry, 0.0

    progress = (
        (
            step
            - onset_step
            + 1
        )
        / max(
            1,
            total_steps
            - onset_step,
        )
    )

    progress = max(
        0.0,
        min(
            1.0,
            progress,
        ),
    )

    effective_severity = (
        float(config.severity)
        * progress
    )

    altered = inject_fault(
        telemetry,
        fault,
        effective_severity,
    )

    altered[
        "Degradation_Severity"
    ] = effective_severity

    return altered, effective_severity


@app.get(
    "/",
    response_class=HTMLResponse,
)
def home():
    return (
        STATIC_DIR / "index.html"
    ).read_text(
        encoding="utf-8"
    )


@app.get("/api/status")
def status():

    return {
        "project": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "models_ready": _ai is not None,
        "model_files": {
            name: (
                MODEL_DIR / name
            ).exists()
            for name in REQUIRED_MODEL_FILES
        },
        "demo_ready": (
            _demo is not None
            and not _demo.empty
        ),
        "available_faults": sorted(
            FAULTS
        ),
        "operating_states": (
            _ai.twin.operating_states
            if _ai
            else []
        ),
        "metrics_ready": (
            MODEL_DIR / "metrics.json"
        ).exists(),
        "vibration_model_ready": (
            _vibration_ai is not None
        ),
        "vibration_demo_ready": (
            _vibration_demo is not None
            and not _vibration_demo.empty
        ),
        "setup_error": _ai_error,
        "telemetry_interface": {
            "version": "1.0",
            "schema": "UAVTelemetry",
            "source": "uav_simulator",
            "hardware_ready_interface": True,
        },
        "capabilities": [
            "healthy-reference Digital Twin",
            "four-state AI health monitoring",
            "unsupervised anomaly detection",
            "sensor-trust assessment",
            "fault evidence and maintenance advisory",
            "mission-condition simulation",
            "UAV mission simulation",
            "hardware-equivalent telemetry schema",
            "simulated real-time telemetry",
            "live WebSocket telemetry",
            "mission replay / early-warning comparison",
            "prototype degradation and RUL methodology",
        ],
        "safety_note": (
            "Research/SIH prototype; not certified "
            "for flight-safety or airworthiness decisions."
        ),
    }


@app.post("/api/reload")
def reload_assets():
    _load_assets()
    return status()


@app.get("/api/v1/validation/sil")
def validation_sil():
    """Runs Phase C2 Virtual Hardware and Software-in-the-Loop emulation validation suite."""
    return AeroPulseValidator().validate_virtual_hardware_sil()


@app.get("/api/v1/validation/master")
def validation_master():
    """Runs formal master validation across all project boundaries."""
    return AeroPulseValidator().generate_master_report()


@app.get("/api/v1/validation/engine")
def validation_engine():
    """Runs Phase A engine model validation harness."""
    return AeroPulseValidator().validate_engine_model()


@app.get("/api/v1/validation/hil")
def validation_hil():
    """Runs Phase B Virtual ECU/FADEC CAN HIL validation harness."""
    return AeroPulseValidator().validate_virtual_ecu_fadec_hil()


@app.get("/api/v1/validation/edge")
def validation_edge():
    """Runs Phase C edge compute deployment and benchmarking suite."""
    return AeroPulseValidator().validate_edge_compute_embedded()


@app.get("/api/v1/validation/rul")
def validation_rul():
    """Runs Phase D RUL and prognostics validation suite."""
    return AeroPulseValidator().validate_rul_prognostics_full()


# =========================================================================
# VIRTUAL DATA LABORATORY & CANONICAL TELEMETRY APIS
# =========================================================================

class GenerateDataRequest(BaseModel):
    category: str = Field("degradation", description="healthy, degradation, sensor_fault, mission")
    scenario_type: str = Field("thermal", description="thermal, lubrication, mechanical, injector, misfire, electrical, compound, bias, drift, noise")
    duration_hours: float = Field(30.0, ge=0.5, le=100.0)
    ambient_c: float = Field(25.0, ge=-50.0, le=70.0)
    altitude_ft: float = Field(5000.0, ge=0.0, le=45000.0)
    severity: float = Field(0.60, ge=0.0, le=1.0)
    seed: Optional[int] = 42


from .data_engine import FAILURE_HEALTH_THRESHOLD, VirtualDataLabEngine
from .dataset_registry import DatasetRegistry
from .data_validator import DataQualityValidator
from .data_replay import ClosedLoopReplayEngine


class ReplayDataRequest(BaseModel):
    trajectory_id: Optional[str] = None
    custom_points: Optional[List[Dict[str, Any]]] = None
    seed: Optional[int] = 42


@app.get("/api/v1/data/catalog")
def get_data_catalog():
    """Returns dataset registry metadata and provenance for all primary and proxy datasets."""
    return DatasetRegistry().get_summary()


@app.get("/api/v1/data/health")
def get_data_health():
    """Returns operational status of the Virtual Data Laboratory generation and replay engine."""
    return {
        "status": "OPERATIONAL",
        "schema_version": "2.0.0",
        "engine": "AeroPulse-X Virtual Data Laboratory",
        "capabilities": [
            "Canonical Telemetry Schema v2.0",
            "Multi-Phase Healthy Trajectory Generation",
            "Continuous Progressive Degradation Kinetics (H_failure=35.0)",
            "Physically Coupled Fault Injection",
            "Isolated Transducer Sensor Faults",
            "Mission & Environmental Dynamic Coupling",
            "Virtual CAN 2.0B Communication Traces",
            "Virtual ECU / FADEC Supervisory Logging",
            "Virtual Flight Computer Resource Scheduling",
            "Trajectory-Level Zero-Leakage Splitting",
            "Closed-Loop Full Pipeline Replay",
        ],
        "compliance": "NASA PCoE & IEEE PHM Verification Standards (Software-Only Demonstrator)",
    }


@app.get("/api/v1/data/trajectory/{trajectory_id}")
def get_data_trajectory(trajectory_id: str, seed: int = 42):
    """Retrieves or deterministically generates canonical time-series points for a trajectory ID."""
    from .data_engine import VirtualDataLabEngine
    engine = VirtualDataLabEngine(master_seed=seed)
    tid = trajectory_id.upper()

    if "HEALTHY" in tid or "NOMINAL" in tid:
        pts = engine.generate_healthy_trajectory(trajectory_id=trajectory_id, seed=seed)
    elif "SENS" in tid or "SENSOR" in tid:
        pts = engine.generate_sensor_fault_trajectory(trajectory_id=trajectory_id, seed=seed)
    elif "MSN" in tid or "MISSION" in tid:
        pts = engine.generate_mission_trajectory(trajectory_id=trajectory_id, seed=seed)
    else:
        # Default to degradation
        mode = "thermal"
        for m in ("thermal", "lubrication", "mechanical", "injector", "misfire", "electrical", "compound"):
            if m.upper() in tid:
                mode = m
                break
        pts = engine.generate_degradation_trajectory(trajectory_id=trajectory_id, failure_mode=mode, seed=seed)

    return {
        "trajectory_id": trajectory_id,
        "sample_count": len(pts),
        "schema_version": "2.0.0",
        "points": [pt.to_dict() for pt in pts],
    }


@app.post("/api/v1/data/generate")
def generate_custom_data(req: GenerateDataRequest):
    """Generates custom multivariate time-series trajectory based on user request parameters."""
    from .data_engine import VirtualDataLabEngine
    engine = VirtualDataLabEngine(master_seed=req.seed or 42)
    tid = f"TRAJ_CUSTOM_{req.category.upper()}_{req.scenario_type.upper()}_001"

    if req.category == "healthy":
        pts = engine.generate_healthy_trajectory(
            trajectory_id=tid,
            duration_hours=req.duration_hours,
            ambient_c=req.ambient_c,
            seed=req.seed,
        )
    elif req.category == "sensor_fault":
        pts = engine.generate_sensor_fault_trajectory(
            trajectory_id=tid,
            sensor_fault_type=req.scenario_type,
            duration_hours=req.duration_hours,
            severity=req.severity,
            seed=req.seed,
        )
    elif req.category == "mission":
        pts = engine.generate_mission_trajectory(
            trajectory_id=tid,
            mission_type=req.scenario_type,
            seed=req.seed,
        )
    else:
        pts = engine.generate_degradation_trajectory(
            trajectory_id=tid,
            failure_mode=req.scenario_type,
            duration_hours=req.duration_hours,
            altitude_ft=req.altitude_ft,
            ambient_c=req.ambient_c,
            seed=req.seed,
        )

    return {
        "trajectory_id": tid,
        "category": req.category,
        "scenario_type": req.scenario_type,
        "sample_count": len(pts),
        "points": [pt.to_dict() for pt in pts],
    }


@app.post("/api/v1/data/replay")
def replay_data_trajectory(req: ReplayDataRequest):
    """Executes closed-loop replay through the complete SIL avionics and digital twin pipeline."""
    from .data_engine import VirtualDataLabEngine
    from .data_schema import CanonicalTelemetryPoint
    from .data_replay import ClosedLoopReplayEngine

    engine = VirtualDataLabEngine(master_seed=req.seed or 42)
    replay_eng = ClosedLoopReplayEngine(master_seed=req.seed or 42)

    if req.custom_points:
        points = [CanonicalTelemetryPoint.from_dict(p) for p in req.custom_points]
    else:
        tid = req.trajectory_id or "TRAJ_DEG_THERMAL_001"
        pts_dict = get_data_trajectory(trajectory_id=tid, seed=req.seed or 42)
        points = [CanonicalTelemetryPoint.from_dict(p) for p in pts_dict["points"]]

    summary = replay_eng.replay_trajectory(points)
    return summary.to_dict()


@app.get("/api/v1/data/quality")
def audit_data_quality(seed: int = 42):
    """Runs automated data-quality validation and trajectory leakage audit across generated corpus."""
    from .data_engine import VirtualDataLabEngine
    from .data_validator import DataQualityValidator

    engine = VirtualDataLabEngine(master_seed=seed)
    corpus = engine.generate_master_corpus(num_healthy=10, num_degradation=15, num_sensor_faults=8, num_missions=5, master_seed=seed)
    train_dict, test_dict = engine.split_corpus_trajectories(corpus, train_ratio=0.70, seed=seed)

    report = DataQualityValidator.audit_corpus(corpus=corpus, train_dict=train_dict, test_dict=test_dict)
    return report.to_dict()


@app.get("/api/v1/data/statistics")
def get_data_statistics(seed: int = 42):
    """Computes statistical telemetry distributions and actual materialized corpus counts."""
    from .data_engine import VirtualDataLabEngine
    engine = VirtualDataLabEngine(master_seed=seed)
    stats = engine.get_materialized_corpus_statistics(master_seed=seed)
    
    corpus = engine.generate_master_corpus(
        num_healthy=20,
        num_degradation=35,
        num_sensor_faults=15,
        num_missions=10,
        num_can_faults=10,
        master_seed=seed,
    )
    all_points = []
    for pts in corpus.values():
        all_points.extend(pts)

    rpms = [p.RPM for p in all_points]
    chts = [p.CHT for p in all_points]
    oil_press = [p.oil_pressure for p in all_points]
    healths = [p.health_index for p in all_points]
    voltages = [p.bus_voltage for p in all_points]

    stats["metrics"] = {
        "RPM": {"mean": round(float(np.mean(rpms)), 1), "std": round(float(np.std(rpms)), 1), "min": round(float(np.min(rpms)), 1), "max": round(float(np.max(rpms)), 1)},
        "CHT_degC": {"mean": round(float(np.mean(chts)), 1), "std": round(float(np.std(chts)), 1), "min": round(float(np.min(chts)), 1), "max": round(float(np.max(chts)), 1)},
        "Oil_Pressure_psi": {"mean": round(float(np.mean(oil_press)), 1), "std": round(float(np.std(oil_press)), 1), "min": round(float(np.min(oil_press)), 1), "max": round(float(np.max(oil_press)), 1)},
        "Health_Index": {"mean": round(float(np.mean(healths)), 1), "std": round(float(np.std(healths)), 1), "min": round(float(np.min(healths)), 1), "max": round(float(np.max(healths)), 1)},
        "Bus_Voltage_V": {"mean": round(float(np.mean(voltages)), 2), "std": round(float(np.std(voltages)), 2), "min": round(float(np.min(voltages)), 2), "max": round(float(np.max(voltages)), 2)},
    }
    return stats


@app.get("/api/v1/data/ground-truth/{trajectory_id}")
def get_trajectory_ground_truth(trajectory_id: str, seed: int = 42):
    """Returns exact failure timestamp, RUL curve, and degradation kinetic parameters for a trajectory."""
    data = get_data_trajectory(trajectory_id=trajectory_id, seed=seed)
    points = data["points"]
    
    gt_curve = []
    failure_time = None
    failure_mode = "none"

    for p in points:
        if p.get("true_failure_time") is not None and failure_time is None:
            failure_time = p["true_failure_time"]
            failure_mode = p.get("failure_mode", "thermal")
        gt_curve.append({
            "timestamp_s": p["timestamp"],
            "time_hours": round(p["timestamp"] / 3600.0, 3),
            "health_index": p["health_index"],
            "true_RUL_hours": p["true_RUL"],
            "predicted_RUL_hours": p["predicted_RUL"],
            "RUL_lower_hours": p["RUL_lower"],
            "RUL_upper_hours": p["RUL_upper"],
        })

    return {
        "trajectory_id": trajectory_id,
        "failure_health_threshold": FAILURE_HEALTH_THRESHOLD,
        "true_failure_time_hours": failure_time,
        "failure_mode": failure_mode,
        "ground_truth_methodology": "Mathematical ODE forward integration to H(t) = 35.0 (y_true = max(0, t_failure - t))",
        "sample_count": len(gt_curve),
        "ground_truth_curve": gt_curve,
    }


@app.get("/api/sample")
def sample(
    operating_state: str = "CRUISE",
):
    return _base_sample(
        operating_state
    )[0]


@app.post("/api/analyze")
def analyze(
    scenario: Scenario,
):

    ai = _require_ai()

    if scenario.fault not in FAULTS:
        raise HTTPException(
            400,
            detail=(
                f"Unsupported fault: "
                f"{scenario.fault}"
            ),
        )

    base, source = _base_sample(
        scenario.operating_state
    )

    mission = mission_adjust(
        base,
        scenario.altitude_ft,
        scenario.ambient_c,
        scenario.duration_h,
        scenario.rapid_throttle,
    )

    altered = inject_fault(
        mission,
        scenario.fault,
        scenario.severity,
    )

    context = scenario.model_dump()

    result = ai.analyze(
        altered,
        context=context,
    )

    risk = mission_risk(
        result,
        context,
    )

    if scenario.waypoints and len(scenario.waypoints) >= 2:
        gps = SimulatedGPSSource(
            waypoints=scenario.waypoints,
            ground_temp_c=float(scenario.ambient_c),
        )
    else:
        gps = _GPS

    uav_pos = gps.get_position(
        progress_ratio=0.15,
        mission_context={
            "altitude_ft": float(scenario.altitude_ft),
            "throttle": 0.60,
            "mission_phase": "CRUISE" if scenario.operating_state == "CRUISE" else "HIGH",
        },
    )

    result.update(
        {
            "telemetry": altered,
            "source_reference_state": source,
            "scenario": context,
            "mission_risk": risk,
            "mission_risk_score": risk["score"],
            "mission_risk_level": risk["level"],
            "uav": uav_pos.to_dict(),
            "waypoints": [wp.to_dict() for wp in gps.waypoints],
            "planned_route": [[wp.latitude, wp.longitude] for wp in gps.waypoints],
            "home_base": gps.waypoints[0].to_dict(),
            "flight_plan_summary": gps.get_flight_plan_summary(),
        }
    )

    return result


@app.get("/api/mission/presets")
def mission_presets():
    """Returns all available preset mission flight plans."""
    return {
        k: {
            "name": v["name"],
            "description": v["description"],
            "waypoints": [wp.to_dict() for wp in v["waypoints"]],
        }
        for k, v in PRESET_MISSIONS.items()
    }


@app.post("/api/mission/plan")
def calculate_flight_plan(request: FlightPlanRequest):
    """Calculates full 3D flight plan metrics, distance, duration, and route summary."""
    gps = SimulatedGPSSource(
        waypoints=[MissionWaypoint.from_dict(w) for w in request.waypoints],
        ground_temp_c=request.ground_temp_c,
        hot_weather_bias=request.hot_weather_bias,
    )
    return gps.get_flight_plan_summary()


@app.get("/api/mission/waypoints")
def mission_waypoints(preset: str | None = None):
    """Returns planned 3D mission waypoints, route coordinates, and base coordinates."""
    if preset and preset in PRESET_MISSIONS:
        gps = SimulatedGPSSource(PRESET_MISSIONS[preset]["waypoints"])
    else:
        gps = _GPS
    return gps.get_flight_plan_summary()


@app.post("/api/mission-whatif-rul")
def mission_whatif_rul(
    request: WhatIfRequest,
):

    _require_ai()

    base, source = _base_sample(
        request.baseline.operating_state
    )

    engine = MissionWhatIfRUL(
        {
            "injector": 0.05,
            "lubrication": 0.04,
            "thermal": 0.03,
            "mechanical": 0.02,
            "electrical": 0.01,
            "sensor": 0.02,
        }
    )

    result = engine.compare(
        base,
        _mission_scenario(
            request.baseline,
            "baseline",
        ),
        _mission_scenario(
            request.alternative,
            "alternative",
        ),
    )

    result[
        "source_reference_state"
    ] = source

    return result


@app.post("/api/replay")
def replay(
    scenario: ReplayScenario,
):

    ai = _require_ai()

    base, source = _base_sample(
        scenario.operating_state
    )

    payload = scenario.model_dump()

    result = run_replay(
        ai,
        base,
        payload,
        scenario.steps,
        scenario.step_minutes,
        scenario.fault_onset_ratio,
    )

    result["scenario"] = payload

    result[
        "source_reference_state"
    ] = source

    result["disclaimer"] = (
        "Mission replay, early-warning and RUL "
        "outputs are prototype method demonstrations, "
        "not operational airworthiness determinations."
    )

    return result


@app.get("/api/metrics")
def metrics():

    path = MODEL_DIR / "metrics.json"

    if not path.exists():
        raise HTTPException(
            404,
            detail=(
                "Train models first; "
                "metrics.json is missing."
            ),
        )

    return json.loads(
        path.read_text()
    )


@app.get("/api/model-manifest")
def model_manifest():

    path = MODEL_DIR / "model_manifest.json"

    if not path.exists():
        raise HTTPException(
            404,
            detail=(
                "Model manifest is not available; "
                "retrain with the current training script."
            ),
        )

    return json.loads(
        path.read_text()
    )


@app.get("/api/vibration/demo")
def vibration_demo(
    condition: str = "Normal",
):

    if (
        _vibration_ai is None
        or _vibration_demo is None
        or _vibration_demo.empty
    ):
        raise HTTPException(
            503,
            detail=(
                "CWRU vibration model/demo is not "
                "available. Retrain models first."
            ),
        )

    candidates = _vibration_demo

    if "Fault" in candidates.columns:

        matched = candidates[
            candidates["Fault"]
            .astype(str)
            .str.lower()
            == str(condition).lower()
        ]

        if not matched.empty:
            candidates = matched

    row = candidates.iloc[0].to_dict()

    features = {
        feature: float(row[feature])
        for feature in _vibration_ai.features
    }

    result = _vibration_ai.analyze(
        features
    )

    result["input_features"] = features

    result["source_label"] = str(
        row.get(
            "Fault",
            "unknown",
        )
    )

    return result


@app.get("/api/v1/validation/engine-model")
def engine_model_validation():
    """Returns formal engine model validation, provenance, sensitivity, and uncertainty metrics."""
    from .engine_validation import EngineModelValidator

    validator = EngineModelValidator(_ENGINE)
    return validator.generate_full_validation_summary()


@app.get("/api/v1/validation/ecu-fadec-hil")
def ecu_fadec_hil_validation():
    """Returns formal Virtual ECU/FADEC CAN HIL validation scenario matrix and latency statistics."""
    from .can_hil import CANHILSimulator

    simulator = CANHILSimulator()
    return simulator.run_master_hil_validation_suite()


@app.get("/api/v1/validation/edge")
def edge_compute_validation():
    """Returns edge compute deployment profile, stage latency percentiles, throughput, and hardware classification."""
    from .edge_benchmark import run_benchmark_and_get_summary

    report = run_benchmark_and_get_summary(samples=1000, warmup=100)
    return report.to_dict()


@app.websocket("/ws/telemetry")
async def telemetry_stream(
    websocket: WebSocket,
):
    """
    Live simulated UAV telemetry pipeline.

    UAV mission
        ↓
    Engine simulation
        ↓
    UAVTelemetry hardware-equivalent packet
        ↓
    Fault injection
        ↓
    Digital Twin
        ↓
    AI/ML
        ↓
    Risk / advisory
        ↓
    WebSocket
        ↓
    GCS dashboard
    """

    await websocket.accept()

    try:

        config = await websocket.receive_json()

        playback_interval = max(
            0.05,
            min(
                float(
                    config.pop(
                        "playback_interval_s",
                        0.25,
                    )
                ),
                2.0,
            ),
        )

        live_config = LiveMissionConfig(
            **config
        )

        if live_config.fault not in FAULTS:

            await websocket.send_json(
                {
                    "type": "error",
                    "message": (
                        f"Unsupported fault: "
                        f"{live_config.fault}"
                    ),
                }
            )

            await websocket.close()

            return

        ai = _require_ai()

        if live_config.waypoints and len(live_config.waypoints) >= 2:
            gps = SimulatedGPSSource(
                waypoints=live_config.waypoints,
                ground_temp_c=float(live_config.ambient_c),
                hot_weather_bias=8.0 if live_config.hot_weather else 0.0,
            )
        else:
            gps = _GPS

        mission = UAVMissionSimulator(
            duration_min=(
                float(
                    live_config.duration_h
                )
                * 60.0
            ),
            max_altitude_ft=(
                float(
                    live_config.max_altitude_ft
                )
            ),
            cruise_altitude_ft=(
                float(
                    live_config.cruise_altitude_ft
                )
            ),
            ambient_c=(
                float(
                    live_config.ambient_c
                )
            ),
            hot_weather=(
                bool(
                    live_config.hot_weather
                )
            ),
            rapid_throttle=(
                bool(
                    live_config.rapid_throttle
                )
            ),
            waypoints=gps.waypoints,
        )

        total_steps = int(
            live_config.steps
        )

        await websocket.send_json(
            {
                "type": "start",
                "mode": "live_uav_mission",
                "telemetry_schema": "UAVTelemetry",
                "telemetry_version": "1.0",
                "source": "uav_simulator",
                "scenario": (
                    live_config.model_dump()
                ),
                "mission": {
                    "duration_min": (
                        mission.duration_min
                    ),
                    "max_altitude_ft": (
                        mission.max_altitude_ft
                    ),
                    "cruise_altitude_ft": (
                        mission.cruise_altitude_ft
                    ),
                    "hot_weather": (
                        mission.hot_weather
                    ),
                    "rapid_throttle": (
                        mission.rapid_throttle
                    ),
                },
                "waypoints": [wp.to_dict() for wp in gps.waypoints],
                "planned_route": [[wp.latitude, wp.longitude] for wp in gps.waypoints],
                "home_base": gps.waypoints[0].to_dict(),
                "flight_plan_summary": gps.get_flight_plan_summary(),
            }
        )

        health_history: list[float] = []

        peak_risk = 0.0
        final_analysis = None
        final_risk = None

        for step in range(
            total_steps
        ):

            mission_point = mission.point(
                step,
                total_steps,
            )

            engine_data = (
                _build_live_engine_data(
                    mission_point
                )
            )

            telemetry_packet = (
                telemetry_from_engine(
                    engine_data,
                    mission_point,
                    source="uav_simulator",
                )
            )

            telemetry = (
                telemetry_packet.to_dict()
            )

            altered, fault_severity = (
                _apply_live_fault(
                    telemetry,
                    live_config,
                    step,
                )
            )

            altered[
                "Degradation_Severity"
            ] = fault_severity

            context = {
                **live_config.model_dump(),

                "data_source": (
                    "uav_simulation"
                ),

                "rpm": (
                    telemetry_packet.Engine_RPM
                ),

                "throttle": (
                    telemetry_packet.Throttle
                ),

                "load": (
                    telemetry_packet.Load
                ),

                "mission_phase": (
                    telemetry_packet.Mission_Phase
                ),

                "mission_time_min": (
                    telemetry_packet.Mission_Time_Min
                ),

                "mission_step": (
                    telemetry_packet.Mission_Step
                ),

                "altitude_ft": (
                    telemetry_packet.Altitude_ft
                ),

                "ambient_c": (
                    telemetry_packet.Ambient_C
                ),
            }

            analysis = ai.analyze(
                altered,
                context=context,
            )

            risk = mission_risk(
                analysis,
                context,
            )

            health_history.append(
                float(
                    analysis[
                        "health_index"
                    ]
                )
            )

            peak_risk = max(
                peak_risk,
                float(
                    risk["score"]
                ),
            )

            final_analysis = analysis
            final_risk = risk

            if analysis[
                "fault_candidates"
            ]:

                primary_fault = (
                    analysis[
                        "fault_candidates"
                    ][0]["name"]
                )

            else:

                primary_fault = "None"

            point = {
                "step": step,

                "time_min": round(
                    telemetry_packet.Mission_Time_Min,
                    3,
                ),

                "mission_phase": (
                    telemetry_packet.Mission_Phase
                ),

                "altitude_ft": round(
                    telemetry_packet.Altitude_ft,
                    2,
                ),

                "ambient_c": round(
                    telemetry_packet.Ambient_C,
                    2,
                ),

                "throttle": round(
                    telemetry_packet.Throttle,
                    4,
                ),

                "load": round(
                    telemetry_packet.Load,
                    4,
                ),

                "operating_state": (
                    telemetry_packet.Operating_State
                ),

                "rapid_throttle": (
                    telemetry_packet.Rapid_Throttle
                ),

                "health_state": (
                    analysis[
                        "health_state"
                    ]
                ),

                "ml_health_state": (
                    analysis[
                        "ml_health_state"
                    ]
                ),

                "health_index": (
                    analysis[
                        "health_index"
                    ]
                ),

                "health_confidence": (
                    analysis[
                        "health_confidence"
                    ]
                ),

                "anomaly_score": (
                    analysis[
                        "anomaly_score"
                    ]
                ),

                "anomaly_flag": (
                    analysis[
                        "anomaly_flag"
                    ]
                ),

                "residual_rms": round(
                    float(
                        analysis[
                            "twin"
                        ][
                            "residual_rms"
                        ]
                    ),
                    3,
                ),

                "max_abs_z": round(
                    float(
                        analysis[
                            "twin"
                        ][
                            "max_abs_z"
                        ]
                    ),
                    3,
                ),

                "risk_score": (
                    risk["score"]
                ),

                "risk_level": (
                    risk["level"]
                ),

                "primary_fault": (
                    primary_fault
                ),

                "sensor_trust": (
                    analysis[
                        "sensor_health"
                    ][
                        "overall_trust_score"
                    ]
                ),

                "fault_severity": round(
                    fault_severity,
                    4,
                ),

                "telemetry_version": (
                    telemetry_packet.telemetry_version
                ),

                "telemetry_source": (
                    telemetry_packet.source
                ),

                "uav": gps.get_position(
                    progress_ratio=step / max(1, total_steps - 1),
                    mission_context={
                        "altitude_ft": telemetry_packet.Altitude_ft,
                        "throttle": telemetry_packet.Throttle,
                        "mission_phase": telemetry_packet.Mission_Phase,
                    },
                ).to_dict(),

                "environment": gps.get_position(
                    progress_ratio=step / max(1, total_steps - 1),
                ).environment or {},

                "telemetry": (
                    _round_telemetry(
                        altered
                    )
                ),
            }

            await websocket.send_json(
                {
                    "type": "telemetry",
                    "data": point,
                }
            )

            await asyncio.sleep(
                playback_interval
            )

        final_point = mission.point(
            total_steps - 1,
            total_steps,
        )

        summary = {
            "steps": total_steps,

            "duration_min": round(
                mission.duration_min,
                2,
            ),

            "final_health_index": (
                final_analysis[
                    "health_index"
                ]
                if final_analysis
                else None
            ),

            "final_health_state": (
                final_analysis[
                    "health_state"
                ]
                if final_analysis
                else None
            ),

            "peak_risk_score": round(
                peak_risk,
                2,
            ),

            "final_risk_level": (
                final_risk["level"]
                if final_risk
                else None
            ),

            "final_mission_phase": (
                final_point.mission_phase
            ),

            "fault": (
                live_config.fault
            ),

            "fault_severity": (
                live_config.severity
            ),

            "fault_onset_ratio": (
                live_config.fault_onset_ratio
            ),

            "health_history_points": len(
                health_history
            ),

            "telemetry_schema": (
                "UAVTelemetry"
            ),

            "telemetry_version": (
                "1.0"
            ),

            "source": (
                "uav_simulator"
            ),

            "mode": (
                "live_uav_mission"
            ),

            "note": (
                "Simulated UAV mission telemetry "
                "feeding the AeroPulse Digital Twin "
                "and AI monitoring pipeline. "
                "Prototype only."
            ),
        }

        await websocket.send_json(
            {
                "type": "summary",
                "data": summary,
            }
        )

        await websocket.close()

    except WebSocketDisconnect:
        return

    except Exception as exc:

        try:

            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )

            await websocket.close()

        except Exception:
            pass
