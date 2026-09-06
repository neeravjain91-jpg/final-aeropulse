# Tests for Physics Engine V2 thermodynamic equations, parameterization, and ISA atmosphere.
import pytest
from app.engine_config import EngineConfig
from app.engine_model import EngineInputs, ReducedOrderPistonEngine


def test_engine_config_defaults_and_customization():
    cfg = EngineConfig.default_135l()
    assert cfg.displacement_l == 1.352
    assert cfg.num_cylinders == 4
    assert cfg.compression_ratio == 9.0

    custom = EngineConfig.custom(displacement_l=2.0, base_power_kw=120.0)
    assert custom.displacement_l == 2.0
    assert custom.base_power_kw == 120.0
    engine = ReducedOrderPistonEngine(custom)
    assert engine.DISPLACEMENT_L == 2.0


def test_isa_barometric_altitude_lapse():
    engine = ReducedOrderPistonEngine()
    t_sl, p_sl, sigma_sl = engine._isa_atmosphere(0.0, 15.0)
    t_10k, p_10k, sigma_10k = engine._isa_atmosphere(10000.0, 15.0)
    t_25k, p_25k, sigma_25k = engine._isa_atmosphere(25000.0, 15.0)

    # Pressure and density ratio must decrease monotonically with altitude
    assert p_sl > p_10k > p_25k
    assert sigma_sl > sigma_10k > sigma_25k
    assert t_sl > t_10k > t_25k


def test_mass_air_and_fuel_flow_scaling():
    engine = ReducedOrderPistonEngine()
    state_idle = engine.estimate_state(EngineInputs(rpm=1500.0, throttle=0.20))
    state_cruise = engine.estimate_state(EngineInputs(rpm=3000.0, throttle=0.60))
    state_takeoff = engine.estimate_state(EngineInputs(rpm=5200.0, throttle=1.00))

    assert state_takeoff.air_mass_flow_kg_s > state_cruise.air_mass_flow_kg_s > state_idle.air_mass_flow_kg_s
    assert state_takeoff.fuel_mass_flow_g_s > state_cruise.fuel_mass_flow_g_s > state_idle.fuel_mass_flow_g_s
    assert state_takeoff.indicated_power_kw > state_cruise.indicated_power_kw > state_idle.indicated_power_kw


def test_friction_and_brake_power_dynamics():
    engine = ReducedOrderPistonEngine()
    state_nom = engine.estimate_state(EngineInputs(rpm=3000.0, throttle=0.60, friction_multiplier=1.0))
    state_high_fric = engine.estimate_state(EngineInputs(rpm=3000.0, throttle=0.60, friction_multiplier=1.8))

    assert state_nom.brake_power_kw > state_high_fric.brake_power_kw
