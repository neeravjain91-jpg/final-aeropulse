# Tests for HMAC-SHA256 authenticated telemetry and anti-replay defense.
import pytest
import time
from app.secure_telemetry import SecureTelemetryManager, SecurePacket


def test_secure_telemetry_valid_authentication():
    sec = SecureTelemetryManager(shared_key=b"TEST_KEY_123", drone_id="UAV-01")
    data = {"Engine_RPM": 3000.0, "CHT": 195.0, "Health": "Normal"}

    packet = sec.sign_telemetry(data)
    assert packet.sequence == 1
    assert len(packet.signature) == 64

    is_valid, payload, status = sec.verify_and_unpack(packet)
    assert is_valid is True
    assert payload == data
    assert status == "AUTHENTICATED_AND_VERIFIED"


def test_secure_telemetry_anti_replay_rejection():
    sec = SecureTelemetryManager(shared_key=b"TEST_KEY_123", drone_id="UAV-01")
    data = {"Engine_RPM": 3000.0}

    packet1 = sec.sign_telemetry(data)
    is_valid1, _, _ = sec.verify_and_unpack(packet1)
    assert is_valid1 is True

    # Attempt replay of packet 1
    is_valid_replay, _, status = sec.verify_and_unpack(packet1)
    assert is_valid_replay is False
    assert status == "REPLAY_DETECTED_STALE_SEQUENCE"


def test_secure_telemetry_tamper_rejection():
    sec = SecureTelemetryManager(shared_key=b"TEST_KEY_123", drone_id="UAV-01")
    data = {"Engine_RPM": 3000.0, "CHT": 195.0}

    packet = sec.sign_telemetry(data)
    # Attacker tampers with payload
    packet.payload["CHT"] = 999.0

    is_valid, _, status = sec.verify_and_unpack(packet)
    assert is_valid is False
    assert status == "HMAC_SIGNATURE_MISMATCH_TAMPERED"
