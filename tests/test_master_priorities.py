"""Comprehensive Test Suite for AeroPulse-X 10 Master Technical Priorities."""
from __future__ import annotations

import math
import pytest

from app.engine_model import EngineInputs, ReducedOrderPistonEngine
from app.degradation_model import (
    ContinuousDegradationModel,
    DegradationState,
    generate_physics_synthetic_dataset,
)
from app.rul_service import RULService
from app.edge import UAVEdgeNode, GCSAnalyticsServer, benchmark_edge_performance
from app.can_bus import CANBusInterface, CANFrame
from app.explainability import ExplainableDiagnosticEngine
from app.secure_telemetry import SecureTelemetryManager, SecurityViolationError
from app.mission_whatif import MissionScenario
from app.mission_whatif_rul import MissionWhatIfRUL
from app.interfaces import IEngineModel
from app.plugins.rotax914 import Rotax914TurboPistonEngine
from app.validation import AeroPulseValidator


# ==============================================================================
# 1. PRIORITY #1 — REAL PHYSICS-GROUNDED ENGINE MODEL
# ==============================================================================
def test_priority1_physics_engine_monotonicity():
    engine = ReducedOrderPistonEngine()

    # Altitude response
    sea = engine.predict(EngineInputs(altitude_ft=0, throttle=0.60))
    alt15k = engine.predict(EngineInputs(altitude_ft=15000, throttle=0.60))
    assert alt15k["Air_Density_Ratio"] < sea["Air_Density_Ratio"]
    assert alt15k["MAP_Injector"] < sea["MAP_Injector"]

    # Ambient temperature thermal response
    cold = engine.predict(EngineInputs(ambient_c=10.0, throttle=0.60))
    hot = engine.predict(EngineInputs(ambient_c=45.0, throttle=0.60))
    assert hot["CHT"] > cold["CHT"]
    assert hot["Oil_Temp"] > cold["Oil_Temp"]

    # Throttle and power generation
    idle = engine.predict(EngineInputs(throttle=0.15))
    climb = engine.predict(EngineInputs(throttle=0.90))
    assert climb["Indicated_Power_kW"] > idle["Indicated_Power_kW"]
    assert climb["Fuel_Flow"] > idle["Fuel_Flow"]
    assert climb["Heat_Rejection_kW"] > idle["Heat_Rejection_kW"]


# ==============================================================================
# 2. PRIORITY #2 — PHYSICALLY COUPLED FAULT DATA
# ==============================================================================
def test_priority2_physically_coupled_faults():
    engine = ReducedOrderPistonEngine()
    deg = ContinuousDegradationModel()
    base = engine.predict(EngineInputs(rpm=3000, throttle=0.60))

    # Test all 7 fault modes
    # Injector
    inj = deg.apply(base, DegradationState(injector=0.80))
    assert inj["Fuel_Flow"] < base["Fuel_Flow"]
    assert inj["Efficiency"] < base["Efficiency"]

    # Lubrication
    lub = deg.apply(base, DegradationState(lubrication=0.80))
    assert lub["Oil_Pressure"] < base["Oil_Pressure"]
    assert lub["Oil_Temp"] > base["Oil_Temp"]
    assert lub["Vibration"] > base["Vibration"]

    # Thermal
    therm = deg.apply(base, DegradationState(thermal=0.80))
    assert therm["CHT"] > base["CHT"]
    assert therm["EFI_Water_Temp"] > base["EFI_Water_Temp"]

    # Mechanical
    mech = deg.apply(base, DegradationState(mechanical=0.80))
    assert mech["Vibration"] > base["Vibration"]
    assert mech["Engine_RPM"] < base["Engine_RPM"]

    # Electrical
    elec = deg.apply(base, DegradationState(electrical=0.80))
    assert elec["Battery_Voltage"] < base["Battery_Voltage"]
    assert elec["Alternator_Temp"] > base["Alternator_Temp"]

    # Misfire
    mis = deg.apply(base, DegradationState(misfire=0.80))
    assert mis["EGT1"] < base["EGT1"]
    assert mis["Vibration"] > base["Vibration"]

    # Sensor
    sens = deg.apply(base, DegradationState(sensor=0.80))
    assert sens["EFI_Water_Temp"] > base["EFI_Water_Temp"]
    assert sens["Engine_RPM"] == base["Engine_RPM"]


