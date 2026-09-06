from __future__ import annotations

import json
import math
from typing import Dict, Any, List, Optional
from collections import deque

from .config import MODEL_DIR
from .engine_model import EngineInputs, ReducedOrderPistonEngine


PARAMS = [
    "Engine_RPM",
    "EGT1",
    "EGT2",
    "EGT3",
    "CHT",
    "Fuel_Flow",
    "Oil_Temp",
    "Oil_Pressure",
    "Battery_Voltage",
    "Battery_Current",
    "Alternator_Temp",
    "EFI_Fuel_Temp",
    "EFI_Water_Temp",
    "MAP_Injector",
]

ENGINE_MODEL_MAP = {
    "Engine_RPM": "Engine_RPM",
    "EGT1": "EGT1",
    "EGT2": "EGT2",
    "EGT3": "EGT3",
    "CHT": "CHT",
    "Fuel_Flow": "Fuel_Flow",
    "Oil_Temp": "Oil_Temp",
    "Oil_Pressure": "Oil_Pressure",
    "Battery_Voltage": "Battery_Voltage",
    "Battery_Current": "Battery_Current",
    "Alternator_Temp": "Alternator_Temp",
    "EFI_Fuel_Temp": "EFI_Fuel_Temp",
    "EFI_Water_Temp": "EFI_Water_Temp",
    "MAP_Injector": "MAP_Injector",
}


class ReferenceTwin:
    def __init__(self):
        self.stats = json.loads((MODEL_DIR / "healthy_reference.json").read_text(encoding="utf-8"))
        self.engine_model = ReducedOrderPistonEngine()
        self._history_z: Dict[str, deque] = {p: deque(maxlen=20) for p in PARAMS}
        self._persistence_counts: Dict[str, int] = {p: 0 for p in PARAMS}

    @property
    def operating_states(self) -> list[str]:
        return sorted(key for key in self.stats if key != "_GLOBAL_")

    def expected(self, operating_state: str) -> dict:
        state = self.stats.get(str(operating_state), self.stats["_GLOBAL_"])
        return {key: value["median"] for key, value in state.items()}

    def _sanitize_telemetry(self, telemetry: dict, expected: dict) -> dict:
        sanitized = {}
        for p in PARAMS:
            val = telemetry.get(p)
            if val is None or (isinstance(val, (int, float)) and (math.isnan(val) or math.isinf(val))):
                sanitized[p] = float(expected.get(p, 0.0))
            else:
                try:
                    fval = float(val)
                    if p == "Engine_RPM" and fval < 0:
                        fval = 0.0
                    elif p in ["CHT", "Oil_Temp", "EFI_Water_Temp"] and fval < -40.0:
                        fval = float(expected.get(p, 180.0))
                    sanitized[p] = fval
                except (ValueError, TypeError):
                    sanitized[p] = float(expected.get(p, 0.0))
        return sanitized

    def _contextual_expected(self, ref: dict, context: dict | None) -> dict:
        context = context or {}
        expected = {p: float(ref[p]["median"]) for p in PARAMS}
        alt_ft = float(context.get("altitude_ft", 0.0))
        amb_c = float(context.get("ambient_c", 25.0))
        if alt_ft > 5000.0:
            alt_ratio = (alt_ft - 5000.0) / 20000.0
            expected["MAP_Injector"] *= max(0.60, 1.0 - 0.25 * alt_ratio)
        if amb_c > 35.0:
            hot_ratio = (amb_c - 35.0) / 15.0
            expected["CHT"] *= (1.0 + 0.04 * hot_ratio)
            expected["Oil_Temp"] *= (1.0 + 0.05 * hot_ratio)
            expected["EFI_Water_Temp"] *= (1.0 + 0.04 * hot_ratio)
        return expected

    def _physics_expected(self, ref: dict, context: dict | None) -> dict:
        context = context or {}
        rpm = float(context.get("rpm", context.get("Engine_RPM", 4544.0)))
        throttle = float(context.get("throttle", 0.60))
        altitude = float(context.get("altitude_ft", 3000.0))
        ambient = float(context.get("ambient_c", 25.0))
        load = context.get("load")

        current = self.engine_model.predict(
            EngineInputs(rpm=rpm, throttle=throttle, altitude_ft=altitude, ambient_c=ambient, load=load)
        )
        return {p: float(current[ENGINE_MODEL_MAP[p]]) for p in PARAMS}

    def compare(self, telemetry: dict, context: dict | None = None) -> dict:
        context = context or {}
        state = str(telemetry.get("Operating_State", "_GLOBAL_"))
        ref = self.stats.get(state, self.stats["_GLOBAL_"])

        simulation_mode = str(context.get("data_source", "")).lower() in {"simulation", "uav_simulation", "live_uav"}

        if simulation_mode:
            physics_expected = self._physics_expected(ref, context)
            expected = dict(physics_expected)
        else:
            contextual_expected = self._contextual_expected(ref, context)
            physics_expected = self._physics_expected(ref, context)
            expected = {
                p: 0.50 * float(contextual_expected[p]) + 0.50 * float(physics_expected[p])
                for p in PARAMS
            }

        sanitized_telemetry = self._sanitize_telemetry(telemetry, expected)

        residuals = {}
        z_scores = {}
        percentage_deviation = {}
        residual_slopes = {}
        deviations = {}

        for p in PARAMS:
            obs = sanitized_telemetry[p]
            exp = expected[p]
            std = max(float(ref[p]["std"]), 1e-6) if not simulation_mode else max(abs(exp) * 0.03, 1e-6)

            res = obs - exp
            z = res / std
            pct = 100.0 * res / abs(exp) if abs(exp) > 1e-9 else 0.0

            residuals[p] = res
            z_scores[p] = z
            percentage_deviation[p] = pct

            # Temporal slopes & persistence
            hist = self._history_z[p]
            if len(hist) > 0:
                slope = (z - hist[-1])  # delta z per step
            else:
                slope = 0.0
            hist.append(z)
            residual_slopes[p] = slope

            if abs(z) >= 2.0:
                self._persistence_counts[p] += 1
            else:
                self._persistence_counts[p] = max(0, self._persistence_counts[p] - 1)

            deviations[p] = {
                "measured": obs,
                "expected": exp,
                "residual": res,
                "z_score": z,
                "percentage_deviation": pct,
                "slope": slope,
                "persistence": self._persistence_counts[p],
            }

        max_abs_z = max(abs(v) for v in z_scores.values())
        residual_rms = math.sqrt(sum(v * v for v in z_scores.values()) / len(z_scores))

        dominant = sorted(
            [
                {
                    "parameter": p,
                    "z_score": round(float(z_scores[p]), 3),
                    "residual": round(float(residuals[p]), 3),
                    "percentage_deviation": round(float(percentage_deviation[p]), 2),
                    "persistence": self._persistence_counts[p],
                }
                for p in PARAMS
            ],
            key=lambda x: abs(x["z_score"]),
            reverse=True,
        )[:5]

        return {
            "operating_state": state,
            "expected": expected,
            "physics_expected": physics_expected,
            "residuals": residuals,
            "z_scores": z_scores,
            "residual_slopes": residual_slopes,
            "residual_persistence": dict(self._persistence_counts),
            "percentage_deviation": percentage_deviation,
            "residual_rms": residual_rms,
            "max_abs_z": max_abs_z,
            "dominant_deviations": dominant,
            "deviations": deviations,
            "reference_alarm": (max_abs_z >= 3.0),
            "simulation_mode": simulation_mode,
        }
