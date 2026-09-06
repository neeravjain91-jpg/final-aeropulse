import pytest
from app.degradation import estimate_degradation_horizon
from app.rul_service import RULService
from app.engine_model import ReducedOrderPistonEngine
from app.state import EngineRunState

def test_positive_health_slope_is_not_degrading():
    improving_trajectory = [70.0, 75.0, 80.0, 85.0, 90.0, 95.0]
    res = estimate_degradation_horizon(improving_trajectory, step_minutes=5.0)
    assert res['available'] is True
    assert res['status'] == 'RECOVERY_OR_IMPROVING'
    assert res['rul_hours'] is None
    assert res['trend_per_hour'] > 0.15

def test_negative_health_slope_is_degrading():
    degrading_trajectory = [95.0, 90.0, 85.0, 80.0, 75.0, 70.0]
    res = estimate_degradation_horizon(degrading_trajectory, step_minutes=5.0)
    assert res['available'] is True
    assert res['status'] == 'DEGRADING'
    assert res['rul_hours'] is not None
    assert res['rul_hours'] > 0.0
    assert res['trend_per_hour'] < -0.15

def test_near_zero_slope_is_stable():
    stable_trajectory = [90.0, 90.05, 89.95, 90.0, 90.02, 89.98]
    res = estimate_degradation_horizon(stable_trajectory, step_minutes=5.0)
    assert res['available'] is True
    assert res['status'] == 'STABLE_OR_NON_DEGRADING'
    assert res['rul_hours'] is None

def test_critical_health_threshold_produces_zero_rul():
    # 1. Stable at critical threshold
    stable_critical = [30.0, 30.0, 30.0, 30.0, 30.0, 30.0]
    res_stable = estimate_degradation_horizon(stable_critical, step_minutes=5.0)
    assert res_stable['available'] is True
    assert res_stable['status'] == 'CRITICAL'
    assert res_stable['rul_hours'] == 0.0

    # 2. Actively declining below critical threshold
    declining_critical = [38.0, 36.0, 34.0, 32.0, 30.0, 28.0]
    res_declining = estimate_degradation_horizon(declining_critical, step_minutes=5.0)
    assert res_declining['available'] is True
    assert res_declining['status'] == 'DEGRADING'
    assert res_declining['rul_hours'] == 0.0

    # 3. RULService critical prediction
    service = RULService()
    pred_crit = service.estimate_rul(health_index=30.0)
    assert pred_crit['status'] == 'CRITICAL_MAINTENANCE_REQUIRED'
    assert pred_crit['rul_hours'] == 0.0

def test_rul_monotonicity_under_degradation():
    service = RULService()
    healthy = service.predict({'Degradation_Severity': 0.1})
    moderate = service.predict({'Degradation_Severity': 0.4})
    severe = service.predict({'Degradation_Severity': 0.8})
    assert healthy['rul_hours'] > moderate['rul_hours'] > severe['rul_hours']

def test_method_labeling_is_accurate():
    service = RULService()
    res = service.estimate_rul(health_index=85.0)
    assert res['method'] == 'Physics-Stress Weighted Trend Extrapolation'
    assert 'Weibull' not in res['method']

def test_mission_stress_single_count():
    service = RULService()
    low_stress_ctx = {'altitude_ft': 3000.0, 'ambient_c': 20.0, 'duration_h': 2.0}
    high_stress_ctx = {'altitude_ft': 15000.0, 'ambient_c': 45.0, 'duration_h': 10.0}
    s_low = service.calculate_mission_stress(low_stress_ctx)
    s_high = service.calculate_mission_stress(high_stress_ctx)
    assert s_high > s_low

    # Explicit slope test with positive vs negative slopes
    pos_res = service.predict({'Degradation_Severity': 0.2}, context={'degradation_slope': 0.05})
    assert pos_res['status'] == 'STABLE_OR_NON_DEGRADING'
    assert pos_res['rul_hours'] == 2000.0

    neg_res = service.predict({'Degradation_Severity': 0.2}, context={'degradation_slope': -0.05})
    assert neg_res['status'] == 'SLOPE_EXTRAPOLATED'
    assert neg_res['rul_hours'] < 2000.0

def test_phase2_piston_and_engine_state_preserved():
    engine = ReducedOrderPistonEngine()
    assert engine.IDLE_RPM == 1400.0
    assert EngineRunState.ENGINE_OFF == 'ENGINE_OFF'
