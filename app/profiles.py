# Deployment Profiles for AeroPulse-X
from enum import Enum

class DeploymentProfile(str, Enum):
    DEVELOPMENT = "development"
    GCS = "gcs"
    EDGE = "edge"

CURRENT_PROFILE = DeploymentProfile.GCS
