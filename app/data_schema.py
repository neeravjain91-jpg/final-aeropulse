"""Canonical Telemetry Schema and Data Models for AeroPulse-X Virtual Data Lab.

Implements versioned, strongly typed canonical telemetry data points (Schema v2.0)
with explicit availability semantics (nullable fields) covering:
- Metadata & Mission Phase
- Engine Kinetics & Ambient Conditions
- Thermodynamics & Fluid Dynamics
- Vibration & Electrical Power
- Degradation & System Health Index
- Physical Faults & Failure Modes
- Sensor Faults & Sensor Trust
- Ground-Truth RUL (y_true = max(0, t_failure - t))
- Prognostic Predictions & Nominal 90% Prediction Bounds
- Virtual ECU & FADEC Supervisory States
- Virtual CAN Bus 2.0B Frames
- Virtual Flight Computer & Watchdog Metrics
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple, Union
import json


SCHEMA_VERSION: str = "2.0.0"
SCHEMA_NAME: str = "AeroPulseCanonicalTelemetry"


@dataclass
class CanonicalTelemetryPoint:
    # 1. Identification & Metadata
    timestamp: float                                      # Simulation timestamp in seconds
    trajectory_id: str                                    # Unique trajectory identifier
    engine_id: str = "ROTAX_914_F_TWIN_01"                # Engine serial/identifier
    mission_id: str = "MSN_NOMINAL_01"                    # Mission identifier
    mission_phase: str = "CRUISE"                         # STARTUP, TAKEOFF, CLIMB, CRUISE, HIGH_ALTITUDE, ENDURANCE, DESCENT, LANDING

    # 2. Kinetics & Ambient Environment
    RPM: float = 4650.0                                   # Engine crankshaft speed (RPM)
    throttle: float = 0.65                                # Commanded / actual throttle fraction [0.0, 1.0]
    engine_load: float = 0.65                             # Relative engine mechanical load [0.0, 1.0]
    MAP: float = 28.5                                     # Manifold Absolute Pressure (inHg)
    manifold_pressure: float = 96.5                       # Manifold Absolute Pressure (kPa)
    ambient_temperature: float = 15.0                     # Ambient air temperature (deg C)
    ambient_pressure: float = 101.325                     # Ambient atmospheric pressure (kPa)
    altitude: float = 5000.0                              # Barometric altitude (ft)
    vertical_speed: float = 0.0                           # Vertical climb/descent rate (ft/min)
    ground_speed: float = 85.0                            # Aircraft ground speed (knots)

    # 3. Thermodynamics & Fluid Dynamics
    CHT: float = 110.0                                    # Cylinder Head Temperature (deg C)
    coolant_temperature: float = 85.0                     # EFI Water / Coolant temperature (deg C)
    EGT: float = 780.0                                    # Mean Exhaust Gas Temperature (deg C)
    oil_pressure: float = 45.0                            # Engine oil pressure (psi)
    oil_temperature: float = 92.0                         # Engine oil temperature (deg C)
    fuel_flow: float = 22.5                               # Fuel flow rate (L/h)
    airflow: float = 265.0                                # Induction mass air flow (kg/h)
    AFR_or_lambda: float = 14.7                           # Air-to-fuel ratio (or equivalence ratio)
    torque: float = 115.0                                 # Shaft torque (N*m)
    brake_power: float = 56.0                             # Brake power output (kW)

    # 4. Vibration & Electrical Power
    vibration: float = 1.15                               # Tri-axial engine vibration RMS (g)
    bus_voltage: float = 28.0                             # 28V DC Avionics bus voltage (V)
    current: float = 18.5                                 # Total electrical current draw (A)
    battery_SOC: float = 98.0                             # Battery state of charge (%)
    alternator_temperature: float = 65.0                  # Alternator stator temperature (deg C)

    # 5. System Health & Degradation
    health_index: float = 95.0                            # Continuous engine health index [0.0, 100.0]
    degradation_severity: float = 0.0                     # Normalized degradation severity [0.0, 1.0]
    degradation_stage: str = "HEALTHY"                    # HEALTHY, EARLY, MODERATE, SEVERE, CRITICAL

    # 6. Physical Fault States
    fault_present: bool = False                           # True if physical engine fault active
    fault_type: str = "none"                              # none, overheating, lubrication, mechanical, injector, misfire, electrical, compound
    fault_severity: float = 0.0                           # Physical fault magnitude [0.0, 1.0]
    failure_mode: str = "none"                            # Specific physical degradation mechanism

    # 7. Sensor Quality & Sensor Faults
    sensor_fault_present: bool = False                    # True if transducer signal corrupted
    sensor_fault_type: str = "none"                       # none, noise, bias, drift, scale_error, quantization, saturation, stuck_at, dropout, jitter
    sensor_trust: float = 98.5                            # Composite sensor trust score [0.0, 100.0]

    # 8. Ground Truth RUL (ODE Derived)
    true_failure_time: Optional[float] = None             # Exact timestamp where H = 35.0 (hours)
    true_RUL: Optional[float] = None                      # max(0, true_failure_time - current_time) (hours)

    # 9. Prognostic Predictions & Uncertainty Bounds
    predicted_RUL: Optional[float] = None                 # Model predicted RUL (hours)
    RUL_lower: Optional[float] = None                     # 5th percentile prediction bound (hours)
    RUL_upper: Optional[float] = None                     # 95th percentile prediction bound (hours)
    RUL_confidence: Optional[float] = None                # Predictive confidence score (%)

    # 10. Virtual ECU & FADEC Supervisory States
    ECU_state: str = "ACTIVE_RUN"                         # OFF, CRANKING, ACTIVE_RUN, DERATED, EMERGENCY_STOP
    FADEC_state: str = "NOMINAL"                          # NOMINAL, MONITORING, DERATED_WARN, DERATED_CRITICAL, EMERGENCY_RTL
    DTC: List[str] = field(default_factory=list)          # Active Diagnostic Trouble Codes
    derate_command: float = 1.0                           # FADEC throttle ceiling clamp [0.0, 1.0]
    safety_action: str = "NONE"                           # NONE, ADVISORY, DERATE_80, DERATE_50, EMERGENCY_RTL

    # 11. Virtual CAN 2.0B Communication Metrics
    CAN_ID: Optional[str] = "0x100"                       # Primary CAN Arbitration ID
    CAN_DLC: int = 8                                      # Data length code (bytes)
    CAN_sequence: int = 0                                 # Rolling frame sequence counter (0..15)
    CAN_CRC_status: str = "VALID"                         # VALID, CRC_ERROR, STALE, CORRUPTED
    CAN_packet_loss: float = 0.0                          # Instantaneous packet loss rate [0.0, 1.0]
    CAN_latency: float = 0.045                            # Network transport latency (ms)

    # 12. Virtual Flight Computer & Watchdog
    flight_computer_state: str = "OPERATIONAL"            # OPERATIONAL, OVERLOADED, RECOVERING
    watchdog_state: str = "HEALTHY"                       # HEALTHY, WARNING, TRIPPED, RESTARTED
    deadline_missed: bool = False                         # True if scheduled cycle missed execution deadline

    # Schema Metadata
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        """Converts point to a canonical JSON-serializable dictionary."""
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                d[k] = None
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CanonicalTelemetryPoint:
        """Constructs a CanonicalTelemetryPoint with graceful field fallback."""
        valid_fields = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def validate_physical_bounds(self) -> Tuple[bool, List[str]]:
        """Validates that all telemetry measurements fall within plausible physical limits."""
        violations = []
        if not (0.0 <= self.RPM <= 7000.0):
            violations.append(f"RPM out of bounds: {self.RPM}")
        if not (0.0 <= self.throttle <= 1.0):
            violations.append(f"Throttle out of bounds: {self.throttle}")
        if not (-60.0 <= self.ambient_temperature <= 80.0):
            violations.append(f"Ambient temp out of bounds: {self.ambient_temperature}")
        if not (0.0 <= self.CHT <= 350.0):
            violations.append(f"CHT out of bounds: {self.CHT}")
        if not (0.0 <= self.oil_pressure <= 150.0):
            violations.append(f"Oil pressure out of bounds: {self.oil_pressure}")
        if not (0.0 <= self.health_index <= 100.0):
            violations.append(f"Health index out of bounds: {self.health_index}")
        if not (0.0 <= self.bus_voltage <= 40.0):
            violations.append(f"Bus voltage out of bounds: {self.bus_voltage}")
        if self.true_RUL is not None and self.true_RUL < 0.0:
            violations.append(f"True RUL cannot be negative: {self.true_RUL}")
        return len(violations) == 0, violations
