# AEROPULSE-X PROTOTYPE SECURE TELEMETRY ARCHITECTURE
## Cryptographic Integrity, Message Authentication & Anti-Replay Defense

**Document Version**: 2.0.0-SIH  
**Release Date**: August 26, 2026  
**Module**: `app/secure_telemetry.py`

---

## 1. Threat Model & Security Scope
> [!NOTE]
> **PROTOTYPE ARCHITECTURE DECLARATION**:  
> This security subsystem is a functional prototype demonstrating authenticated telemetry protection. It is NOT certified for military combat systems (NSA/FIPS-140-3).

### Addressed Threats:
1. **Telemetry Tampering / Man-in-the-Middle (MitM)**: Modifying sensor values in transit.
2. **Replay Attacks**: Replaying healthy telemetry records during an active engine failure.
3. **Spoofed Ingestion**: Submitting fake GCS command packets or synthetic fault states.

---

## 2. Authenticated Telemetry Frame Schema

```
+-------------------------------------------------------------------------------+
|                             SECURE TELEMETRY FRAME                            |
+---------------+---------------+---------------+---------------+---------------+
| Sequence (4B) | Timestamp(8B) | Drone ID (4B) | Payload (JSON)| HMAC-SHA256   |
| uint32        | uint64 (ms)   | string/int    | Telemetry Data| Signature(32B)|
+---------------+---------------+---------------+---------------+---------------+
```

### Signature Formulation:
$$\text{Signature} = \text{HMAC-SHA256}\Big(K_{\text{shared}}, \text{Seq} \,|\, \text{Timestamp} \,|\, \text{DroneID} \,|\, \text{PayloadBytes}\Big)$$

---

## 3. Replay Defense & Sequence Verification
- The GCS receiver maintains a monotonic high-water mark $\text{Seq}_{\max}$.
- Incoming packets with $\text{Seq} \le \text{Seq}_{\max}$ or with timestamp drift $|t_{\text{local}} - t_{\text{packet}}| > 5.0\text{ s}$ are immediately rejected and logged as `SECURITY_REPLAY_ATTACK_DETECTED`.
