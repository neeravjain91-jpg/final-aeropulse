"""Contract tests for the leakage-safe health benchmark."""
from scripts.benchmark_health_models import FORBIDDEN_FEATURES, validate_feature_contract


def test_forbidden_feature_contract_rejects_target_leakage():
    features = ["Engine_RPM", "CHT", "Degradation_Severity"]
    try:
        validate_feature_contract({"Health_State": []}, features)
    except AssertionError as exc:
        assert "Degradation_Severity" in str(exc)
    else:
        raise AssertionError("Forbidden degradation label was accepted")


def test_forbidden_contract_does_not_contain_runtime_sensor_features():
    assert "Engine_RPM" not in FORBIDDEN_FEATURES
    assert "CHT" not in FORBIDDEN_FEATURES
    assert "Health_State" in FORBIDDEN_FEATURES
    assert "true_RUL" in FORBIDDEN_FEATURES
