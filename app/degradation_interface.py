from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import pandas as pd
from pathlib import Path

@dataclass
class EngineRunToFailureRecord:
    engine_id: str
    timestamp: float
    operating_hours: float
    engine_rpm: float
    cht_f: float
    egt_f: float
    oil_pressure_psi: float
    oil_temperature_f: float
    fuel_flow_lh: float
    vibration_g: float
    altitude_ft: float
    ambient_temperature_c: float
    load: float
    health_state: str
    failure_mode: Optional[str] = None
    failure_timestamp: Optional[float] = None

class DegradationDataLoader:
    """Interface schema for future empirical run-to-failure datasets."""
    REQUIRED_COLUMNS = [
        "engine_id", "timestamp", "operating_hours", "engine_rpm",
        "cht_f", "egt_f", "oil_pressure_psi", "oil_temperature_f",
        "fuel_flow_lh", "vibration_g", "altitude_ft", "ambient_temperature_c",
        "load", "health_state"
    ]

    @classmethod
    def validate_and_load(cls, file_path: str | Path) -> pd.DataFrame:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Degradation dataset {file_path} not found.")
        df = pd.read_csv(p)
        missing = [c for c in cls.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Dataset missing required degradation schema columns: {missing}")
        return df
