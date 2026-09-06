"""Comprehensive Test Suite for Engine Model Validation, Parameter Provenance, and Uncertainty Harness."""
from __future__ import annotations

import math
import pytest
import numpy as np

from app.engine_model import EngineInputs, ReducedOrderPistonEngine
from app.engine_config import EngineConfig, default_engine_config
from app.engine_parameters import (
    EngineParameterRegistry,
    ParameterSourceType,
    ValidationStatus,
    get_default_parameter_registry,
)
from app.engine_validation import EngineModelValidator


def test_parameter_provenance_registry():
    """Verifies that all engine parameters are registered with valid provenance metadata."""
    registry = get_default_parameter_registry()
    params = registry.all_parameters()

    assert len(params) >= 20
    for p in params:
        assert p.name
        assert p.unit
        assert isinstance(p.source_type, ParameterSourceType)
        assert isinstance(p.confidence_status, ValidationStatus)
        assert len(p.source) > 5
        assert isinstance(p.value, (int, float))

    # Check specific critical parameters
    cr = registry.get("compression_ratio")
    assert cr is not None
    assert cr.value == 9.0
    assert cr.unit == "ratio"
    assert cr.source_type == ParameterSourceType.PUBLISHED_SPECIFICATION

    gamma = registry.get("gamma")
    assert gamma is not None
    assert gamma.value == 1.33
    assert gamma.source_type == ParameterSourceType.LITERATURE_ASSUMPTION


def test_parameter_provenance_markdown_export():
    """Verifies that the parameter registry generates a valid markdown table."""
    registry = get_default_parameter_registry()
    md = registry.to_markdown_table()
    assert "| Parameter | Value | Unit |" in md
    assert "`displacement_l`" in md
    assert "`compression_ratio`" in md


def test_engine_config_registry_integration():
    """Verifies that EngineConfig integrates seamlessly with the parameter registry."""
    config = default_engine_config()
    registry = config.get_registry()
    assert registry is not None
    assert len(registry.all_parameters()) >= 20

    cfg_dict = config.to_dict()
    assert cfg_dict["displacement_l"] == 1.352
    assert cfg_dict["base_power_kw"] == 84.5


def test_operating_point_validation_metrics():
    """Verifies operating point validation against published Rotax 914 reference points."""
    validator = EngineModelValidator()
    results = validator.validate_operating_points()

    assert results["operating_points_evaluated"] == 5
    assert results["power_r2"] >= 0.85
    assert results["power_mae_kw"] < 10.0

    # Verify Takeoff & MCP points specifically
    comparisons = results["comparisons"]
    takeoff_power = next(c for c in comparisons if c["point_id"] == "OP_TAKEOFF" and c["channel"] == "Brake_Power_kW")
    assert takeoff_power["status"] == "VALIDATED"
    assert takeoff_power["relative_error_pct"] < 10.0

    mcp_power = next(c for c in comparisons if c["point_id"] == "OP_MCP" and c["channel"] == "Brake_Power_kW")
    assert mcp_power["status"] == "VALIDATED"
    assert mcp_power["relative_error_pct"] < 10.0

    # Verify uncalibrated / nacelle-specific channels are marked UNAVAILABLE honestly
    takeoff_cht = next(c for c in comparisons if c["point_id"] == "OP_TAKEOFF" and c["channel"] == "CHT")
    assert takeoff_cht["status"] == "UNAVAILABLE"


def test_nine_point_physical_monotonicity_suite():
    """Verifies that all 9 physical monotonicity tests pass 100%."""
    validator = EngineModelValidator()
    res = validator.run_monotonicity_suite()

    assert res["total_tests"] == 9
    assert res["passed_tests"] == 9
    assert res["all_passed"] is True
    assert res["pass_ratio_pct"] == 100.0

    test_ids = [r["test_id"] for r in res["results"]]
    assert "MONO_01_THROTTLE_POWER" in test_ids
    assert "MONO_02_ALT_DENSITY" in test_ids
    assert "MONO_03_ALT_POWER" in test_ids
    assert "MONO_04_LOAD_STRESS" in test_ids
    assert "MONO_05_RPM_ENVELOPE" in test_ids
    assert "MONO_06_AMBIENT_TEMP" in test_ids
    assert "MONO_07_COOLING_DEGRADATION" in test_ids
    assert "MONO_08_FUEL_DELIVERY" in test_ids
    assert "MONO_09_FRICTION_LOSS" in test_ids


