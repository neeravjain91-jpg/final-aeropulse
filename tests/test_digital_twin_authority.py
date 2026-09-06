import pytest
from types import SimpleNamespace
from app.inference import AeroTwinAI
from app.state import EngineRunState, EngineStateRecord
from app.main import _build_live_engine_data
from app.risk import mission_risk

def test_authoritative_pipeline_end_to_end():
    ai = AeroTwinAI()
    mp = SimpleNamespace(mission_phase='CRUISE', throttle=0.6, load=0.85, altitude_ft=8000.0, ambient_c=35.0, step=10, time_min=20.0, operating_state='CRUISE', rapid_throttle=False)
    telemetry = _build_live_engine_data(mp)
    assert telemetry['engine_run_state'] == 'ENGINE_RUNNING'
    telemetry['Operating_State'] = 'CRUISE'
    analysis = ai.analyze(telemetry, context={'altitude_ft': 8000.0, 'ambient_c': 35.0})
    risk = mission_risk(analysis, {'altitude_ft': 8000.0, 'ambient_c': 35.0})
    analysis['mission_risk'] = risk
    record = EngineStateRecord.from_analysis(analysis)
    d = record.as_dict()
    assert d['engine_run_state'] == 'ENGINE_RUNNING'
    assert d['ml_health_state'] in ['Normal', 'Watch', 'Warning', 'Critical']
    assert 'residuals' in d
    assert 'physics_expected' in d
    assert 'rul_hours' in d
    assert 'mission_risk_index' in d

def test_engine_off_authority_propagation():
    ai = AeroTwinAI()
    mp = SimpleNamespace(mission_phase='GROUND', throttle=0.0, load=0.0, altitude_ft=0.0, ambient_c=25.0, step=0, time_min=0.0, operating_state='CRUISE', rapid_throttle=False)
    telemetry = _build_live_engine_data(mp)
    assert telemetry['engine_run_state'] == 'ENGINE_OFF'
    assert telemetry['Engine_RPM'] == 0.0
    telemetry['Operating_State'] = 'CRUISE'
    analysis = ai.analyze(telemetry)
    record = EngineStateRecord.from_analysis(analysis)
    assert record.engine_run_state == 'ENGINE_OFF'
    assert record.telemetry['Engine_RPM'] == 0.0
