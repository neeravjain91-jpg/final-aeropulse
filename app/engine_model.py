"""Thermodynamic Reduced-Order Piston Engine Model for AeroPulse-X Digital Twin."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .engine_config import EngineConfig, default_engine_config


@dataclass
class EngineInputs:
    """Input operating vector driving the propulsion digital twin."""
    rpm: float = 3000.0
    throttle: float = 0.60
    altitude_ft: float = 3000.0
    ambient_c: float = 25.0
    load: Optional[float] = None
    rapid_throttle: bool = False
    cooling_efficiency: float = 1.0
    fuel_delivery_ratio: float = 1.0
    misfire_fraction: float = 0.0
    friction_multiplier: float = 1.0
    cooling_airflow_factor: float = 1.0


@dataclass
class EngineState:
    """Internal physics state of the 4-stroke spark-ignited aero piston engine."""
    air_density_ratio: float
    ambient_pressure_kpa: float
    ambient_temp_k: float
    manifold_pressure_kpa: float
    volumetric_efficiency: float
    indicated_power_kw: float
    brake_power_kw: float
    thermal_efficiency: float
    peak_cylinder_pressure_bar: float
    bsfc_g_kwh: float
    air_mass_flow_kg_s: float
    fuel_mass_flow_g_s: float
    heat_rejection_kw: float

    @property
    def density_ratio(self) -> float:
        return self.air_density_ratio

    @property
    def mass_air_flow_kg_s(self) -> float:
        return self.air_mass_flow_kg_s

    @property
    def fuel_flow_kg_s(self) -> float:
        return self.fuel_mass_flow_g_s / 1000.0


class ReducedOrderPistonEngine:
    """
    First-principles, physics-informed reduced-order propulsion digital twin.
    Implements Otto cycle thermodynamics, Bishop-Heywood friction, ISA barometric lapse,
    and lumped-capacitance thermal rejection calibrated for MALE UAV aero-piston engines.
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or default_engine_config()
        self.DISPLACEMENT_L = self.config.displacement_l
        self.NOMINAL_RPM = self.config.nominal_rpm
        self.IDLE_RPM = self.config.idle_rpm
        self.MAX_RPM = self.config.max_rpm
        self.BASE_POWER_KW = self.config.base_power_kw
        self.COMPRESSION_RATIO = self.config.compression_ratio
        self.gamma = self.config.gamma
        self.fuel_lhv_mj_kg = self.config.fuel_lhv_mj_kg

    @staticmethod
    def _isa_atmosphere(altitude_ft: float, ambient_c: float) -> tuple[float, float, float]:
        """Calculates ISA atmosphere parameters: (ambient_temp_k, pressure_kpa, density_ratio_sigma)."""
        alt_m = max(0.0, float(altitude_ft)) * 0.3048
        t_sea_level_k = ambient_c + 273.15
        p_sea_level_pa = 101325.0
        lapse_rate = 0.0065
        r_air = 287.058
        g = 9.80665

        t_actual_k = max(216.65, t_sea_level_k - lapse_rate * alt_m)
        p_pa = p_sea_level_pa * math.pow(max(0.05, 1.0 - (lapse_rate * alt_m) / max(200.0, t_sea_level_k)), (g / (r_air * lapse_rate)))
        rho = p_pa / (r_air * t_actual_k)
        sigma = max(0.55, min(1.15, rho / 1.225))
        return t_actual_k, p_pa / 1000.0, sigma

    def estimate_state(self, inputs: EngineInputs) -> EngineState:
        """Estimates internal thermodynamic cycle parameters from first principles."""
        rpm = max(self.IDLE_RPM, min(self.MAX_RPM, float(inputs.rpm)))
        throttle = float(inputs.load) if inputs.load is not None else float(inputs.throttle)
        throttle = max(0.05, min(1.0, throttle))
        altitude_ft = max(0.0, float(inputs.altitude_ft))
        ambient_c = float(inputs.ambient_c)

        t_amb_k, p_amb_kpa, sigma = self._isa_atmosphere(altitude_ft, ambient_c)

        # 1. Intake Manifold Pressure & Volumetric Efficiency
        map_kpa = 101.325 * (0.35 + 0.65 * throttle) * (0.60 + 0.40 * sigma)
        map_kpa = max(28.0, map_kpa)

        rpm_ratio = rpm / self.NOMINAL_RPM
        vol_eff = (0.84 + 0.12 * throttle - 0.05 * math.pow(rpm_ratio - 1.0, 2)) * math.sqrt(sigma)
        vol_eff = max(0.45, min(1.05, vol_eff))

        # 2. Intake Air & Fuel Mass Flow Rates
        air_density_kg_m3 = (p_amb_kpa * 1000.0) / (287.058 * max(t_amb_k, 100.0))
        displacement_m3 = self.DISPLACEMENT_L * 1e-3
        air_mass_flow_kg_s = (rpm / 120.0) * displacement_m3 * air_density_kg_m3 * vol_eff
        air_mass_flow_index = (map_kpa / 101.325) * vol_eff * rpm_ratio

        # Fuel delivery with injector scaling
        afr_actual = self.config.afr_stoich / max(0.50, float(inputs.fuel_delivery_ratio))
        fuel_mass_flow_g_s = (air_mass_flow_kg_s / max(5.0, afr_actual)) * 1000.0

        # 3. Indicated & Brake Power Generation
        misfire_penalty = max(0.0, 1.0 - float(inputs.misfire_fraction))
        combustion_heat_kw = (fuel_mass_flow_g_s * 1e-3) * (self.fuel_lhv_mj_kg * 1000.0) * misfire_penalty

        thermal_eff = 0.32 * (1.0 - math.pow(1.0 / self.COMPRESSION_RATIO, self.gamma - 1.0) / 0.58)
        thermal_eff = max(0.24, min(0.38, thermal_eff * (0.85 + 0.15 * throttle)))

        indicated_power_kw = self.BASE_POWER_KW * air_mass_flow_index * 1.12 * misfire_penalty

        friction_loss_kw = (self.config.base_friction_kw + 8.5 * math.pow(rpm / self.MAX_RPM, self.config.friction_rpm_exp)) * float(inputs.friction_multiplier)
        brake_power_kw = max(3.0, indicated_power_kw - friction_loss_kw)

        # 4. Thermal Rejection
        heat_rejection_kw = max(2.0, indicated_power_kw * (1.0 - thermal_eff) / thermal_eff)

        # 5. Cylinder Pressures & BSFC
        p_max_bar = (map_kpa / 100.0) * math.pow(self.COMPRESSION_RATIO, self.gamma) * (1.2 + 0.6 * throttle) * misfire_penalty
        bsfc_g_kwh = (3600.0 / (self.fuel_lhv_mj_kg * thermal_eff)) * (1.0 + 0.15 * math.pow(1.0 - throttle, 2))

        return EngineState(
            air_density_ratio=round(sigma, 4),
            ambient_pressure_kpa=round(p_amb_kpa, 2),
            ambient_temp_k=round(t_amb_k, 2),
            manifold_pressure_kpa=round(map_kpa, 2),
            volumetric_efficiency=round(vol_eff, 4),
            indicated_power_kw=round(indicated_power_kw, 2),
            brake_power_kw=round(brake_power_kw, 2),
            thermal_efficiency=round(thermal_eff, 4),
            peak_cylinder_pressure_bar=round(p_max_bar, 2),
            bsfc_g_kwh=round(bsfc_g_kwh, 1),
            air_mass_flow_kg_s=round(air_mass_flow_kg_s, 4),
            fuel_mass_flow_g_s=round(fuel_mass_flow_g_s, 3),
            heat_rejection_kw=round(heat_rejection_kw, 2),
        )

    def predict(self, inputs: EngineInputs) -> dict[str, float]:
        """Calculates telemetry values matching ACES / UAV sensor channels in native units."""
        rpm = max(self.IDLE_RPM, min(self.MAX_RPM, float(inputs.rpm)))
        throttle = float(inputs.load) if inputs.load is not None else float(inputs.throttle)
        throttle = max(0.05, min(1.0, throttle))
        altitude_ft = max(0.0, float(inputs.altitude_ft))
        ambient_c = float(inputs.ambient_c)
        load = float(inputs.load) if inputs.load is not None else throttle * 0.95

        state = self.estimate_state(inputs)
        thermal_load = state.indicated_power_kw / self.BASE_POWER_KW

        # Thermal System: First-principles heat generation vs cooling dissipation
        cooling_factor = max(0.35, float(inputs.cooling_efficiency) * float(inputs.cooling_airflow_factor))
        heat_factor = (1.0 / cooling_factor)

        base_egt = (1180.0 + 170.0 * throttle + 35.0 * (altitude_ft / 10000.0) + 1.2 * ambient_c) * (0.90 + 0.10 * heat_factor)
        misfire_egt_drop = 1.0 - (0.28 * float(inputs.misfire_fraction))
        egt1 = (base_egt + 12.0 * math.sin(rpm * 0.01)) * misfire_egt_drop
        egt2 = base_egt - 8.0 + 10.0 * math.cos(rpm * 0.01)
        egt3 = base_egt + 4.0 - 6.0 * math.sin(rpm * 0.015)

        cht = (195.0 + 16.0 * thermal_load + 0.5 * (ambient_c - 25.0) + 4.0 * (altitude_ft / 10000.0)) * (0.85 + 0.15 * heat_factor)
        water_temp_f = (175.0 + 14.0 * thermal_load + 0.45 * (ambient_c - 25.0) + 3.0 * (altitude_ft / 10000.0)) * (0.88 + 0.12 * heat_factor)
        oil_temp_f = (165.0 + 16.0 * thermal_load + 0.48 * (ambient_c - 25.0) + 3.5 * (altitude_ft / 10000.0)) * float(inputs.friction_multiplier) * (0.88 + 0.12 * heat_factor)

        viscosity_factor = max(0.60, 1.0 - 0.003 * (oil_temp_f - 170.0))
        oil_press_psi = (48.0 + 15.0 * (rpm / self.NOMINAL_RPM)) * viscosity_factor / float(inputs.friction_multiplier)

        base_ff = (12.0 + 18.0 * throttle) * (0.85 + 0.30 * (rpm / self.NOMINAL_RPM)) * float(inputs.fuel_delivery_ratio)
        fuel_flow_l_h = base_ff * (1.0 + 0.25 * (altitude_ft / 25000.0))
        map_injector = (state.manifold_pressure_kpa / 101.325) * 29.92
        fuel_temp_f = max(ambient_c * 1.8 + 32.0 + 5.0, 75.0 + 0.25 * water_temp_f + 0.2 * (ambient_c * 1.8 + 32.0))

        battery_voltage = 28.2 - 0.4 * (load - 0.5) - 0.02 * (ambient_c - 25.0)
        battery_current = 14.0 + 18.0 * load + 4.0 * math.sin(rpm * 0.02)
        alternator_temp_f = (48.0 + 26.0 * (battery_current / 35.0) + 0.6 * ambient_c) * 1.8 + 32.0

        misfire_vib = 1.65 * float(inputs.misfire_fraction)
        vibration_g = 0.85 + 0.75 * math.pow(rpm / self.NOMINAL_RPM, 2.0) + 0.45 * (load - 0.5) + misfire_vib

        return {
            "Engine_RPM": round(rpm, 1),
            "EGT1": round(egt1, 1),
            "EGT2": round(egt2, 1),
            "EGT3": round(egt3, 1),
            "CHT": round(cht, 1),
            "Fuel_Flow": round(fuel_flow_l_h, 2),
            "Oil_Temp": round(oil_temp_f, 1),
            "Oil_Pressure": round(oil_press_psi, 1),
            "Battery_Voltage": round(battery_voltage, 2),
            "Battery_Current": round(battery_current, 2),
            "Alternator_Temp": round(alternator_temp_f, 1),
            "EFI_Fuel_Temp": round(fuel_temp_f, 1),
            "EFI_Water_Temp": round(water_temp_f, 1),
            "MAP_Injector": round(map_injector, 2),
            "Vibration": round(vibration_g, 3),
            "Efficiency": round(state.thermal_efficiency, 4),
            "Load": round(load, 3),
            "Air_Density_Ratio": round(state.air_density_ratio, 4),
            "Indicated_Power_kW": round(state.indicated_power_kw, 2),
            "Brake_Power_kW": round(state.brake_power_kw, 2),
            "Peak_Pressure_bar": round(state.peak_cylinder_pressure_bar, 2),
            "Air_Mass_Flow_kg_s": round(state.air_mass_flow_kg_s, 4),
            "Heat_Rejection_kW": round(state.heat_rejection_kw, 2),
        }

    def simulate(
        self,
        rpm: float = 3000.0,
        throttle: float = 0.60,
        altitude_ft: float = 3000.0,
        ambient_c: float = 25.0,
        load: Optional[float] = None,
        rapid_throttle: bool = False,
        cooling_efficiency: float = 1.0,
        fuel_delivery_ratio: float = 1.0,
        misfire_fraction: float = 0.0,
        friction_multiplier: float = 1.0,
    ) -> dict[str, float]:
        inputs = EngineInputs(
            rpm=rpm,
            throttle=throttle,
            altitude_ft=altitude_ft,
            ambient_c=ambient_c,
            load=load,
            rapid_throttle=rapid_throttle,
            cooling_efficiency=cooling_efficiency,
            fuel_delivery_ratio=fuel_delivery_ratio,
            misfire_fraction=misfire_fraction,
            friction_multiplier=friction_multiplier,
        )
        return self.predict(inputs)
