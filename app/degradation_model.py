from __future__ import annotations

from dataclasses import dataclass


COMPONENTS = ("injector", "lubrication", "thermal", "mechanical", "electrical", "misfire", "sensor")


@dataclass(frozen=True)
class DegradationState:
    injector: float = 0.0
    lubrication: float = 0.0
    thermal: float = 0.0
    mechanical: float = 0.0
    electrical: float = 0.0
    misfire: float = 0.0
    sensor: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name, 0.0)) for name in COMPONENTS}

    @staticmethod
    def _clip(value: float) -> float:
        return max(0.0, min(1.0, float(value)))


class ContinuousDegradationModel:
    """Deterministic, physically grounded component degradation model for UAV mission simulation.

    Severity is represented on [0, 1]. The model couples thermodynamic, friction,
    and electrical degradation kinetics instead of adding uncorrelated Gaussian noise.
    """

    def state_at(self, mission_hours: float, rates: dict[str, float] | None = None) -> DegradationState:
        hours = max(0.0, float(mission_hours))
        rates = rates or {}
        values = {name: DegradationState._clip(hours * float(rates.get(name, 0.0))) for name in COMPONENTS}
        return DegradationState(**values)

    def apply(self, telemetry: dict, state: DegradationState) -> dict:
        data = dict(telemetry)
        d = state.as_dict()

        # 1. Injector: fuel-delivery loss changes fuel flow, cylinder AFR, EGT asymmetry, and efficiency.
        if d.get("injector", 0.0) > 0.0:
            x = d["injector"]
            data["Fuel_Flow"] = float(data.get("Fuel_Flow", 0.0)) * (1.0 - 0.22 * x)
            data["MAP_Injector"] = float(data.get("MAP_Injector", 30.0)) * (1.0 + 0.25 * x)
            data["EGT1"] = float(data.get("EGT1", 0.0)) * (1.0 - 0.12 * x)
            data["EGT2"] = float(data.get("EGT2", 0.0)) * (1.0 + 0.06 * x)
            data["EGT3"] = float(data.get("EGT3", 0.0)) * (1.0 - 0.10 * x)
            data["Efficiency"] = float(data.get("Efficiency", 0.0)) * (1.0 - 0.16 * x)

        # 2. Lubrication: lower oil pressure, elevated oil temperature, increased friction, and vibration.
        if d.get("lubrication", 0.0) > 0.0:
            x = d["lubrication"]
            data["Oil_Pressure"] = max(12.0, float(data.get("Oil_Pressure", 0.0)) * (1.0 - 0.50 * x))
            data["Oil_Temp"] = float(data.get("Oil_Temp", 0.0)) * (1.0 + 0.22 * x)
            data["Vibration"] = float(data.get("Vibration", 0.0)) * (1.0 + 0.45 * x)
            data["Efficiency"] = float(data.get("Efficiency", 0.0)) * (1.0 - 0.12 * x)

        # 3. Thermal: heat rejection deficit increases CHT, coolant, and oil temperatures non-linearly.
        if d.get("thermal", 0.0) > 0.0:
            x = d["thermal"]
            for key in ("EGT1", "EGT2", "EGT3"):
                data[key] = float(data.get(key, 0.0)) * (1.0 + 0.16 * x)
            data["CHT"] = float(data.get("CHT", 0.0)) * (1.0 + 0.24 * x)
            data["EFI_Water_Temp"] = float(data.get("EFI_Water_Temp", 0.0)) * (1.0 + 0.18 * x)
            data["Oil_Temp"] = float(data.get("Oil_Temp", 0.0)) * (1.0 + 0.14 * x)
            data["Efficiency"] = float(data.get("Efficiency", 0.0)) * (1.0 - 0.12 * x)

        # 4. Mechanical: bearing / ring wear elevates high-frequency vibration, reduces compression and RPM.
        if d.get("mechanical", 0.0) > 0.0:
            x = d["mechanical"]
            data["Vibration"] = float(data.get("Vibration", 0.0)) * (1.0 + 0.95 * x)
            data["Engine_RPM"] = float(data.get("Engine_RPM", 0.0)) * (1.0 - 0.05 * x)
            data["Oil_Pressure"] = float(data.get("Oil_Pressure", 0.0)) * (1.0 - 0.10 * x)
            data["Brake_Power_kW"] = float(data.get("Brake_Power_kW", 60.0)) * (1.0 - 0.15 * x)

        # 5. Electrical: alternator diode / regulator degradation reduces bus voltage and elevates alternator temperature.
        if d.get("electrical", 0.0) > 0.0:
            x = d["electrical"]
            data["Battery_Voltage"] = max(16.0, float(data.get("Battery_Voltage", 0.0)) * (1.0 - 0.20 * x))
            data["Battery_Current"] = float(data.get("Battery_Current", 0.0)) * (1.0 - 0.25 * x)
            data["Alternator_Temp"] = float(data.get("Alternator_Temp", 0.0)) * (1.0 + 0.28 * x)

        # 6. Misfire: cyclic combustion torque loss causes marked EGT drop on affected cylinder and vibration spike.
        if d.get("misfire", 0.0) > 0.0:
            x = d["misfire"]
            data["EGT1"] = float(data.get("EGT1", 0.0)) * (1.0 - 0.28 * x)
            data["EGT2"] = float(data.get("EGT2", 0.0)) * (1.0 + 0.03 * x)
            data["Vibration"] = float(data.get("Vibration", 0.0)) + 1.30 * x
            data["Engine_RPM"] = max(1400.0, float(data.get("Engine_RPM", 0.0)) * (1.0 - 0.06 * x))
            data["Efficiency"] = float(data.get("Efficiency", 0.0)) * (1.0 - 0.18 * x)

        # 7. Sensor: isolated transducer drift / bias leaving engine thermodynamic state unaffected.
        if d.get("sensor", 0.0) > 0.0:
            x = d["sensor"]
            data["EFI_Water_Temp"] = float(data.get("EFI_Water_Temp", 0.0)) + 30.0 * x
            data["MAP_Injector"] = float(data.get("MAP_Injector", 0.0)) * (1.0 + 0.12 * x)

        data["Degradation_Severity"] = max(d.values())
        data["Degradation_State"] = d
        return data


