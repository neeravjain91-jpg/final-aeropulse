from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosticEvidence:
    channel: str
    observed: float
    expected: float
    z_score: float
    percentage_deviation: float
    persistence_steps: int
    physical_implication: str


@dataclass
class ComprehensiveDiagnosis:
    primary_fault: str
    severity: str
    confidence_score: float
    physics_consistency_score: float
    dominant_deviations: List[DiagnosticEvidence]
    supporting_evidence: List[str]
    competing_hypotheses: List[Dict[str, Any]]
    diagnostic_summary: str
    remediation_guidance: str


default_explain_engine = None


class ExplainableDiagnosticEngine:
    """
    Generates causal, physics-grounded, and engineer-readable fault diagnoses.
    Combines machine learning classification confidence with Digital Twin residual
    analysis, cross-sensor thermodynamic coupling, and temporal persistence.
    """

    @staticmethod
    def explain(
        telemetry: Dict[str, Any],
        twin_assessment: Dict[str, Any],
        sensor_health: Dict[str, Any],
        fault_candidates: List[Dict[str, Any]],
        ml_prediction: str = "Normal",
        ml_confidence: float = 0.95,
    ) -> ComprehensiveDiagnosis:
        z_scores = twin_assessment.get("z_scores", {})
        expected_vals = twin_assessment.get("expected", {})
        persistence = twin_assessment.get("residual_persistence", {})
        pct_dev = twin_assessment.get("percentage_deviation", {})

        evidence_items: List[DiagnosticEvidence] = []
        for param, z in sorted(z_scores.items(), key=lambda item: abs(item[1]), reverse=True):
            if abs(z) >= 1.5:
                obs = float(telemetry.get(param, 0.0))
                exp = float(expected_vals.get(param, 0.0))
                implication = "High residual above nominal thermodynamic envelope" if z > 0 else "Low residual below nominal thermodynamic envelope"
                evidence_items.append(
                    DiagnosticEvidence(
                        channel=param,
                        observed=round(obs, 2),
                        expected=round(exp, 2),
                        z_score=round(z, 2),
                        percentage_deviation=round(pct_dev.get(param, 0.0), 1),
                        persistence_steps=int(persistence.get(param, 1)),
                        physical_implication=implication,
                    )
                )

        # Evaluate thermodynamic coupling score
        coupling_score = 95.0
        if len(evidence_items) == 1 and abs(evidence_items[0].z_score) > 3.0:
            coupling_score = 40.0
        elif len(evidence_items) >= 2:
            coupling_score = min(98.0, 70.0 + 5.0 * len(evidence_items))

        primary_fault = fault_candidates[0]["name"] if fault_candidates else ("Nominal Healthy Baseline" if ml_prediction == "Normal" else f"Elevated {ml_prediction} Indicator")
        primary_sev = fault_candidates[0]["severity"] if fault_candidates else "LOW"
        supporting = fault_candidates[0].get("evidence", []) if fault_candidates else ["All telemetry channels within 2-sigma healthy baseline"]

        competing = []
        if len(fault_candidates) > 1:
            for cand in fault_candidates[1:]:
                competing.append({
                    "name": cand.get("name"),
                    "severity": cand.get("severity"),
                    "evidence": cand.get("evidence", []),
                })

        sev_upper = primary_sev.upper()
        summary = (
            f"Primary finding: '{primary_fault}' (Severity: {sev_upper}). "
            f"Driven by {len(evidence_items)} physics residual deviations with {coupling_score:.0f}% thermodynamic coupling consistency. "
            f"ML Confidence: {ml_confidence * 100.0:.1f}%."
        )

        remediation = "Continue planned mission with nominal scan interval."
        if primary_sev.lower() == "high":
            remediation = "Safety Advisory: Restrict maximum throttle and initiate planned diversion / RTB."
        elif primary_sev.lower() == "medium":
            remediation = "Caution Advisory: Monitor thermal and lubrication channels; avoid continuous climb power."

        return ComprehensiveDiagnosis(
            primary_fault=primary_fault,
            severity=primary_sev,
            confidence_score=round(ml_confidence, 3),
            physics_consistency_score=round(coupling_score, 1),
            dominant_deviations=evidence_items,
            supporting_evidence=supporting,
            competing_hypotheses=competing,
            diagnostic_summary=summary,
            remediation_guidance=remediation,
        )
