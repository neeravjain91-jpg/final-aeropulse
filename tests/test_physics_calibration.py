import pytest
import numpy as np
from app.engine_model import EngineInputs, ReducedOrderPistonEngine


def test_calibrated_physics_output_ranges():
    engine = ReducedOrderPistonEngine()
    pred = engine.predict(EngineInputs(rpm=4544.0, throttle=0.60, altitude_ft=3000.0, ambient_c=25.0))
    
    assert 195.0 <= pred["CHT"] <= 230.0
    assert 1200.0 <= pred["EGT1"] <= 1350.0
    assert 1200.0 <= pred["EGT2"] <= 1350.0
    assert 1200.0 <= pred["EGT3"] <= 1350.0
    assert 50.0 <= pred["Oil_Pressure"] <= 70.0
    assert 170.0 <= pred["EFI_Water_Temp"] <= 195.0
    assert 150.0 <= pred["Oil_Temp"] <= 185.0
    assert 26.5 <= pred["Battery_Voltage"] <= 28.5


def test_temperature_unit_conversions_consistency():
    engine = ReducedOrderPistonEngine()
    p_norm = engine.predict(EngineInputs(rpm=4500.0, ambient_c=25.0))
    p_hot = engine.predict(EngineInputs(rpm=4500.0, ambient_c=45.0))
    
    assert p_hot["CHT"] > p_norm["CHT"]
    assert p_hot["EFI_Water_Temp"] > p_norm["EFI_Water_Temp"]
    assert p_hot["Oil_Temp"] > p_norm["Oil_Temp"]
    assert p_hot["EGT1"] > p_norm["EGT1"]
