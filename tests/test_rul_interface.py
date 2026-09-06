import pytest
from pathlib import Path
import pandas as pd
from app.degradation_interface import DegradationDataLoader, EngineRunToFailureRecord

def test_degradation_schema_validation(tmp_path):
    valid_csv = tmp_path / "valid_deg.csv"
    data = {
        "engine_id": ["ENG_001"],
        "timestamp": [1700000000.0],
        "operating_hours": [125.5],
        "engine_rpm": [4540.0],
        "cht_f": [205.0],
        "egt_f": [1280.0],
        "oil_pressure_psi": [61.0],
        "oil_temperature_f": [175.0],
        "fuel_flow_lh": [38.0],
        "vibration_g": [0.85],
        "altitude_ft": [8000.0],
        "ambient_temperature_c": [22.0],
        "load": [0.65],
        "health_state": ["Normal"]
    }
    pd.DataFrame(data).to_csv(valid_csv, index=False)
    
    df = DegradationDataLoader.validate_and_load(valid_csv)
    assert len(df) == 1
    assert df["engine_id"].iloc[0] == "ENG_001"

def test_degradation_missing_columns_raises(tmp_path):
    invalid_csv = tmp_path / "invalid_deg.csv"
    pd.DataFrame({"engine_id": ["ENG_001"], "timestamp": [1.0]}).to_csv(invalid_csv, index=False)
    with pytest.raises(ValueError, match="missing required degradation schema columns"):
        DegradationDataLoader.validate_and_load(invalid_csv)
