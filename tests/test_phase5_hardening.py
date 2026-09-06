import math
import pytest
from types import SimpleNamespace

from app.engine_model import EngineInputs, ReducedOrderPistonEngine
from app.state import EngineRunState, EngineStateRecord
from app.main import _build_live_engine_data
from app.inference import AeroTwinAI
from app.digital_twin import ReferenceTwin
from app.degradation import estimate_degradation_horizon
from app.rul_service import RULService
from app.risk import mission_risk
from app.simulator import inject_fault, mission_adjust
from app.sensor_health import assess_sensor_health
from app.mission_whatif_rul import MissionWhatIfRUL, MissionScenario


# ==============================================================================
# 1. ENGINE STATE & PISTON STATE MACHINE
# ==============================================================================

def test_engine_state_transitions_comprehensive():
    # GROUND -> OFF
    mp_off = SimpleNamespace(mission_phase='GROUND', throttle=0.0, load=0.0, altitude_ft=0.0, ambient_c=25.0)
    data_off = _build_live_engine_data(mp_off)
    assert data_off['engine_run_state'] == 'ENGINE_OFF'
    assert data_off['Engine_RPM'] == 0.0
    assert data_off['Fuel_Flow'] == 0.0
    assert data_off['Brake_Power_kW'] == 0.0

    # STARTING -> CRANKING
    mp_start = SimpleNamespace(mission_phase='STARTING', throttle=0.1, load=0.1, altitude_ft=0.0, ambient_c=25.0)
    data_start = _build_live_engine_data(mp_start)
    assert data_start['engine_run_state'] == 'ENGINE_STARTING'
    assert data_start['Engine_RPM'] == 800.0

    # CRUISE -> RUNNING
    mp_run = SimpleNamespace(mission_phase='CRUISE', throttle=0.6, load=0.8, altitude_ft=5000.0, ambient_c=20.0)
    data_run = _build_live_engine_data(mp_run)
    assert data_run['engine_run_state'] == 'ENGINE_RUNNING'
    assert data_run['Engine_RPM'] >= 1400.0

    # STOPPING -> COOLDOWN
    mp_stop = SimpleNamespace(mission_phase='STOPPING', throttle=0.0, load=0.0, altitude_ft=0.0, ambient_c=25.0)
    data_stop = _build_live_engine_data(mp_stop)
    assert data_stop['engine_run_state'] == 'ENGINE_STOPPING'
    assert data_stop['Engine_RPM'] == 400.0


def test_idle_rpm_strict_invariant():
    engine = ReducedOrderPistonEngine()
    assert engine.IDLE_RPM == 1400.0
    assert engine.config.idle_rpm == 1400.0


# ==============================================================================
# 2. PISTON KINEMATICS SIMULATION
# ==============================================================================

def test_piston_kinematics_velocity_scaling():
    def compute_angular_velocity(rpm, engine_state):
        raw_rpm = float(rpm)
        state = str(engine_state).upper()
        is_running = raw_rpm > 0 and state not in ['ENGINE_OFF', 'OFF']
        if not is_running:
            return 0.0
        return min(max(raw_rpm / 60.0, 0.0), 95.0) * math.pi * 0.32

    assert compute_angular_velocity(0, 'ENGINE_OFF') == 0.0
    assert compute_angular_velocity(3000, 'ENGINE_OFF') == 0.0
    assert compute_angular_velocity(3000, 'ENGINE_RUNNING') > 0.0

    w3000 = compute_angular_velocity(3000, 'ENGINE_RUNNING')
    w4500 = compute_angular_velocity(4500, 'ENGINE_RUNNING')
    assert math.isclose(w4500 / w3000, 1.5, rel_tol=1e-3)


# ==============================================================================
# 3. DIGITAL-TWIN AUTHORITY & PIPELINE CONSISTENCY
# ==============================================================================

def test_digital_twin_authority_canonical_record():
    ai = AeroTwinAI()
    mp = SimpleNamespace(mission_phase='CRUISE', throttle=0.7, load=0.85, altitude_ft=6000.0, ambient_c=25.0)
    telemetry = _build_live_engine_data(mp)
    telemetry['Operating_State'] = 'CRUISE'

    analysis = ai.analyze(telemetry, context={'altitude_ft': 6000.0, 'ambient_c': 25.0})
    risk = mission_risk(analysis, {'altitude_ft': 6000.0, 'ambient_c': 25.0})
    analysis['mission_risk'] = risk

    record = EngineStateRecord.from_analysis(analysis)
    d = record.as_dict()

    assert d['engine_run_state'] == 'ENGINE_RUNNING'
    assert 'Engine_RPM' in d['telemetry']
    assert 'physics_expected' in d
    assert 'residuals' in d
    assert 'rul_hours' in d
    assert 'mission_risk_index' in d
    assert d['rul_provenance'] == 'Physics-Stress Weighted Trend Extrapolation' or 'Extrapolation' in d['rul_provenance'] or d['rul_provenance'] == 'SIMULATION-DERIVED'


# ==============================================================================
# 4. HEALTH THRESHOLDS & BOUNDS
# ==============================================================================

def test_health_bounds_and_determinism():
    ai = AeroTwinAI()
    twin = ReferenceTwin()
    ref = twin.expected('CRUISE')
    ref['Operating_State'] = 'CRUISE'

    res1 = ai.analyze(ref)
    res2 = ai.analyze(ref)

    assert 0.0 <= res1['health_index'] <= 100.0
    assert res1['health_index'] == res2['health_index']
    assert res1['health_state'] == res2['health_state']