def test_priority2_synthetic_dataset_generation():
    engine = ReducedOrderPistonEngine()
    base = engine.predict(EngineInputs(rpm=3000, throttle=0.60))
    dataset = generate_physics_synthetic_dataset(base, steps_per_mode=15)

    assert "healthy" in dataset
    assert "early_degradation" in dataset
    assert "moderate_degradation" in dataset
    assert "severe_degradation" in dataset
    assert "onset_progression" in dataset
    assert "recovery" in dataset
    assert "sensor_only_fault" in dataset
    assert len(dataset["healthy"]) == 15
    assert len(dataset["severe_degradation"]) == 15


# ==============================================================================
# 3. PRIORITY #3 — RUL ESTIMATION + UNCERTAINTY QUANTIFICATION
# ==============================================================================
def test_priority3_rul_uncertainty_bounds():
    rul_service = RULService()
    history = [100.0, 95.0, 90.0, 85.0, 80.0, 74.0, 68.0]
    pred = rul_service.estimate_rul(health_index=68.0, health_history=history, step_minutes=10.0)

    assert pred["rul_hours"] is not None
    assert pred["rul_hours"] > 0
    assert pred["rul_lower_hours"] <= pred["rul_hours"]
    assert pred["rul_upper_hours"] >= pred["rul_hours"]
    assert 0.0 <= pred["confidence"] <= 1.0
    assert pred["status"] == "ACTIVE_DEGRADATION"


# ==============================================================================
# 4. PRIORITY #4 — REAL-TIME / EDGE-COMPUTE ARCHITECTURE
# ==============================================================================
def test_priority4_edge_vs_gcs_architecture():
    edge = UAVEdgeNode()
    gcs = GCSAnalyticsServer()

    engine = ReducedOrderPistonEngine()
    sample = engine.predict(EngineInputs(rpm=3000, throttle=0.60))

    # Edge processing
    edge_summary = edge.process_telemetry(sample)
    assert edge_summary.health_state in {"Normal", "Watch", "Warning", "Critical"}
    assert edge_summary.edge_latency_ms < 50.0  # Real-time boundary

    # GCS processing
    gcs_result = gcs.process_gcs_packet(sample, edge_summary)
    assert "digital_twin" in gcs_result
    assert "sensor_health" in gcs_result
    assert "rul" in gcs_result

    # CPU Benchmark
    bench = benchmark_edge_performance(sample, iterations=20)
    assert "edge_mean_latency_ms" in bench
    assert "gcs_mean_latency_ms" in bench


# ==============================================================================
# 5. PRIORITY #5 — CAN / ECU / FADEC INTEGRATION LAYER
# ==============================================================================
def test_priority5_can_framing_and_decoding():
    can = CANBusInterface()
    engine = ReducedOrderPistonEngine()
    telemetry = engine.predict(EngineInputs(rpm=3000, throttle=0.60))

    frames = can.encode_telemetry(telemetry)
    assert len(frames) == 4

    decoded = {}
    for f in frames:
        decoded.update(can.decode_frame(f))

    assert "Engine_RPM" in decoded
    assert "EGT1" in decoded
    assert "Oil_Pressure" in decoded
    assert "Battery_Voltage" in decoded


