from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
import math

@dataclass(frozen=True)
class SensorAssessment:
    name: str
    trust_score: float
    status: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "trust_score": round(self.trust_score, 1),
            "status": self.status,
            "reason": self.reason,
        }

def _status(score: float) -> str:
    if score >= 80:
        return "TRUSTED"
    if score >= 55:
        return "CHECK"
    return "SUSPECT"

def assess_sensor_health(telemetry: dict, twin: dict) -> dict:
    z = twin.get("z_scores", {})
    results: list[SensorAssessment] = []

    # 1. EGT multi-channel peer cross-check
    egt_names = ["EGT1", "EGT2", "EGT3"]
    for name in egt_names:
        score = 100.0
        reason = "consistent with peer EGT channels"
        if name in telemetry:
            val = telemetry.get(name)
            if val is None or (isinstance(val, (int, float)) and (math.isnan(val) or val <= 0.0)):
                score = 10.0
                reason = "Sensor dropout or non-positive value"
                results.append(SensorAssessment(name, score, _status(score), reason))
                continue
        others = [abs(z.get(x, 0.0)) for x in egt_names if x != name]
        if abs(z.get(name, 0.0)) > 4.0 and max(others) < 1.5:
            score = 35.0
            reason = "single-channel EGT deviation inconsistent with peer channels"
        elif abs(z.get(name, 0.0)) > 3.0 and max(others) < 2.0:
            score = 60.0
            reason = "EGT channel deviates more than peer channels"
        results.append(SensorAssessment(name, score, _status(score), reason))

    # 2. CHT cross-check against other thermal channels
    avg_egt_abs = sum(abs(z.get(x, 0.0)) for x in egt_names) / 3.0
    cht_score = 100.0
    cht_reason = "cylinder head temperature consistent with thermal state"
    cht_z = abs(z.get("CHT", 0.0))
    water_z = abs(z.get("EFI_Water_Temp", 0.0))
    oil_t_z = abs(z.get("Oil_Temp", 0.0))

    if "CHT" in telemetry:
        cht_val = telemetry.get("CHT")
        if cht_val is None or (isinstance(cht_val, (int, float)) and (math.isnan(cht_val) or cht_val < 32.0 or cht_val > 550.0)):
            cht_score = 10.0
            cht_reason = "CHT sensor dropout / implausible out-of-range value"
        elif cht_z > 2.5 and avg_egt_abs < 1.2 and water_z < 1.2:
            cht_score = 30.0
            cht_reason = "CHT spike without corroboration in coolant or exhaust gas temps"
        elif cht_z > 2.0 and avg_egt_abs < 1.5:
            cht_score = 60.0
            cht_reason = "CHT deviation has weak thermal corroboration"
    results.append(SensorAssessment("CHT", cht_score, _status(cht_score), cht_reason))

    # 3. Coolant Water Temp
    water_score = 100.0
    water_reason = "thermal channels are mutually consistent"
    if "EFI_Water_Temp" in telemetry:
        water_val = telemetry.get("EFI_Water_Temp")
        if water_val is None or (isinstance(water_val, (int, float)) and (math.isnan(water_val) or water_val < 32.0 or water_val > 350.0)):
            water_score = 10.0
            water_reason = "coolant temperature dropout / implausible value"
        elif water_z > 2.5 and avg_egt_abs < 1.2 and oil_t_z < 1.2:
            water_score = 25.0
            water_reason = "water-temperature excursion is not supported by other thermal channels"
        elif water_z > 2.0 and avg_egt_abs < 1.5:
            water_score = 55.0
            water_reason = "water-temperature deviation has weak corroboration"
    results.append(SensorAssessment("EFI_Water_Temp", water_score, _status(water_score), water_reason))

    # 4. Oil Pressure & Temperature
    oil_score = 100.0
    oil_reason = "oil pressure is consistent with lubrication state"
    oil_p_z = abs(z.get("Oil_Pressure", 0.0))
    if "Oil_Pressure" in telemetry:
        op_val = telemetry.get("Oil_Pressure")
        if op_val is None or (isinstance(op_val, (int, float)) and (math.isnan(op_val) or op_val <= 0.0 or op_val > 150.0)):
            oil_score = 10.0
            oil_reason = "oil pressure sensor dropout / implausible value"
        elif oil_p_z > 3.5 and oil_t_z < 0.8:
            oil_score = 50.0
            oil_reason = "large oil-pressure deviation with little thermal corroboration"
    results.append(SensorAssessment("Oil_Pressure", oil_score, _status(oil_score), oil_reason))

    # 5. Vibration accelerometer
    vib_z = abs(z.get("Vibration", 0.0))
    rpm_z = abs(z.get("Engine_RPM", 0.0))
    vib_score = 100.0
    vib_reason = "vibration accelerometer consistent with dynamic load"
    if "Vibration" in telemetry:
        vib_val = telemetry.get("Vibration")
        if vib_val is None or (isinstance(vib_val, (int, float)) and (math.isnan(vib_val) or vib_val < 0.05 or vib_val > 25.0)):
            vib_score = 10.0
            vib_reason = "vibration accelerometer dropout / disconnected"
        elif vib_z > 2.8 and rpm_z < 1.2 and oil_p_z < 1.2:
            vib_score = 30.0
            vib_reason = "high accelerometer vibration spike without mechanical RPM or lubrication anomaly"
        elif vib_z > 2.0 and rpm_z < 1.5:
            vib_score = 60.0
            vib_reason = "isolated accelerometer elevation"
    results.append(SensorAssessment("Vibration", vib_score, _status(vib_score), vib_reason))

    # 6. Fuel flow transducer
    ff_z = abs(z.get("Fuel_Flow", 0.0))
    map_z = abs(z.get("MAP_Injector", 0.0))
    ff_score = 100.0
    ff_reason = "fuel metering consistent with manifold pressure and EGT"
    if "Fuel_Flow" in telemetry:
        ff_val = telemetry.get("Fuel_Flow")
        if ff_val is None or (isinstance(ff_val, (int, float)) and (math.isnan(ff_val) or ff_val <= 0.0 or ff_val > 200.0)):
            ff_score = 10.0
            ff_reason = "fuel flow transducer dropout / implausible reading"
        elif ff_z > 2.8 and map_z < 1.2 and avg_egt_abs < 1.2:
            ff_score = 30.0
            ff_reason = "fuel flow transducer shift without manifold pressure or EGT response"
        elif ff_z > 2.0 and map_z < 1.5:
            ff_score = 60.0
            ff_reason = "fuel flow signal anomaly with weak thermodynamic coupling"
    results.append(SensorAssessment("Fuel_Flow", ff_score, _status(ff_score), ff_reason))

    assessments = [item.as_dict() for item in results]
    overall = min(item["trust_score"] for item in assessments) if assessments else 100.0
    suspects = [item for item in assessments if item["status"] == "SUSPECT"]
    overall_status = _status(overall)

    return {
        "overall_trust_score": overall,
        "overall_status": overall_status,
        "sensors": assessments,
        "channels": assessments,
        "suspect_sensors": [item["name"] for item in suspects],
        "suspect_channels": [item["name"] for item in suspects],
        "is_sensor_fault_only": (overall < 50.0 and len(suspects) <= 2),
    }

