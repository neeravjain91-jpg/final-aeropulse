# AEROPULSE-X: REAL-TIME VS. STATIC / SIMULATED FEATURE AUDIT
**Classification and Data Flow Lineage for All UI Subsystems and Dashboard Telemetry**

---

## 1. Executive Summary & Audit Mandate

This audit establishes the definitive classification for every data display, metric gauge, chart series, and operational indicator across the AeroPulse-X Ground Control Station (GCS) and Propulsion Digital Twin platform. To uphold uncompromising scientific integrity, every interface element is rigorously categorized according to its authoritative runtime source:

1. **`LIVE_STREAM`**: Streaming telemetry received over UDP/WebSocket/CAN from active sensor transducers or real-time simulation loops.
2. **`PHYSICS_DERIVED`**: Computed dynamically at runtime from first-principles thermodynamic and kinematic state equations (Reduced-Order Engine Model, ISA barometric lapse, Bishop-Heywood friction).
3. **`ML_DERIVED`**: Computed in real-time by edge machine learning inference engines (HGB-PRO Gradient Boosting, 1D Dilated Causal TCN, Temporal Conv Autoencoder, Weibull Prognostics).
4. **`SIMULATED_REPLAY`**: Generated deterministically from seed-reproducible flight trajectories or historical ACES telemetry replay buffers.
5. **`STATIC_CONFIG`**: Fixed hardware constants, calibration baselines, schema definitions, or UI structural parameters.

---

## 2. Comprehensive Subsystem Lineage Matrix

