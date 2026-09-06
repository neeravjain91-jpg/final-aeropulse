import pytest
from types import SimpleNamespace
from app.state import EngineRunState, EngineStateRecord
from app.engine_model import EngineInputs, ReducedOrderPistonEngine
from app.main import _build_live_engine_data

def test_engine_run_state_enum_and_record():
    assert EngineRunState.ENGINE_OFF == "ENGINE_OFF"
    assert EngineRunState.ENGINE_STARTING == "ENGINE_STARTING"
    assert EngineRunState.ENGINE_RUNNING == "ENGINE_RUNNING"
    assert EngineRunState.ENGINE_STOPPING == "ENGINE_STOPPING"
    rec = EngineStateRecord(engine_run_state=EngineRunState.ENGINE_OFF)
    d = rec.as_dict()
    assert d["engine_run_state"] == "ENGINE_OFF"

def test_idle_rpm_remains_strictly_1400():
    engine = ReducedOrderPistonEngine()
    assert engine.IDLE_RPM == 1400.0
    assert engine.config.idle_rpm == 1400.0
    inputs = EngineInputs(rpm=0.0, throttle=0.5, altitude_ft=3000.0, ambient_c=25.0)
    state = engine.estimate_state(inputs)
    assert state.brake_power_kw > 0.0
    assert state.volumetric_efficiency > 0.0

def test_engine_off_produces_zero_rpm_and_stationary_state():
    mp = SimpleNamespace(mission_phase="GROUND", throttle=0.0, load=0.0, altitude_ft=0.0, ambient_c=25.0)
    data = _build_live_engine_data(mp)
    assert data["engine_run_state"] == "ENGINE_OFF"
    assert data["Engine_RPM"] == 0.0
    assert data["Fuel_Flow"] == 0.0
    assert data["Brake_Power_kW"] == 0.0
    assert data["Vibration"] == 0.0

def test_engine_starting_produces_cranking_state():
    mp = SimpleNamespace(mission_phase="STARTING", throttle=0.1, load=0.1, altitude_ft=0.0, ambient_c=25.0)
    data = _build_live_engine_data(mp)
    assert data["engine_run_state"] == "ENGINE_STARTING"
    assert data["Engine_RPM"] == 800.0

def test_engine_running_produces_physics_coupled_rpm():
    mp_low = SimpleNamespace(mission_phase="CRUISE", throttle=0.3, load=0.5, altitude_ft=5000.0, ambient_c=20.0)
    d_low = _build_live_engine_data(mp_low)
    assert d_low["engine_run_state"] == "ENGINE_RUNNING"
    assert d_low["Engine_RPM"] > 1400.0
    mp_high = SimpleNamespace(mission_phase="CLIMB", throttle=0.9, load=0.95, altitude_ft=5000.0, ambient_c=20.0)
    d_high = _build_live_engine_data(mp_high)
    assert d_high["engine_run_state"] == "ENGINE_RUNNING"
    assert d_high["Engine_RPM"] > d_low["Engine_RPM"]
    assert d_high["Fuel_Flow"] > d_low["Fuel_Flow"]

def test_engine_stopping_produces_cooldown_state():
    mp = SimpleNamespace(mission_phase="STOPPING", throttle=0.0, load=0.0, altitude_ft=0.0, ambient_c=25.0)
    data = _build_live_engine_data(mp)
    assert data["engine_run_state"] == "ENGINE_STOPPING"
    assert data["Engine_RPM"] == 400.0
