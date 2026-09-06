import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from app.tcn_model import build_sequences

def test_zero_temporal_leakage_between_flight_missions():
    csv_path = Path("FINAL_DATASET/ACES/aces_health.csv")
    if not csv_path.exists():
        pytest.skip("Dataset file not available for leakage test.")
    
    df = pd.read_csv(csv_path, nrows=5000)
    train_flights = ["aces1am_2002_191"]
    test_flights = ["aces1am_2002_192"]
    
    tr_df = df[df["Flight"].isin(train_flights)]
    te_df = df[df["Flight"].isin(test_flights)]
    
    if len(tr_df) > 35 and len(te_df) > 35:
        X_tr, y_tr = build_sequences(tr_df, window_size=30, step=10)
        X_te, y_te = build_sequences(te_df, window_size=30, step=10)
        
        assert len(X_tr) > 0
        assert len(X_te) > 0
        assert set(tr_df["Flight"].unique()).isdisjoint(set(te_df["Flight"].unique()))
