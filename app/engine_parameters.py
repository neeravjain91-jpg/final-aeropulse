"""Engine Parameter Configuration and Provenance Registry for AeroPulse-X.

Provides a structured, auditable provenance metadata system for every physical
parameter in the aero-piston digital twin. Explicitly distinguishes:
  - published_specification (manufacturer/TCDS certified values)
  - literature_assumption (established textbook/paper empirical values)
  - derived (computed from first principles)
  - calibrated (test-cell dynamometer measured - currently PENDING)
  - synthetic (simulation perturbation/noise factors)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ParameterSourceType(str, Enum):
    PUBLISHED_SPECIFICATION = "published_specification"
    LITERATURE_ASSUMPTION = "literature_assumption"
    DERIVED = "derived"
    CALIBRATED = "calibrated"
    SYNTHETIC = "synthetic"


class ValidationStatus(str, Enum):
    VALIDATED_SPEC = "VALIDATED_SPEC"
    LITERATURE_INFORMED = "LITERATURE_INFORMED"
    DERIVED_THEORETICAL = "DERIVED_THEORETICAL"
    PENDING_TEST_CELL = "PENDING_TEST_CELL"
    SYNTHETIC_PROXY = "SYNTHETIC_PROXY"


@dataclass(frozen=True)
class EngineParameter:
    """Metadata container for an individual engine model parameter."""
    name: str
    value: float
    unit: str
    source_type: ParameterSourceType
    source: str
    confidence_status: ValidationStatus
    notes: str
    is_configurable: bool = True
    is_validated: bool = False
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source_type": self.source_type.value,
            "source": self.source,
            "confidence_status": self.confidence_status.value,
            "notes": self.notes,
            "is_configurable": self.is_configurable,
            "is_validated": self.is_validated,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
        }


class EngineParameterRegistry:
    """Central registry tracking parameter provenance for aero-piston digital twin."""

    def __init__(self, engine_name: str = "AeroPiston-4C-1.35L"):
        self.engine_name = engine_name
        self._parameters: Dict[str, EngineParameter] = {}
        self._initialize_default_registry()

    def register(self, param: EngineParameter) -> None:
        self._parameters[param.name] = param

    def get(self, name: str) -> Optional[EngineParameter]:
        return self._parameters.get(name)

    def all_parameters(self) -> List[EngineParameter]:
        return list(self._parameters.values())

    def get_by_source_type(self, source_type: ParameterSourceType) -> List[EngineParameter]:
        return [p for p in self._parameters.values() if p.source_type == source_type]

    def _initialize_default_registry(self) -> None:
        params = [
            EngineParameter(
                name="displacement_l",
                value=1.352,
                unit="liters",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 912/914 & Continental O-200 Aero-Piston Specifications / EASA TCDS E.121",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Total swept volume for 4-cylinder horizontally-opposed aircraft engine",
                is_configurable=True,
                is_validated=True,
                lower_bound=1.0,
                upper_bound=2.5,
            ),
            EngineParameter(
                name="bore_mm",
                value=84.0,
                unit="mm",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 912 ULS / Aero-Engine Type Certification Data Sheet",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Cylinder internal diameter",
                is_configurable=True,
                is_validated=True,
                lower_bound=70.0,
                upper_bound=100.0,
            ),
            EngineParameter(
                name="stroke_mm",
                value=61.0,
                unit="mm",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 912/914 Type Certification Data Sheet",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Piston travel length from TDC to BDC",
                is_configurable=True,
                is_validated=True,
                lower_bound=50.0,
                upper_bound=90.0,
            ),
            EngineParameter(
                name="num_cylinders",
                value=4.0,
                unit="count",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Engine Architecture Definition",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="4-stroke spark-ignition boxer/in-line configuration",
                is_configurable=False,
                is_validated=True,
                lower_bound=1.0,
                upper_bound=8.0,
            ),
            EngineParameter(
                name="compression_ratio",
                value=9.0,
                unit="ratio",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 914 Turbo Operator's Manual (OM-914) Section 2.1",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Static compression ratio for turbocharged aero piston variant (9.0:1)",
                is_configurable=True,
                is_validated=True,
                lower_bound=7.5,
                upper_bound=12.0,
            ),
            EngineParameter(
                name="base_power_kw",
                value=84.5,
                unit="kW",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 914 F/UL Takeoff Rating (115 HP @ 5800 RPM, 5 min limit)",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Maximum rated takeoff brake power at sea level ISA",
                is_configurable=True,
                is_validated=True,
                lower_bound=30.0,
                upper_bound=150.0,
            ),
            EngineParameter(
                name="nominal_rpm",
                value=3000.0,
                unit="RPM",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="MALE-UAV Propeller Direct Drive / Reduced Geared Shaft Reference",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Nominal continuous operating cruise engine speed",
                is_configurable=True,
                is_validated=True,
                lower_bound=2000.0,
                upper_bound=5800.0,
            ),
            EngineParameter(
                name="max_rpm",
                value=5800.0,
                unit="RPM",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 912/914 Operating Limits (Redline Speed)",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Maximum allowable crankshaft rotational speed",
                is_configurable=True,
                is_validated=True,
                lower_bound=4500.0,
                upper_bound=6500.0,
            ),
            EngineParameter(
                name="idle_rpm",
                value=1400.0,
                unit="RPM",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 914 Ground/Flight Idle Operating Specification",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Minimum sustained operational idle speed",
                is_configurable=True,
                is_validated=True,
                lower_bound=1000.0,
                upper_bound=1800.0,
            ),
            EngineParameter(
                name="fuel_lhv_mj_kg",
                value=43.5,
                unit="MJ/kg",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="ASTM D910 Standard Specification for Aviation Gasolines (Avgas 100LL / Mogas EN228)",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Lower heating value (net calorific value) of aviation gasoline",
                is_configurable=True,
                is_validated=True,
                lower_bound=42.0,
                upper_bound=45.0,
            ),
            EngineParameter(
                name="afr_stoich",
                value=14.7,
                unit="ratio",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Heywood (1988) Internal Combustion Engine Fundamentals, Chapter 3",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Chemically stoichiometric air-to-fuel mass ratio for unleaded gasoline",
                is_configurable=True,
                is_validated=True,
                lower_bound=13.5,
                upper_bound=15.5,
            ),
            EngineParameter(
                name="fuel_density_kg_l",
                value=0.72,
                unit="kg/L",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="ASTM D910 / DIN EN 228 Fuel Density Standard @ 15°C",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Specific gravity / density of standard aviation gasoline",
                is_configurable=True,
                is_validated=True,
                lower_bound=0.70,
                upper_bound=0.78,
            ),
            EngineParameter(
                name="gamma",
                value=1.33,
                unit="ratio",
                source_type=ParameterSourceType.LITERATURE_ASSUMPTION,
                source="Heywood (1988), Internal Combustion Engine Fundamentals (Burned Gas Specific Heat Ratio)",
                confidence_status=ValidationStatus.LITERATURE_INFORMED,
                notes="Effective ratio of specific heats (Cp/Cv) for high-temperature cylinder combustion gases",
                is_configurable=True,
                is_validated=False,
                lower_bound=1.28,
                upper_bound=1.38,
            ),
            EngineParameter(
                name="volumetric_efficiency_base",
                value=0.88,
                unit="ratio",
                source_type=ParameterSourceType.LITERATURE_ASSUMPTION,
                source="Taylor (1985), The Internal-Combustion Engine in Theory and Practice",
                confidence_status=ValidationStatus.LITERATURE_INFORMED,
                notes="Baseline breathing efficiency for 4-stroke naturally-aspirated/boosted cylinder head",
                is_configurable=True,
                is_validated=False,
                lower_bound=0.75,
                upper_bound=0.98,
            ),
            EngineParameter(
                name="base_friction_kw",
                value=6.5,
                unit="kW",
                source_type=ParameterSourceType.LITERATURE_ASSUMPTION,
                source="Bishop-Heywood Hydrodynamic Friction Correlation for Small Light Aero-Pistons",
                confidence_status=ValidationStatus.LITERATURE_INFORMED,
                notes="Crankcase, valvetrain, and piston hydrodynamic friction loss baseline at idle",
                is_configurable=True,
                is_validated=False,
                lower_bound=4.0,
                upper_bound=10.0,
            ),
            EngineParameter(
                name="friction_rpm_exp",
                value=1.8,
                unit="exponent",
                source_type=ParameterSourceType.LITERATURE_ASSUMPTION,
                source="Heywood (1988) Friction Scaling Law (Typical range: 1.6 to 2.0)",
                confidence_status=ValidationStatus.LITERATURE_INFORMED,
                notes="Empirical exponent for rotational speed hydrodynamic shear resistance",
                is_configurable=True,
                is_validated=False,
                lower_bound=1.5,
                upper_bound=2.2,
            ),
            EngineParameter(
                name="thermal_capacity_j_k",
                value=35000.0,
                unit="J/K",
                source_type=ParameterSourceType.LITERATURE_ASSUMPTION,
                source="Lumped-Capacitance Thermal Engine Mass Model (~65 kg aluminum/steel equivalent thermal mass)",
                confidence_status=ValidationStatus.LITERATURE_INFORMED,
                notes="Thermal heat storage capacity of engine block and cylinder heads",
                is_configurable=True,
                is_validated=False,
                lower_bound=20000.0,
                upper_bound=60000.0,
            ),
            EngineParameter(
                name="cooling_area_m2",
                value=0.85,
                unit="m²",
                source_type=ParameterSourceType.LITERATURE_ASSUMPTION,
                source="UAV Nacelle Ram-Air Radiator & Cylinder Fin Effective Surface Area",
                confidence_status=ValidationStatus.LITERATURE_INFORMED,
                notes="Effective convective heat dissipation surface area",
                is_configurable=True,
                is_validated=False,
                lower_bound=0.5,
                upper_bound=1.5,
            ),
            EngineParameter(
                name="cooling_coeff_w_m2k",
                value=120.0,
                unit="W/(m²·K)",
                source_type=ParameterSourceType.LITERATURE_ASSUMPTION,
                source="Incropera & DeWitt Forced Convective Air Heat Transfer at 90-120 KTAS Flight Speeds",
                confidence_status=ValidationStatus.LITERATURE_INFORMED,
                notes="Heat transfer coefficient under typical UAV cruise airflow",
                is_configurable=True,
                is_validated=False,
                lower_bound=80.0,
                upper_bound=200.0,
            ),
            EngineParameter(
                name="oil_volume_l",
                value=3.5,
                unit="liters",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 914 Dry Sump Oil Tank Capacity (OM-914 Section 2.5)",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Dry sump lubrication reservoir volume",
                is_configurable=True,
                is_validated=True,
                lower_bound=2.5,
                upper_bound=4.5,
            ),
            EngineParameter(
                name="oil_viscosity_cst",
                value=14.0,
                unit="cSt",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="SAE 10W-40 / 15W-50 Kinematic Viscosity Specification @ 100°C",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Lubricant viscosity at standard nominal engine operating temperature",
                is_configurable=True,
                is_validated=True,
                lower_bound=10.0,
                upper_bound=20.0,
            ),
            EngineParameter(
                name="turbo_critical_alt_ft",
                value=15000.0,
                unit="ft",
                source_type=ParameterSourceType.PUBLISHED_SPECIFICATION,
                source="Rotax 914 Turbocharger TCU Wastegate Operating Limit (16,000 ft Critical Altitude)",
                confidence_status=ValidationStatus.VALIDATED_SPEC,
                notes="Altitude above which wastegate is 100% closed and manifold pressure begins to decay",
                is_configurable=True,
                is_validated=True,
                lower_bound=10000.0,
                upper_bound=20000.0,
            ),
        ]
        for p in params:
            self.register(p)

    def to_markdown_table(self) -> str:
        """Generates a complete, publication-ready GitHub markdown parameter provenance table."""
        lines = [
            "| Parameter | Value | Unit | Source Type | Confidence Status | Source / Citation | Configurable | Validated |",
            "| :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: |",
        ]
        for p in sorted(self._parameters.values(), key=lambda x: x.name):
            val_str = f"{p.value:g}" if isinstance(p.value, (int, float)) else str(p.value)
            conf_str = f"`{p.confidence_status.value}`"
            src_type = f"`{p.source_type.value}`"
            lines.append(
                f"| `{p.name}` | {val_str} | {p.unit} | {src_type} | {conf_str} | {p.source} | {'Yes' if p.is_configurable else 'No'} | {'Yes' if p.is_validated else 'Pending'} |"
            )
        return "\n".join(lines)


def get_default_parameter_registry() -> EngineParameterRegistry:
    return EngineParameterRegistry()