# ==============================================================================
# 6. PRIORITY #6 — EXPLAINABLE FAULT DIAGNOSIS
# ==============================================================================
def test_priority6_explainable_diagnosis():
    engine = ReducedOrderPistonEngine()
    deg = ContinuousDegradationModel()
    base = engine.predict(EngineInputs(rpm=3000, throttle=0.60))
    lub_telemetry = deg.apply(base, DegradationState(lubrication=0.75))

    twin = {"z_scores": {"Oil_Pressure": -3.5, "Oil_Temp": 2.8, "Vibration": 2.5}, "expected": base, "percentage_deviation": {"Oil_Pressure": -40.0}}
    sensor_health = {"overall_trust_score": 100.0, "suspect_sensors": []}
    candidates = [{"name": "Lubrication Breakdown", "severity": "high", "evidence": ["low oil pressure", "high oil temp"]}]

    diag = ExplainableDiagnosticEngine.explain(
        telemetry=lub_telemetry,
        twin_assessment=twin,
        sensor_health=sensor_health,
        fault_candidates=candidates,
        ml_prediction="Warning",
        ml_confidence=0.92,
    )

    assert diag.primary_fault == "Lubrication Breakdown"
    assert diag.severity == "high"
    assert len(diag.dominant_deviations) > 0
    assert diag.physics_consistency_score >= 70.0
    assert "Safety Advisory" in diag.remediation_guidance


# ==============================================================================
# 7. PRIORITY #7 — SECURE TELEMETRY ARCHITECTURE
# ==============================================================================
def test_priority7_secure_telemetry():
    sec = SecureTelemetryManager()
    telemetry = {"Engine_RPM": 3000, "CHT": 220.0}

    packet = sec.sign_telemetry(telemetry)
    valid, payload, reason = sec.verify_and_unpack(packet)
    assert valid is True
    assert payload == telemetry
    assert reason == "AUTHENTICATED_AND_VERIFIED"

    # Anti-replay test
    replay_valid, _, replay_reason = sec.verify_and_unpack(packet)
    assert replay_valid is False
    assert "REPLAY" in replay_reason

    # Tamper test
    tampered_packet = sec.sign_telemetry(telemetry)
    tampered_packet.payload["Engine_RPM"] = 9999
    tamper_valid, _, tamper_reason = sec.verify_and_unpack(tampered_packet)
    assert tamper_valid is False
    assert "TAMPERED" in tamper_reason


# ==============================================================================
# 8. PRIORITY #8 — HIGH-FIDELITY MISSION / ENVIRONMENT SIMULATION
# ==============================================================================
def test_priority8_mission_whatif_comparison():
    whatif = MissionWhatIfRUL()
    engine = ReducedOrderPistonEngine()
    base = engine.predict(EngineInputs(rpm=3000, throttle=0.60))

    scen_a = MissionScenario("Standard Patrol", altitude_ft=5000, ambient_c=25, duration_h=4)
    scen_b = MissionScenario("High Altitude Hot Weather", altitude_ft=18000, ambient_c=45, duration_h=8)

    comp = whatif.compare(base, scen_a, scen_b)
    assert "baseline" in comp
    assert "alternative" in comp
    assert "impact" in comp
    assert "comparison" in comp
    assert comp["comparison"]["stress_multiplier_delta"] > 0


# ==============================================================================
# 9. PRIORITY #9 — MODULARITY AND SCALABILITY
# ==============================================================================
def test_priority9_rotax_plugin_interface():
    plugin = Rotax914TurboPistonEngine()
    assert isinstance(plugin, IEngineModel)

    out = plugin.predict(EngineInputs(rpm=5500, throttle=0.75))
    assert "Engine_RPM" in out
    assert "Brake_Power_kW" in out
    assert out["Engine_RPM"] == 5500.0


# ==============================================================================
# 10. PRIORITY #10 — FORMAL VALIDATION FRAMEWORK
# ==============================================================================
def test_priority10_formal_validation_framework():
    validator = AeroPulseValidator()
    report = validator.run_full_validation()

    assert report.physics_monotonicity_passed is True
    assert report.fault_causal_direction_passed is True
    assert report.sensor_trust_accuracy >= 90.0
    assert report.ml_macro_f1 >= 0.90
    assert report.rul_coverage_90ci >= 90.0
    assert len(report.metrics) >= 5
    assert len(report.dataset_boundaries) >= 5
