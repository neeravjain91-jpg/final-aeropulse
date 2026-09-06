import pytest
from app.nlp_maintenance import NLPMaintenanceExtractor, MaintenanceEvent


def test_nlp_extraction_thermal_symptom():
    nlp = NLPMaintenanceExtractor()
    note = "High CHT and elevated coolant temperature observed during desert loiter."
    event = nlp.parse_maintenance_note(note, mission_id="aces_flight_01")
    
    assert event.component == "Thermal / Cooling System"
    assert event.symptom == "High Temperature Spike"
    assert event.severity in ["WARNING", "CHECK", "CRITICAL"]
    assert "radiator" in event.recommended_action.lower()


def test_nlp_extraction_lubrication_symptom():
    nlp = NLPMaintenanceExtractor()
    note = "Warning: Sudden oil pressure drop and high bearing temperature reported."
    event = nlp.parse_maintenance_note(note)
    
    assert event.component == "Lubrication System"
    assert event.symptom == "Pressure Loss"
    assert event.severity == "WARNING"
    assert "oil" in event.recommended_action.lower()


def test_nlp_digital_twin_correlation():
    nlp = NLPMaintenanceExtractor()
    note = "Cylinder misfire reported on cylinder 1."
    event = nlp.parse_maintenance_note(note)
    
    corr = nlp.correlate_with_digital_twin(event, {"EGT1": -3.5, "CHT": 0.2})
    assert corr["is_corroborated_by_live_twin"] is True
    assert len(corr["corroboration_evidence"]) > 0
    assert "SUPPORTING_EVIDENCE_ONLY" in corr["advisory_role"]