def test_sensitivity_analysis_ranking():
    """Verifies that normalized sensitivity analysis correctly calculates sensitivities and directional signs."""
    validator = EngineModelValidator()
    sens = validator.run_sensitivity_analysis()

    assert "matrix" in sens
    assert "top_10_sensitivities" in sens
    matrix = sens["matrix"]

    # Throttle and RPM should be strong positive drivers for Brake Power
    assert matrix["throttle"]["Brake_Power_kW"] > 0.5
    assert matrix["rpm"]["Brake_Power_kW"] > 0.5

    # Fuel delivery ratio should have ~1.0 normalized sensitivity for fuel flow
    assert matrix["fuel_delivery_ratio"]["Fuel_Flow"] > 0.8

    # Cooling efficiency should have negative sensitivity on CHT
    assert matrix["cooling_efficiency"]["CHT"] < 0.0

    # Friction multiplier should reduce Brake Power
    assert matrix["friction_multiplier"]["Brake_Power_kW"] < 0.0


def test_parametric_uncertainty_propagation():
    """Verifies Monte Carlo parametric uncertainty propagation produces valid confidence intervals."""
    validator = EngineModelValidator()
    unc = validator.run_uncertainty_propagation(num_samples=100, seed=123)

    assert unc.sample_count == 100
    assert unc.uncertainty_type == "MODEL_PARAMETER_UNCERTAINTY"

    power_unc = unc.channels["Brake_Power_kW"]
    assert power_unc.p05_lower <= power_unc.mean <= power_unc.p95_upper
    assert power_unc.uncertainty_width_90ci > 0.0
    assert power_unc.relative_uncertainty_pct > 0.0

    cht_unc = unc.channels["CHT"]
    assert cht_unc.p05_lower <= cht_unc.mean <= cht_unc.p95_upper
    assert cht_unc.uncertainty_width_90ci > 0.0


def test_aces_cross_domain_telemetry_check():
    """Verifies that NASA ACES real flight telemetry cross-checks pass within bounds."""
    validator = EngineModelValidator()
    aces_res = validator.run_aces_cross_domain_check()

    assert aces_res["status"] == "CONSISTENT"
    assert len(aces_res["channels_checked"]) >= 4
    for ch in aces_res["channels_checked"]:
        assert ch["envelope_overlap_pct"] > 0.0


def test_invalid_inputs_and_out_of_envelope_handling():
    """Verifies that engine model handles extreme, invalid, or out-of-envelope inputs without crashing."""
    engine = ReducedOrderPistonEngine()

    # Negative RPM clipped to IDLE_RPM
    res_neg_rpm = engine.simulate(rpm=-500.0)
    assert res_neg_rpm["Engine_RPM"] == 1400.0

    # Over-speed RPM clipped to MAX_RPM
    res_over_rpm = engine.simulate(rpm=9000.0)
    assert res_over_rpm["Engine_RPM"] == 5800.0

    # Negative throttle clipped to 0.05
    res_neg_throt = engine.simulate(throttle=-0.5)
    assert res_neg_throt["Brake_Power_kW"] >= 3.0

    # Extreme sub-zero ambient
    res_cold = engine.simulate(ambient_c=-60.0)
    assert math.isfinite(res_cold["CHT"])
    assert math.isfinite(res_cold["Oil_Temp"])

    # Extreme hot ambient
    res_hot = engine.simulate(ambient_c=70.0)
    assert math.isfinite(res_hot["CHT"])
    assert res_hot["CHT"] > res_cold["CHT"]


def test_full_validation_summary_structure():
    """Verifies that generate_full_validation_summary() produces all expected sections."""
    validator = EngineModelValidator()
    summary = validator.generate_full_validation_summary()

    assert summary["parameter_provenance"]["status"] == "LITERATURE_INFORMED_AND_PUBLISHED_SPECS"
    assert summary["operating_point_validation"]["status"] == "PASS"
    assert summary["monotonicity"]["status"] == "PASS"
    assert summary["sensitivity"]["status"] == "PASS"
    assert summary["uncertainty"]["status"] == "PASS"
    assert summary["physical_test_cell_status"] == "NOT_AVAILABLE_PENDING_DYNAMOMETER"
    assert "defensible_conclusion" in summary
