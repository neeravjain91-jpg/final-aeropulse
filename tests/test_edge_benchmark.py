"""Automated verification suite for AeroPulse-X edge compute benchmarking module."""
from __future__ import annotations

import pytest
from app.edge_benchmark import (
    EdgeBenchmarkSuite,
    get_system_hardware_info,
    get_current_process_memory_mb,
    run_benchmark_and_get_summary,
)


def test_hardware_discovery():
    """Verify hardware discovery accurately inspects host system attributes."""
    hw = get_system_hardware_info()

    assert "machine" in hw
    assert "processor" in hw
    assert "system" in hw
    assert "logical_cores" in hw
    assert hw["logical_cores"] >= 1
    assert "hardware_classification" in hw
    assert hw["hardware_classification"] in ["DESKTOP_HOST_X86", "PHYSICAL_ARM_EMBEDDED"]
    assert "embedded_hardware_available" in hw
    assert isinstance(hw["embedded_hardware_available"], bool)


def test_memory_rss_measurement():
    """Verify cross-platform process RSS measurement is non-negative and finite."""
    rss = get_current_process_memory_mb()
    assert isinstance(rss, float)
    assert rss >= 0.0


def test_component_micro_benchmarks():
    """Verify stage-by-stage micro-benchmarks produce valid timing distributions."""
    suite = EdgeBenchmarkSuite()
    results = suite.run_component_benchmarks(sample_count=200, warmup_count=20)

    expected_stages = [
        "1_CAN_Frame_Decode",
        "2_HMAC_Security_Verify",
        "3_Sensor_Trust_Assessment",
        "4_Twin_Physics_Residual",
        "5_FADEC_Limits_DTC_Check",
        "6_Health_State_Classify",
        "7_Local_RUL_Projection",
        "8_Local_Safety_Action",
    ]

    for stage in expected_stages:
        assert stage in results, f"Missing stage: {stage}"
        stats = results[stage]
        assert stats["mean"] >= 0.0
        assert stats["p50"] <= stats["p95"] <= stats["p99"] <= stats["max"]


def test_sustained_load_stability():
    """Verify sustained high-frequency load execution maintains stability and bounded memory."""
    suite = EdgeBenchmarkSuite()
    res = suite.run_sustained_load_test(sample_count=1000)

    assert res["samples_processed"] == 1000
    assert res["errors"] == 0
    assert res["dropped_samples"] == 0
    assert res["is_stable"] is True
    assert res["rss_growth_mb"] < 100.0  # Must not leak memory rapidly


def test_failure_injection_resilience():
    """Verify edge pipeline resilience under simulated fault and corrupt telemetry injections."""
    suite = EdgeBenchmarkSuite()
    res = suite.run_failure_injection_resilience_test()

    assert res["scenarios_tested"] >= 5
    assert res["all_passed"] is True, f"Failed resilience scenarios: {res['details']}"


def test_full_benchmark_suite_execution():
    """Verify end-to-end benchmark execution and report rendering."""
    report = run_benchmark_and_get_summary(samples=500, warmup=50)

    assert report.sample_count == 500
    assert report.warmup_count == 50
    assert report.throughput_samples_per_sec > 1000.0  # Host CPU throughput
    assert report.complete_pipeline_latency_ms["p99"] < 1.0  # Desktop host P99 is sub-millisecond

    summary_text = report.render_summary()
    assert "AEROPULSE-X EDGE COMPUTE BENCHMARK REPORT" in summary_text
    assert "STAGE-BY-STAGE LATENCY BREAKDOWN" in summary_text
    assert "COMPLETE PIPELINE LATENCIES" in summary_text
    assert "FORMAL VALIDATION CLASSIFICATION" in summary_text
    assert "Electrical Power Consumption: NOT_MEASURED" in summary_text
