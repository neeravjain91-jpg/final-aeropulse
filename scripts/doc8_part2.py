
### PART 2 — UAV Flight Avionics & Telemetry Engineering (Questions 11 to 20)

#### Q11: How is the CAN bus implemented, and does it adhere to aviation standards?
- **Evidence-Based Answer:** AeroPulse-X implements standard CAN 2.0B (ISO 11898) framing with 8-byte payload packing in app/can_bus.py and app/virtual_can_bus.py. It defines 5 dedicated arbitration IDs: 0x100 (Engine Dynamics), 0x101 (Thermal Matrix), 0x102 (Lubrication/Coolant), 0x103 (Electrical/Vibration), and 0x104 (Diagnostic Status/DTCs). It supports CRC-8 integrity verification and simulated SocketCAN Linux interfaces.

#### Q12: Is your CAN bus running on physical transceivers or in software?
- **Evidence-Based Answer:** It is a **Software-in-the-Loop (SIL) simulation**. It models bit stuffing, frame transmission latency (128 microseconds per frame at 500 kbps), priority-based bus arbitration, queue overflows, and bit corruption, but has not yet been attached to physical microchip MCP2515 CAN transceivers.

#### Q13: What happens when CAN packets are dropped or corrupted?
- **Evidence-Based Answer:** Frames with CRC-8 mismatches or corrupted bytes are immediately dropped and logged (VirtualCANBus.receive_frame()). The UAV Edge Node detects sequence discontinuities and missing packets, flagging a communication health warning while holding the last valid state for a bounded 200 ms timeout window.

#### Q14: How does AeroPulse-X secure telemetry downlinks against spoofing and replay attacks?
- **Evidence-Based Answer:** Telemetry packets are encapsulated with an **HMAC-SHA256 signature** computed over (monotonic_sequence, timestamp_ms, drone_id, payload) in app/secure_telemetry.py. The GCS verifies HMAC integrity using constant-time comparison (hmac.compare_digest), rejecting tampered bytes, duplicate sequence numbers, and stale packets (|Delta t| > 10 s).

#### Q15: Does AeroPulse-X encrypt engine telemetry?
- **Evidence-Based Answer:** **No.** AeroPulse-X implements cryptographic **authentication and data integrity verification**, NOT encryption. In tactical telemetry, authentication and low latency are prioritized over heavy asymmetric encryption overhead.

#### Q16: How does the Tactical GCS visualize real-time mission telemetry?
- **Evidence-Based Answer:** The GCS (static/app.js and static/index.html) is a zero-dependency Vanilla ES6+ WebGL dashboard. It integrates Leaflet.js for tactical moving-map GPS tracking (with divert airfield range rings) and Three.js / WebGL for an interactive 3D aero-piston engine cutaway featuring RPM-linked rotation and thermal color-gradient mapping.

#### Q17: Does the SIH Problem Statement require live GPS map tracking?
- **Evidence-Based Answer:** **No.** The SIH PS specifies engine health monitoring, fault prediction, and mission simulation. Live geographical map tracking is an **AeroPulse-X architectural extension** engineered to contextualize engine thermal stress against 3D altitude and flight waypoints.

#### Q18: How does the deterministic Mission Replay engine function?
- **Evidence-Based Answer:** app/data_replay.py parses historical flight trajectory logs (JSON/CSV), reconstructing step-by-step telemetry streams at variable playback speeds (1x to 10x), enabling post-flight black-box analysis and incident investigation.

#### Q19: What is the Virtual FADEC, and how does it protect the engine?
- **Evidence-Based Answer:** app/virtual_fadec.py implements autonomous closed-loop safety control laws. When CHT exceeds 135 C or oil pressure drops below 2.0 bar, the Virtual FADEC overrides manual pilot throttle, dynamically derating engine power by up to 30% to stabilize temperatures and extend flight range to an emergency divert base.

#### Q20: Can your Virtual FADEC control a physical aircraft engine today?
- **Evidence-Based Answer:** **No.** It is a software SIL control law demonstrator. Interfacing with physical actuator servos requires DO-178C / DO-254 certifiable embedded hardware.
