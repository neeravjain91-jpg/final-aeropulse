"""NLP Maintenance Intelligence & Structured Advisory Engine."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MaintenanceEvent:
    """Standardized Aerospace Maintenance Event Record."""
    component: str
    symptom: str
    fault_type: str
    severity: str
    operating_condition: str
    recommended_action: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    mission_id: Optional[str] = None
    confidence: float = 0.90
    evidence_source: str = "HISTORICAL_MAINTENANCE_LOG"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NLPMaintenanceExtractor:
    """Rule-based and semantic entity extractor for unstructured aviation maintenance records."""

    COMPONENT_PATTERNS = {
        "Thermal / Cooling System": [r"\bcht\b", r"cylinder head", r"coolant", r"radiator", r"water temp", r"overheat"],
        "Combustion System": [r"\begt\b", r"exhaust gas", r"spark plug", r"cylinder misfire", r"misfire", r"ignition"],
        "Lubrication System": [r"oil temp", r"oil pressure", r"lubrication", r"oil filter", r"bearing", r"metal shavings"],
        "Fuel Injection System": [r"fuel flow", r"injector", r"lean burn", r"manifold pressure", r"map sensor", r"fuel pump"],
        "Electrical System": [r"battery voltage", r"alternator", r"bus voltage", r"current draw", r"charging system"],
        "Mechanical / Structural": [r"vibration", r"propeller governor", r"gearbox", r"mount crack", r"imbalance"],
    }

    SYMPTOM_PATTERNS = {
        "High Temperature Spike": [r"high (?:cht|egt|temp)", r"exceeded \d+", r"spiked to", r"thermal runaway", r"elevated temp"],
        "Pressure Loss": [r"low (?:oil )?pressure", r"pressure drop", r"unstable pressure", r"loss of pressure"],
        "Combustion Misfire": [r"cylinder \d+ misfire", r"rough running", r"rpm drop", r"hesitation"],
        "Excessive Vibration": [r"high vibration", r"airframe buffeting", r"severe tremor", r"g-spike"],
        "Flow Metering Deficit": [r"fuel starvation", r"restricted flow", r"injector clog", r"lean spike"],
    }

    RECOMMENDED_ACTIONS = {
        "Thermal / Cooling System": "Inspect radiator airflow ducts, coolant level, and CHT thermocouple bonding.",
        "Combustion System": "Perform borescope inspection on cylinder 1-4 exhaust valves and test spark igniters.",
        "Lubrication System": "Conduct oil filter teardown for particulate analysis and test oil pressure relief valve.",
        "Fuel Injection System": "Flow-test injector nozzles and inspect fuel distributor rail pressure regulator.",
        "Electrical System": "Check alternator belt tension, inspect battery cell terminal impedance.",
        "Mechanical / Structural": "Perform dynamic propeller balancing and inspect engine mount isolators.",
    }

    def parse_maintenance_note(self, text: str, mission_id: Optional[str] = None) -> MaintenanceEvent:
        """Parses a free-form maintenance technician note into a structured maintenance record."""
        text_lower = text.lower()

        matched_comp = "General Propulsion System"
        for comp, patterns in self.COMPONENT_PATTERNS.items():
            if any(re.search(pat, text_lower) for pat in patterns):
                matched_comp = comp
                break

        matched_symptom = "Telemetry Parameter Deviation"
        for symp, patterns in self.SYMPTOM_PATTERNS.items():
            if any(re.search(pat, text_lower) for pat in patterns):
                matched_symptom = symp
                break

        severity = "INFO"
        if any(w in text_lower for w in ["critical", "severe", "aborted", "emergency", "fail"]):
            severity = "CRITICAL"
        elif any(w in text_lower for w in ["warning", "elevated", "high", "abnormal", "dropped"]):
            severity = "WARNING"
        elif any(w in text_lower for w in ["check", "minor", "slight", "inspection"]):
            severity = "CHECK"

        cond = "Nominal Cruise"
        if "high altitude" in text_lower or "climb" in text_lower:
            cond = "High-Altitude Climb"
        elif "hot day" in text_lower or "desert" in text_lower or "high ambient" in text_lower:
            cond = "High Ambient Temperature"
        elif "descent" in text_lower or "idle" in text_lower:
            cond = "Loiter Descent"

        action = self.RECOMMENDED_ACTIONS.get(matched_comp, "Perform standard line inspection.")

        return MaintenanceEvent(
            component=matched_comp,
            symptom=matched_symptom,
            fault_type=matched_symptom.replace(" ", "_").upper(),
            severity=severity,
            operating_condition=cond,
            recommended_action=action,
            mission_id=mission_id,
            confidence=0.92,
        )

    def correlate_with_digital_twin(
        self,
        event: MaintenanceEvent,
        twin_residuals: Dict[str, float],
    ) -> Dict[str, Any]:
        """Correlates structured historical maintenance records with current Digital Twin residuals."""
        matching_evidence = []
        is_corroborated = False

        if "Thermal" in event.component and (abs(twin_residuals.get("CHT", 0.0)) > 1.5 or abs(twin_residuals.get("EGT1", 0.0)) > 1.5):
            matching_evidence.append(f"Current live CHT/EGT residual matches historical symptom ({event.symptom})")
            is_corroborated = True
        elif "Lubrication" in event.component and abs(twin_residuals.get("Oil_Pressure", 0.0)) > 1.5:
            matching_evidence.append(f"Current live Oil Pressure residual matches historical symptom ({event.symptom})")
            is_corroborated = True
        elif "Combustion" in event.component and abs(twin_residuals.get("EGT1", 0.0)) > 2.0:
            matching_evidence.append(f"Current live EGT asymmetry corroborates historical combustion fault ({event.symptom})")
            is_corroborated = True

        return {
            "historical_event": event.to_dict(),
            "is_corroborated_by_live_twin": is_corroborated,
            "corroboration_evidence": matching_evidence if matching_evidence else ["No active live correlation; historical reference only"],
            "advisory_role": "SUPPORTING_EVIDENCE_ONLY (Does not prove current fault)",
        }