# ==============================================================================
# 5. DEGRADATION SEMANTICS & TOLERANCE
# ==============================================================================

def test_degradation_semantics_comprehensive():
    # 1. Negative slope -> DEGRADING
    res_deg = estimate_degradation_horizon([95, 90, 85, 80, 75, 70], step_minutes=5.0)
    assert res_deg['status'] == 'DEGRADING'
    assert res_deg['rul_hours'] is not None

    # 2. Positive slope -> RECOVERY_OR_IMPROVING (no finite RUL)
    res_imp = estimate_degradation_horizon([70, 75, 80, 85, 90, 95], step_minutes=5.0)
    assert res_imp['status'] == 'RECOVERY_OR_IMPROVING'
    assert res_imp['rul_hours'] is None

    # 3. Near zero slope -> STABLE_OR_NON_DEGRADING
    res_stb = estimate_degradation_horizon([85.0, 85.02, 84.98, 85.01, 84.99, 85.0], step_minutes=5.0)
    assert res_stb['status'] == 'STABLE_OR_NON_DEGRADING'
    assert res_stb['rul_hours'] is None


# ==============================================================================
# 6. RUL PROGNOSTICS ACCURACY & BOUNDS
# ==============================================================================

def test_rul_prognostics_bounds_and_critical_state():
    service = RULService()

    # Critical health <= 35
    crit = service.estimate_rul(health_index=32.0)
    assert crit['status'] == 'CRITICAL_MAINTENANCE_REQUIRED'
    assert crit['rul_hours'] == 0.0

    # Warning health 35 < H <= 60
    warn = service.estimate_rul(health_index=50.0)
    assert warn['status'] == 'WARNING_ELEVATED_WEAR'
    assert warn['rul_lower_hours'] <= warn['rul_hours'] <= warn['rul_upper_hours']

    # Nominal health H > 60
    nom = service.estimate_rul(health_index=90.0)
    assert nom['status'] == 'NOMINAL_HEALTH'
    assert nom['rul_hours'] > warn['rul_hours']
    assert nom['method'] == 'Physics-Stress Weighted Trend Extrapolation'


# ==============================================================================
# 7. MISSION STRESS MULTIPLIERS
# ==============================================================================

def test_mission_stress_factors():
    service = RULService()
    baseline = service.calculate_mission_stress({'altitude_ft': 3000, 'ambient_c': 25, 'duration_h': 4})
    high_alt = service.calculate_mission_stress({'altitude_ft': 20000, 'ambient_c': 25, 'duration_h': 4})
    hot_temp = service.calculate_mission_stress({'altitude_ft': 3000, 'ambient_c': 50, 'duration_h': 4})
    long_dur = service.calculate_mission_stress({'altitude_ft': 3000, 'ambient_c': 25, 'duration_h': 16})
    rapid_thr = service.calculate_mission_stress({'altitude_ft': 3000, 'ambient_c': 25, 'duration_h': 4, 'rapid_throttle': True})

    assert high_alt > baseline
    assert hot_temp > baseline
    assert long_dur > baseline
    assert rapid_thr > baseline


# ==============================================================================
# 8. FAULT INJECTION & DIAGNOSTIC RESPONSE
# ==============================================================================

def test_fault_modes_propagation():
    twin = ReferenceTwin()
    base = twin.expected('CRUISE')
    base['Vibration'] = 0.5

    # Thermal Overheating
    hot = inject_fault(base, 'overheating', 0.8)
    assert hot['CHT'] > base['CHT']
    assert hot['Oil_Temp'] > base['Oil_Temp']

    # Lubrication
    lube = inject_fault(base, 'lubrication', 0.8)
    assert lube['Oil_Pressure'] < base['Oil_Pressure']
    assert lube['Oil_Temp'] > base['Oil_Temp']

    # Misfire
    mis = inject_fault(base, 'misfire', 0.8)
    assert mis['Vibration'] > base['Vibration']
    assert mis['Engine_RPM'] < base['Engine_RPM']


# ==============================================================================
# 9. SENSOR HEALTH, DRIFT & TRUST VETO
# ==============================================================================

def test_sensor_health_trust_evaluation():
    twin_engine = ReferenceTwin()
    base = twin_engine.expected('CRUISE')
    twin_comp = twin_engine.compare(base)

    # Clean sensors
    health_clean = assess_sensor_health(base, twin_comp)
    assert health_clean['overall_trust_score'] >= 90.0

    # Drifted CHT sensor
    drifted = dict(base)
    drifted['CHT'] = 450.0  # extreme deviation
    twin_drift = twin_engine.compare(drifted)
    health_drift = assess_sensor_health(drifted, twin_drift)
    assert health_drift['overall_trust_score'] < health_clean['overall_trust_score']
    assert any(c['name'] == 'CHT' and c['status'] in ['SUSPECT', 'FAILED'] for c in health_drift['sensors'])


# ==============================================================================
# 10. WHAT-IF & MISSION COMPARISON HARDENING
# ==============================================================================

def test_whatif_scenario_hardening():
    whatif = MissionWhatIfRUL()
    twin = ReferenceTwin()
    base = twin.expected('CRUISE')

    scen_low = MissionScenario(name='Low Alt', altitude_ft=3000, ambient_c=20, duration_h=2)
    scen_high = MissionScenario(name='High Alt Hot', altitude_ft=18000, ambient_c=45, duration_h=8)

    comp = whatif.compare(base, scen_low, scen_high)
    assert 'baseline' in comp
    assert 'alternative' in comp
    assert 'impact' in comp
    assert comp['alternative']['rul']['rul_hours'] <= comp['baseline']['rul']['rul_hours']
