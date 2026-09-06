"""AeroPulse-X Edge Compute Node & GCS Analytics Pipeline.

Implements the onboard UAV edge health monitor (UAVEdgeNode) and ground control
station telemetry processor (GCSAnalyticsServer).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .can_bus import CANBusInterface, CANFrame
from .sensor_health import assess_sensor_health
from .digital_twin import ReferenceTwin
from .rul_service import RULService


@dataclass
class EdgeHealthSummary:
    timestamp_s: float
    health_state: str
    anomaly_detected: bool
    sensor_trust_score: float
    suspect_sensors: List[str]
    local_safety_action: str
    edge_latency_ms: float
    stage_latencies_us: Optional[Dict[str, float]] = None
    diagnostics_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_s": self.timestamp_s,
            "health_state": self.health_state,
            "anomaly_detected": self.anomaly_detected,
            "sensor_trust_score": self.sensor_trust_score,
            "suspect_sensors": self.suspect_sensors,
            "local_safety_action": self.local_safety_action,
            "edge_latency_ms": self.edge_latency_ms,
            "stage_latencies_us": self.stage_latencies_us or {},
            "diagnostics_code": self.diagnostics_code,
        }


class UAVEdgeNode:
    """
    Onboard UAV Edge Computing Node.
    Executes fast-loop real-time telemetry validation, sensor plausibility,
    thermodynamic residual assessment, fault detection, and local autonomic safety actions.
    """

    def __init__(self, twin_engine: Optional[ReferenceTwin] = None, can_interface: Optional[CANBusInterface] = None):
        self.twin = twin_engine or ReferenceTwin()
        self.can_interface = can_interface or CANBusInterface()
        self.last_state = "Normal"
        self.consecutive_anomalies: int = 0
        self.frames_processed: int = 0

    def process_can_frames(self, frames: List[CANFrame]) -> EdgeHealthSummary:
        """Decode incoming CAN frames and process resulting telemetry."""
        decoded = self.can_interface.decode_frames(frames)
        return self.process_telemetry(decoded)

    def process_telemetry(self, telemetry: Dict[str, Any]) -> EdgeHealthSummary:
        """
        Process a single telemetry frame with full sub-millisecond stage instrumentation.
        """
        start_time = time.perf_counter_ns()
        sanitized = dict(telemetry)
        state = str(sanitized.get("Operating_State", "CRUISE"))

        # Stage 1: Reference Twin expected values
        t_s1 = time.perf_counter_ns()
        expected_vals = self.twin.expected(state)
        dt_twin_expected = (time.perf_counter_ns() - t_s1) / 1000.0

        # Stage 2: Residual and z-score calculation with robust NaN/None sanitization
        t_s2 = time.perf_counter_ns()
        max_z = 0.0
        z_scores = {}
        for param, exp in expected_vals.items():
            raw_val = sanitized.get(param)
            if raw_val is None:
                obs = float(exp)
            else:
                try:
                    fval = float(raw_val)
                    if math.isnan(fval) or math.isinf(fval):
                        obs = float(exp)
                    else:
                        obs = fval
                except (ValueError, TypeError):
                    obs = float(exp)

            std = max(abs(exp) * 0.04, 1e-4)
            z = (obs - exp) / std
            z_scores[param] = z
            if abs(z) > max_z:
                max_z = abs(z)
        dt_residuals = (time.perf_counter_ns() - t_s2) / 1000.0

        # Stage 3: Sensor Health & Cross-Channel Plausibility
        t_s3 = time.perf_counter_ns()
        twin_stub = {"z_scores": z_scores}
        sh = assess_sensor_health(sanitized, twin_stub)
        trust_score = float(sh.get("overall_trust_score", 100.0))
        suspects = sh.get("suspect_sensors", [])
        dt_sensor_health = (time.perf_counter_ns() - t_s3) / 1000.0

        # Stage 4: Health Classification & Autonomic Action
        t_s4 = time.perf_counter_ns()
        anomaly = max_z >= 3.0 or trust_score < 50.0
        if anomaly:
            self.consecutive_anomalies += 1
        else:
            self.consecutive_anomalies = max(0, self.consecutive_anomalies - 1)

        if max_z >= 4.5 or self.consecutive_anomalies >= 5:
            health_state = "Critical"
            safety_action = "RESTRICT_THROTTLE_INITIATE_RTL"
        elif max_z >= 2.5 or self.consecutive_anomalies >= 2:
            health_state = "Warning"
            safety_action = "MONITOR_THERMAL_AVOID_MAX_THRUST"
        elif max_z >= 1.5:
            health_state = "Watch"
            safety_action = "NOMINAL_ENVELOPE"
        else:
            health_state = "Normal"
            safety_action = "GO_MISSION_CLEARED"

        self.last_state = health_state
        self.frames_processed += 1
        dt_health_action = (time.perf_counter_ns() - t_s4) / 1000.0

        total_latency_ms = (time.perf_counter_ns() - start_time) / 1_000_000.0

        stages_us = {
            "twin_expected_us": round(dt_twin_expected, 2),
            "residuals_zscore_us": round(dt_residuals, 2),
            "sensor_plausibility_us": round(dt_sensor_health, 2),
            "health_safety_action_us": round(dt_health_action, 2),
        }

        return EdgeHealthSummary(
            timestamp_s=round(time.time(), 3),
            health_state=health_state,
            anomaly_detected=anomaly,
            sensor_trust_score=round(trust_score, 1),
            suspect_sensors=suspects,
            local_safety_action=safety_action,
            edge_latency_ms=round(total_latency_ms, 3),
            stage_latencies_us=stages_us,
        )


class GCSAnalyticsServer:
    """
    Ground Control Station (GCS) Analytics Engine.
    Executes heavy fleetwide historical analysis, detailed multi-channel digital twin
    correlation, multi-horizon Weibull/stress RUL prognostics, and causal explainability.
    """

    def __init__(self):
        self.rul_service = RULService()
        self.twin = ReferenceTwin()

    def process_gcs_packet(
        self,
        telemetry: Dict[str, Any],
        edge_summary: EdgeHealthSummary,
        context: Optional[dict] = None,
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        twin_result = self.twin.compare(telemetry, context=context)
        sh = assess_sensor_health(telemetry, twin_result)
        rul_res = self.rul_service.predict(telemetry, context=context)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return {
            "edge_summary": edge_summary,
            "digital_twin": twin_result,
            "sensor_health": sh,
            "rul": rul_res,
            "gcs_latency_ms": round(latency_ms, 3),
        }


def benchmark_edge_performance(sample_telemetry: dict, iterations: int = 500) -> dict[str, Any]:
    """Micro-benchmark edge and GCS processing latencies over N iterations."""
    edge = UAVEdgeNode()
    gcs = GCSAnalyticsServer()

    # Warmup
    for _ in range(min(50, iterations)):
        s = edge.process_telemetry(sample_telemetry)
        gcs.process_gcs_packet(sample_telemetry, s)

    edge_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        summary = edge.process_telemetry(sample_telemetry)
        edge_times.append((time.perf_counter() - t0) * 1000.0)

    gcs_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        gcs.process_gcs_packet(sample_telemetry, summary)
        gcs_times.append((time.perf_counter() - t0) * 1000.0)

    sorted_edge = sorted(edge_times)
    sorted_gcs = sorted(gcs_times)

    return {
        "edge_mean_latency_ms": round(sum(edge_times) / len(edge_times), 3),
        "edge_p99_latency_ms": round(sorted_edge[int(0.99 * (len(sorted_edge) - 1))], 3),
        "gcs_mean_latency_ms": round(sum(gcs_times) / len(gcs_times), 3),
        "gcs_p99_latency_ms": round(sorted_gcs[int(0.99 * (len(sorted_gcs) - 1))], 3),
        "benchmark_platform": "CPU Software Benchmark (Desktop / Host CPU)",
    }


def main():
    """CLI daemon entrypoint for embedded edge deployment."""
    parser = argparse.ArgumentParser(description="AeroPulse-X Edge Node Daemon")
    parser.add_argument("--config", type=str, default=None, help="Path to edge_config.json")
    parser.add_argument("--log-dir", type=str, default="/var/log/aeropulse", help="Log output directory")
    parser.add_argument("--benchmark", action="store_true", help="Run self-benchmark and exit")
    args = parser.parse_args()

    print("[AEROPULSE-X EDGE] Initializing node...")
    node = UAVEdgeNode()
    print("[AEROPULSE-X EDGE] Node initialized successfully.")

    if args.benchmark:
        sample = {
            "Engine_RPM": 4544.0,
            "EGT1": 1285.0,
            "EGT2": 1290.0,
            "EGT3": 1282.0,
            "CHT": 215.0,
            "Fuel_Flow": 22.4,
            "Oil_Temp": 185.0,
            "Oil_Pressure": 42.5,
            "Battery_Voltage": 28.2,
            "Battery_Current": 14.5,
            "Alternator_Temp": 68.0,
            "EFI_Fuel_Temp": 32.0,
            "EFI_Water_Temp": 82.0,
            "MAP_Injector": 101.3,
            "Operating_State": "CRUISE",
        }
        res = benchmark_edge_performance(sample, iterations=1000)
        print(json.dumps(res, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
