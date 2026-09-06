"""Virtual Full Authority Digital Engine Controller (FADEC) Supervisory Logic.

Simulates the onboard FADEC supervisory controller for AeroPulse-X.
Responsibilities:
  - Ingests and decodes CAN frames from the Virtual ECU
  - Monitors certified engine operating limits & thresholds
  - Generates formal Diagnostic Trouble Codes (DTCs) with severity levels
  - Computes supervisory control actions & derating requests
  - Exposes commanded vs measured control states
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .can_bus import CANBusInterface, CANFrame, CANHardwareAdapter


class DTCSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class DiagnosticTroubleCode:
    """Formal airborne Diagnostic Trouble Code (DTC) representation."""
    code: str
    severity: DTCSeverity
    source: str
    description: str
    timestamp_ms: float
    remedial_action: str
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "source": self.source,
            "description": self.description,
            "timestamp_ms": self.timestamp_ms,
            "remedial_action": self.remedial_action,
            "acknowledged": self.acknowledged,
        }


@dataclass
class FADECSupervisoryState:
    """Supervisory state produced by Virtual FADEC control loop."""
    timestamp_ms: float
    mode: str  # NOMINAL, ADVISORY_WATCH, DERATE_THROTTLE_MAX_80, DERATE_THROTTLE_MAX_50, ENRICH_COOLING, EMERGENCY_RTL
    commanded_throttle: float
    measured_throttle: float
    throttle_cap: float
    active_dtcs: List[DiagnosticTroubleCode]
    exceedances_detected: List[str]
    fadec_status_word: str
    remediation_guidance: str


class VirtualFADEC:
    """
    Virtual FADEC supervisory controller.
    Monitors engine limits, evaluates CAN integrity, raises DTCs, and executes derating logic.
    """

    def __init__(
        self,
        fadec_id: str = "FADEC-MALE-01",
        can_bus: Optional[CANBusInterface] = None,
    ):
        self.fadec_id = fadec_id
        self.can_bus = can_bus or CANBusInterface()
        self.active_dtcs: Dict[str, DiagnosticTroubleCode] = {}
        self.last_supervisory_state: Optional[FADECSupervisoryState] = None
        self.exceedance_history: List[str] = []
        self.last_rx_sequence: int = -1
        self.last_rx_timestamp_ms: float = 0.0

        # Certified Aero-Piston Operating Thresholds (Rotax 914 Reference)
        self.LIMIT_MAX_RPM = 5800.0
        self.LIMIT_CONTINUOUS_RPM = 5500.0
        self.LIMIT_MAX_CHT_F = 245.0
        self.LIMIT_MAX_OIL_TEMP_F = 235.0
        self.LIMIT_MIN_OIL_PRESS_PSI = 45.0
        self.LIMIT_MAX_EGT_SPREAD_F = 75.0
        self.LIMIT_MIN_BUS_V = 22.0

    def get_commanded_throttle(self, pilot_throttle: float = 0.60) -> float:
        """Returns the effective commanded throttle subject to active FADEC derate limits."""
        if self.last_supervisory_state is not None:
            return min(float(pilot_throttle), float(self.last_supervisory_state.throttle_cap))
        return float(pilot_throttle)

    def ingest_can_frames(self, frames: List[CANFrame]) -> Dict[str, Any]:
        """Decodes incoming CAN frame burst into a unified telemetry state dictionary."""
        telemetry: Dict[str, Any] = {}
        for f in frames:
            decoded = self.can_bus.decode_frame(f)
            if "_error" in decoded:
                self.raise_dtc(
                    code=str(decoded["_error"]),
                    severity=DTCSeverity.WARNING,
                    source="CAN_TRANSCEIVER",
                    description=f"CAN frame error on arbitration ID {decoded.get('arbitration_id')}",
                    remedial_action="VERIFY_CAN_BUS_TERMINATION",
                    timestamp_ms=f.timestamp_ms,
                )
            telemetry.update(decoded)
        return telemetry

    def raise_dtc(
        self,
        code: str,
        severity: DTCSeverity,
        source: str,
        description: str,
        remedial_action: str,
        timestamp_ms: float,
    ) -> DiagnosticTroubleCode:
        """Raises or updates an active Diagnostic Trouble Code."""
        dtc = DiagnosticTroubleCode(
            code=code,
            severity=severity,
            source=source,
            description=description,
            timestamp_ms=timestamp_ms,
            remedial_action=remedial_action,
        )
        self.active_dtcs[code] = dtc
        return dtc

    def clear_dtc(self, code: str) -> None:
        self.active_dtcs.pop(code, None)

    def evaluate_supervisory_logic(
        self,
        telemetry: Dict[str, Any],
        pilot_commanded_throttle: float = 0.60,
        timestamp_ms: Optional[float] = None,
    ) -> FADECSupervisoryState:
        """
        Executes Virtual FADEC supervisory control laws:
          - Limit exceedance detection
          - DTC generation & lifecycle management
          - Autonomic derating request calculation
        """
        now_ms = timestamp_ms if timestamp_ms is not None else (time.time() * 1000.0)
        exceedances: List[str] = []

        rpm = float(telemetry.get("Engine_RPM", 0.0))
        cht = float(telemetry.get("CHT", 0.0))
        oil_temp = float(telemetry.get("Oil_Temp", 0.0))
        oil_press = float(telemetry.get("Oil_Pressure", 50.0))
        vib = float(telemetry.get("Vibration", 0.0))
        egt1 = float(telemetry.get("EGT1", 0.0))
        egt2 = float(telemetry.get("EGT2", 0.0))
        egt_spread = abs(egt1 - egt2) if (egt1 > 0 and egt2 > 0) else 0.0
        bus_v = float(telemetry.get("Battery_Voltage", 28.0))
        measured_throt = float(telemetry.get("Load", telemetry.get("throttle", pilot_commanded_throttle)))

        # Baseline expected harmonic vibration at this RPM
        expected_vib = 0.85 + 0.75 * math.pow(rpm / 3000.0, 2.0) + 0.45 * max(0.0, measured_throt - 0.5)

        # -------------------------------------------------------------
        # 1. Thermal & Cylinder Head Temperature Limit Check
        # -------------------------------------------------------------
        if cht > self.LIMIT_MAX_CHT_F:
            exceedances.append("CHT_OVERTEMP")
            self.raise_dtc(
                code="ENGINE_OVERTEMP",
                severity=DTCSeverity.CRITICAL,
                source="FADEC_THERMAL_MONITOR",
                description=f"Cylinder head temperature exceeded redline: {cht:.1f} °F > {self.LIMIT_MAX_CHT_F} °F",
                remedial_action="DERATE_THROTTLE_AND_ENRICH_MIXTURE",
                timestamp_ms=now_ms,
            )
        else:
            self.clear_dtc("ENGINE_OVERTEMP")

        # -------------------------------------------------------------
        # 2. Lubrication System Limit Check
        # -------------------------------------------------------------
        if oil_press < self.LIMIT_MIN_OIL_PRESS_PSI and rpm > 1500.0:
            exceedances.append("LOW_OIL_PRESSURE")
            self.raise_dtc(
                code="LOW_OIL_PRESSURE",
                severity=DTCSeverity.EMERGENCY if oil_press < 25.0 else DTCSeverity.CRITICAL,
                source="FADEC_LUBRICATION_MONITOR",
                description=f"Oil pressure below threshold: {oil_press:.1f} psi < {self.LIMIT_MIN_OIL_PRESS_PSI} psi",
                remedial_action="RESTRICT_RPM_PREPARE_IMMEDIATE_DESCENT",
                timestamp_ms=now_ms,
            )
        else:
            self.clear_dtc("LOW_OIL_PRESSURE")

        if oil_temp > self.LIMIT_MAX_OIL_TEMP_F:
            exceedances.append("HIGH_OIL_TEMP")
            self.raise_dtc(
                code="HIGH_OIL_TEMP",
                severity=DTCSeverity.WARNING,
                source="FADEC_LUBRICATION_MONITOR",
                description=f"Oil temperature above threshold: {oil_temp:.1f} °F > {self.LIMIT_MAX_OIL_TEMP_F} °F",
                remedial_action="REDUCE_CONTINUOUS_POWER",
                timestamp_ms=now_ms,
            )
        else:
            self.clear_dtc("HIGH_OIL_TEMP")

        # -------------------------------------------------------------
        # 3. Combustion Symmetry, Injector & Misfire Detection
        # -------------------------------------------------------------
        vib_excess = vib - expected_vib
        if egt_spread > self.LIMIT_MAX_EGT_SPREAD_F and vib_excess > 0.60:
            exceedances.append("COMBUSTION_ASYMMETRY")
            self.raise_dtc(
                code="MISFIRE",
                severity=DTCSeverity.CRITICAL,
                source="FADEC_COMBUSTION_MONITOR",
                description=f"Cylinder EGT asymmetry ({egt_spread:.1f} °F) and cyclic torque vibration (+{vib_excess:.2f} g)",
                remedial_action="AVOID_LEAN_OPERATING_MODES_MONITOR_TORQUE",
                timestamp_ms=now_ms,
            )
            self.clear_dtc("INJECTOR_DEGRADATION")
        elif egt_spread > self.LIMIT_MAX_EGT_SPREAD_F:
            exceedances.append("INJECTOR_ASYMMETRY")
            self.raise_dtc(
                code="INJECTOR_DEGRADATION",
                severity=DTCSeverity.WARNING,
                source="FADEC_FUEL_MONITOR",
                description=f"Fuel injector delivery asymmetry detected: EGT spread {egt_spread:.1f} °F",
                remedial_action="SCHEDULE_INJECTOR_INSPECTION",
                timestamp_ms=now_ms,
            )
            self.clear_dtc("MISFIRE")
        else:
            self.clear_dtc("MISFIRE")
            self.clear_dtc("INJECTOR_DEGRADATION")

        # -------------------------------------------------------------
        # 4. Vibration Exceedance Check (Residual Above RPM-Scaled Baseline)
        # -------------------------------------------------------------
        if vib_excess > 1.20 and "MISFIRE" not in self.active_dtcs:
            exceedances.append("EXCESSIVE_VIBRATION")
            self.raise_dtc(
                code="ABNORMAL_VIBRATION",
                severity=DTCSeverity.WARNING if vib_excess < 2.0 else DTCSeverity.CRITICAL,
                source="FADEC_VIBRATION_MONITOR",
                description=f"Harmonic vibration exceedance above nominal: {vib:.3f} g (+{vib_excess:.2f} g above expected)",
                remedial_action="ADJUST_PROP_RPM_AVOID_RESONANCE",
                timestamp_ms=now_ms,
            )
        else:
            self.clear_dtc("ABNORMAL_VIBRATION")

        # -------------------------------------------------------------
        # 5. Electrical Bus Check
        # -------------------------------------------------------------
        if bus_v < self.LIMIT_MIN_BUS_V:
            exceedances.append("BUS_UNDERVOLTAGE")
            self.raise_dtc(
                code="ELECTRICAL_BUS_FAULT",
                severity=DTCSeverity.WARNING,
                source="FADEC_ELECTRICAL_MONITOR",
                description=f"Avionics DC bus voltage low: {bus_v:.2f} V < {self.LIMIT_MIN_BUS_V} V",
                remedial_action="SHED_NON_ESSENTIAL_ELECTRICAL_LOADS",
                timestamp_ms=now_ms,
            )
        else:
            self.clear_dtc("ELECTRICAL_BUS_FAULT")

        # -------------------------------------------------------------
        # 6. FADEC Supervisory Derating Control Law
        # -------------------------------------------------------------
        mode = "NOMINAL"
        throttle_cap = 1.00
        remediation = "Nominal operating envelope maintained."

        if any(d.severity == DTCSeverity.EMERGENCY for d in self.active_dtcs.values()):
            mode = "EMERGENCY_RTL"
            throttle_cap = 0.40
            remediation = "CRITICAL DEFICIT: Throttle capped to 40%. Execute immediate landing."
        elif any(d.severity == DTCSeverity.CRITICAL for d in self.active_dtcs.values()):
            mode = "DERATE_THROTTLE_MAX_50"
            throttle_cap = 0.50
            remediation = "LIMIT EXCEEDED: Autonomic throttle derate to 50% enforced."
        elif any(d.severity == DTCSeverity.WARNING for d in self.active_dtcs.values()):
            mode = "DERATE_THROTTLE_MAX_80"
            throttle_cap = 0.80
            remediation = "SYSTEM DEGRADATION DETECTED: Throttle capped to 80% maximum continuous power."

        effective_commanded = min(pilot_commanded_throttle, throttle_cap)

        fadec_state = FADECSupervisoryState(
            timestamp_ms=now_ms,
            mode=mode,
            commanded_throttle=round(effective_commanded, 3),
            measured_throttle=round(measured_throt, 3),
            throttle_cap=round(throttle_cap, 2),
            active_dtcs=list(self.active_dtcs.values()),
            exceedances_detected=exceedances,
            fadec_status_word=f"FADEC_{mode}",
            remediation_guidance=remediation,
        )
        self.last_supervisory_state = fadec_state
        return fadec_state
