from pathlib import Path
import os

_here = Path(__file__).resolve()
ROOT = _here.parents[1] if len(_here.parents) > 1 else Path.cwd()

# If static or models don't exist under ROOT, search cwd
if not (ROOT / "static").exists() and (Path.cwd() / "static").exists():
    ROOT = Path.cwd()

MODEL_DIR = ROOT / "models"
STATIC_DIR = ROOT / "static"
DATA_SAMPLE_DIR = ROOT / "data_sample"

PROJECT_NAME = "AeroPulse-X"
PROJECT_VERSION = "1.0.0-sih"

REQUIRED_MODEL_FILES = (
    "aces_health.joblib",
    "aces_anomaly.joblib",
    "healthy_reference.json",
)
