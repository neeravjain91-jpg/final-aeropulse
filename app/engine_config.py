"""Configurable Engine Parameter Schema for AeroPulse-X Propulsion Digital Twin."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .engine_parameters import EngineParameterRegistry, get_default_parameter_registry


@dataclass
class EngineConfig:
    name: str = "AeroPiston-4C-1.35L"
    displacement_l: float = 1.352
    bore_mm: float = 84.0
    stroke_mm: float = 61.0
    num_cylinders: int = 4
    compression_ratio: float = 9.0
    gamma: float = 1.33
    fuel_lhv_mj_kg: float = 43.5
    afr_stoich: float = 14.7
    base_power_kw: float = 84.5
    nominal_rpm: float = 3000.0
    max_rpm: float = 5800.0
    idle_rpm: float = 1400.0
    base_friction_kw: float = 6.5
    friction_rpm_exp: float = 1.8
    thermal_capacity_j_k: float = 35000.0
    cooling_area_m2: float = 0.85
    cooling_coeff_w_m2k: float = 120.0
    oil_volume_l: float = 3.5
    oil_viscosity_cst: float = 14.0
    turbo_critical_alt_ft: float = 15000.0
    volumetric_efficiency_base: float = 0.88
    fuel_density_kg_l: float = 0.72

    @property
    def displacement_liters(self) -> float:
        return self.displacement_l

    @property
    def fuel_lower_heating_value_mj_kg(self) -> float:
        return self.fuel_lhv_mj_kg

    @property
    def air_fuel_ratio_stoich(self) -> float:
        return self.afr_stoich

    @property
    def rated_power_kw(self) -> float:
        return self.base_power_kw

    def get_registry(self) -> EngineParameterRegistry:
        """Returns the formal parameter provenance registry for this engine configuration."""
        return get_default_parameter_registry()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "displacement_l": self.displacement_l,
            "bore_mm": self.bore_mm,
            "stroke_mm": self.stroke_mm,
            "num_cylinders": self.num_cylinders,
            "compression_ratio": self.compression_ratio,
            "fuel_lhv_mj_kg": self.fuel_lhv_mj_kg,
            "base_power_kw": self.base_power_kw,
            "nominal_rpm": self.nominal_rpm,
            "max_rpm": self.max_rpm,
            "idle_rpm": self.idle_rpm,
            "gamma": self.gamma,
            "afr_stoich": self.afr_stoich,
            "base_friction_kw": self.base_friction_kw,
            "cooling_area_m2": self.cooling_area_m2,
            "cooling_coeff_w_m2k": self.cooling_coeff_w_m2k,
            "oil_volume_l": self.oil_volume_l,
            "oil_viscosity_cst": self.oil_viscosity_cst,
            "turbo_critical_alt_ft": self.turbo_critical_alt_ft,
            "volumetric_efficiency_base": self.volumetric_efficiency_base,
            "fuel_density_kg_l": self.fuel_density_kg_l,
        }

    @classmethod
    def default_135l(cls) -> EngineConfig:
        return cls()

    @classmethod
    def custom(cls, **kwargs) -> EngineConfig:
        return cls(**kwargs)


def default_engine_config() -> EngineConfig:
    return EngineConfig.default_135l()
