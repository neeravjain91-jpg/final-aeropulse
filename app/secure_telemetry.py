"""Prototype Secure Telemetry Layer with HMAC-SHA256 Authentication and Anti-Replay Defense."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .exceptions import SecurityViolationError

@dataclass
class SecurePacket:
    sequence: int
    timestamp_s: float
    drone_id: str
    payload: Dict[str, Any]
    signature: str

class SecureTelemetryManager:
    """Manages telemetry authentication, message integrity, and anti-replay verification."""

    def __init__(self, shared_key: bytes = b"AEROPULSE_X_DEFENCE_PROTOTYPE_KEY_2026", drone_id: str = "UAV-ALPHA-01"):
        self.shared_key = shared_key
        self.drone_id = drone_id
        self.outbound_sequence: int = 0
        self.highest_inbound_sequence: int = -1
        self.max_allowed_time_drift_s: float = 10.0

    def rotate_key(self, new_key: bytes):
        if not new_key or len(new_key) < 16:
            raise SecurityViolationError("Key must be at least 16 bytes", error_code="INVALID_KEY_LENGTH")
        self.shared_key = new_key

    def sign_telemetry(self, telemetry: Dict[str, Any]) -> SecurePacket:
        self.outbound_sequence += 1
        now_ts = time.time()
        payload_str = json.dumps(telemetry, sort_keys=True)
        message_bytes = f"{self.outbound_sequence}:{now_ts:.3f}:{self.drone_id}:{payload_str}".encode("utf-8")
        signature = hmac.new(self.shared_key, message_bytes, hashlib.sha256).hexdigest()

        return SecurePacket(
            sequence=self.outbound_sequence,
            timestamp_s=round(now_ts, 3),
            drone_id=self.drone_id,
            payload=telemetry,
            signature=signature,
        )

    def verify_and_unpack(self, packet: SecurePacket) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        now = time.time()
        if packet.sequence <= self.highest_inbound_sequence:
            return False, None, "REPLAY_DETECTED_STALE_SEQUENCE"
        if abs(now - packet.timestamp_s) > self.max_allowed_time_drift_s:
            return False, None, "TIMESTAMP_DRIFT_EXCEEDED"
        payload_str = json.dumps(packet.payload, sort_keys=True)
        expected_message = f"{packet.sequence}:{packet.timestamp_s:.3f}:{packet.drone_id}:{payload_str}".encode("utf-8")
        expected_signature = hmac.new(self.shared_key, expected_message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(packet.signature, expected_signature):
            return False, None, "HMAC_SIGNATURE_MISMATCH_TAMPERED"

        self.highest_inbound_sequence = packet.sequence
        return True, packet.payload, "AUTHENTICATED_AND_VERIFIED"

    def verify_packet(self, packet: SecurePacket) -> Optional[Dict[str, Any]]:
        valid, payload, reason = self.verify_and_unpack(packet)
        return payload if valid else None

# Alias for backwards compatibility
SecureTelemetryProtocol = SecureTelemetryManager