| Subsystem / UI Component | Display Element / Metric | Data Source Classification | Underlying Engine / Algorithm | Update Frequency |
| :--- | :--- | :--- | :--- | :--- |
| **Piston / Core Visualizer** | Piston Displacement & Stroke | `PHYSICS_DERIVED` | Kinematic Slider-Crank Slider Geometry (\(s(	heta)\)) | 60 Hz / Frame |
| | Combustion Flame & Heat Map | `PHYSICS_DERIVED` | Otto Cycle Peak Pressure & Temperature Equations | 60 Hz / Frame |
| | RPM & Crank Angle | `LIVE_STREAM` / `SIMULATED_REPLAY` | Crankshaft Encoder / Scenario Generator | 10 Hz |
| **Telemetry Dashboard** | CHT (Cylinder Head Temp) | `LIVE_STREAM` | Thermocouple Transducer (0.1 °F resolution) | 10 Hz |
| | EGT 1, 2, 3 (Exhaust Gas) | `LIVE_STREAM` | Type-K Thermocouples | 10 Hz |
| | MAP (Manifold Absolute Press) | `LIVE_STREAM` | Piezoresistive MAP Transducer (inHg) | 10 Hz |
| | Fuel Flow Rate (l/h) | `LIVE_STREAM` | Turbine Flow Meter | 10 Hz |
| | Oil Pressure & Temp | `LIVE_STREAM` | Piezoresistive / RTD Transducers | 10 Hz |
| | Bus Voltage & Alternator Current | `LIVE_STREAM` | Hall-Effect Current Sensor / Voltage Divider | 10 Hz |
| **Digital Twin Physics Tab** | Physics Residuals (\(\Delta y\)) | `PHYSICS_DERIVED` | \(y_{\text{measured}} - y_{\text{twin}}\) (ReducedOrderEngine) | 10 Hz |
| | Residual Z-Scores (\(Z_i\)) | `PHYSICS_DERIVED` | Normalized \((y - \mu_0)/\sigma_0\) via Baseline Calibration | 10 Hz |
| | Normalized Residual Slopes | `PHYSICS_DERIVED` | Dynamic Trend Differentiation (\(\Delta Z / \Delta t\)) | 2 Hz |
| | Indicated & Brake Power (kW) | `PHYSICS_DERIVED` | Otto Cycle & Bishop-Heywood Friction Model | 10 Hz |
| | Volumetric Efficiency (\(\eta_v\)) | `PHYSICS_DERIVED` | Speed-Density Plenum Dynamic Filling Equation | 10 Hz |
| **Diagnostics & Health** | Health State (Normal/Watch/Critical)| `ML_DERIVED` | HGB-PRO Gradient Boosting + Multi-Model Fusion | 10 Hz |
| | Temporal Fault Classification | `ML_DERIVED` | Lightweight 1D Dilated Causal TCN (30-step window)| 2 Hz |
| | Unknown Anomaly Score (\(L_{\text{recon}}\))| `ML_DERIVED` | Temporal Convolutional Autoencoder (\(99.5\%\) threshold)| 2 Hz |
| | Diagnostic Confidence (\(C_f\)) | `ML_DERIVED` | Fused Consensus Matrix + Residual Slopes | 10 Hz |
| | Reason Codes & Root-Cause Trace | `ML_DERIVED` | DiagnosticEvidence Rule-Based Inference Engine | Event-Driven |
| **Sensor Trust Matrix** | Overall Trust Score (\(0-100\%\)) | `PHYSICS_DERIVED` | Cross-Sensor Physical Consistency Matrix | 10 Hz |
| | Suspect Sensor Channel Badges | `PHYSICS_DERIVED` | Dual-Sensor Implausibility & Dropout Detector | 10 Hz |
| **RUL Prognostics Tab** | Estimated RUL (Hours) | `ML_DERIVED` | Empirical Degradation Slope & Weibull Failure Model| 1 Hz |
| | RUL 90% Confidence Bounds | `ML_DERIVED` | Monte Carlo / Variance Propagation (\(\pm 1.645 \sigma\))| 1 Hz |
| | Degradation Severity Index | `PHYSICS_DERIVED` | Cumulative Stress Integral (Thermal + Mechanical) | 1 Hz |
| | Model Assumptions Notice | `STATIC_CONFIG` | Explicit Disclaimer: Weibull \(\beta=2.4, \eta=2200\text{h}\) | Persistent |
| **Mission Map & Navigation** | UAV GPS Coordinates (Lat/Lon) | `SIMULATED_REPLAY` / `LIVE_STREAM` | Great-Circle Haversine Interpolator / GPS NMEA | 5 Hz |
| | Flight Altitude & Ground Speed | `SIMULATED_REPLAY` / `LIVE_STREAM` | Barometric Altimeter & Wind Vector Triangle | 5 Hz |
| | Wind Vector & Headwind/Crosswind | `PHYSICS_DERIVED` | Aerodynamic Vector Decomposition (\(V_w, \theta_w\)) | 5 Hz |
| | Waypoint Path & Remaining Legs | `SIMULATED_REPLAY` | Tactical Mission Flight Plan Route Definition | 1 Hz |
| **What-If Mission Simulator** | Alternative Altitude & Weather | `SIMULATED_REPLAY` | User-Defined Scenario Vectors | Interactive |
| | Projected Fuel Burn & Stress | `PHYSICS_DERIVED` | Reduced-Order Engine Model State Integration | Interactive |
| | Mission Risk Score | `ML_DERIVED` | Risk Matrix conditioned on Projected Health & Terrain | Interactive |
| **Security & Communications** | HMAC-SHA256 Packet Signatures | `LIVE_STREAM` | Defence Telemetry Authenticator (RFC 2104) | 10 Hz |
| | Anti-Replay Counter & CRC8 | `LIVE_STREAM` | Monotonic Sequence Verification & ISO 11898 CRC | 10 Hz |
| | Profile Indicator (DEV/GCS/EDGE) | `STATIC_CONFIG` | Runtime Environment Profile Configuration | Boot |

---

## 3. Boundary Verification & Grounding Guarantee

1. **Zero Data Fabrication**: All ACES baseline metrics and model parameters are grounded in real NASA ACES telemetry files or analytical thermodynamics.
2. **Explicit Separation**: Simulated scenarios and synthetic fault injections are prominently labeled `[SIMULATED]` or `[REPLAY]`.
3. **Hardware Transparency**: All network drivers (CAN, GPS, Serial) feature transparent HALs with graceful simulated fallbacks and explicit indicators when operating in non-hardware environments.