def generate_physics_synthetic_dataset(
    base_telemetry: dict,
    steps_per_mode: int = 30,
    time_step_hours: float = 0.1,
) -> dict[str, list[dict]]:
    """Generates controlled benchmark time-series trajectories for model evaluation and validation.

    Produces trajectories covering:
      - healthy baseline
      - early progressive degradation
      - moderate degradation
      - severe degradation
      - sudden fault onset
      - progressive multi-component degradation
      - post-remediation recovery
      - sensor-only transducer fault (isolated from thermodynamics)
    """
    model = ContinuousDegradationModel()
    dataset: dict[str, list[dict]] = {
        "healthy": [],
        "early_degradation": [],
        "moderate_degradation": [],
        "severe_degradation": [],
        "onset_progression": [],
        "recovery": [],
        "sensor_only_fault": [],
    }

    # 1. Healthy baseline
    for step in range(steps_per_mode):
        t = step * time_step_hours
        state = model.state_at(t, rates={})
        sample = model.apply(base_telemetry, state)
        sample["time_hours"] = round(t, 3)
        sample["ground_truth_state"] = "Normal"
        dataset["healthy"].append(sample)

    # 2. Early progressive degradation (thermal & lubrication)
    for step in range(steps_per_mode):
        t = step * time_step_hours
        state = model.state_at(t, rates={"thermal": 0.08, "lubrication": 0.05})
        sample = model.apply(base_telemetry, state)
        sample["time_hours"] = round(t, 3)
        sample["ground_truth_state"] = "Watch" if state.thermal > 0.15 else "Normal"
        dataset["early_degradation"].append(sample)

    # 3. Moderate degradation
    for step in range(steps_per_mode):
        t = (step + 10) * time_step_hours
        state = model.state_at(t, rates={"thermal": 0.18, "lubrication": 0.15})
        sample = model.apply(base_telemetry, state)
        sample["time_hours"] = round(t, 3)
        sample["ground_truth_state"] = "Warning"
        dataset["moderate_degradation"].append(sample)

    # 4. Severe degradation
    for step in range(steps_per_mode):
        t = (step + 25) * time_step_hours
        state = model.state_at(t, rates={"thermal": 0.35, "lubrication": 0.30, "mechanical": 0.25})
        sample = model.apply(base_telemetry, state)
        sample["time_hours"] = round(t, 3)
        sample["ground_truth_state"] = "Critical"
        dataset["severe_degradation"].append(sample)

    # 5. Sudden fault onset & progression
    for step in range(steps_per_mode):
        t = step * time_step_hours
        rates = {"misfire": 0.40} if step >= 10 else {}
        state = model.state_at(t - 1.0 if step >= 10 else 0.0, rates=rates)
        sample = model.apply(base_telemetry, state)
        sample["time_hours"] = round(t, 3)
        sample["ground_truth_state"] = "Warning" if step >= 10 else "Normal"
        dataset["onset_progression"].append(sample)

    # 6. Recovery trajectory
    for step in range(steps_per_mode):
        t = step * time_step_hours
        sev = max(0.0, 0.80 - (step / float(steps_per_mode)) * 0.80)
        state = DegradationState(lubrication=sev, thermal=sev * 0.5)
        sample = model.apply(base_telemetry, state)
        sample["time_hours"] = round(t, 3)
        sample["ground_truth_state"] = "Normal" if sev < 0.20 else "Warning"
        dataset["recovery"].append(sample)

    # 7. Sensor-only fault (thermodynamically isolated)
    for step in range(steps_per_mode):
        t = step * time_step_hours
        state = DegradationState(sensor=0.85)
        sample = model.apply(base_telemetry, state)
        sample["time_hours"] = round(t, 3)
        sample["ground_truth_state"] = "Sensor_Anomaly_Only"
        dataset["sensor_only_fault"].append(sample)

    return dataset

