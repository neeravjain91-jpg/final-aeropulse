# AeroPulse-X — Mission-Aware Digital Twin for MALE-UAV Engine Health

**SIH26054 research prototype** for an AI-enabled, real-time Digital Twin of a MALE-UAV aero-piston engine.

AeroPulse-X unifies engine physics, telemetry, diagnostics, and prognostics into a single authoritative propulsion health pipeline:

```text
Mission (Waypoints, Altitude, Speed)
        ↓
Environment (ISA Atmosphere, Live Ambient, Wind Vectors)
        ↓
EngineRunState (ENGINE_OFF / ENGINE_STARTING / ENGINE_RUNNING / ENGINE_STOPPING)
        ↓
ReducedOrderPistonEngine (Thermodynamic Otto Cycle, MAP, Throttle)
        ↓
Authoritative Telemetry (Single Source of Truth)
        ↓
ReferenceTwin (Context-Aware Expected State & Residuals)
        ↓
Model Fusion (ML Diagnostics + Anomaly Detection + Sensor Veto)
        ↓
Health Assessment (Normal / Watch / Warning / Critical)
        ↓
Degradation Tracking (Linear / Exponential Wear Kinetics)
        ↓
RUL Prognostics (Physics-Stress Weighted Trend Extrapolation Method Demonstrator)
        ↓
Mission Risk Assessment & Maintenance Advisory
        ↓
EngineStateRecord (Canonical Serialization)
        ↓
Ground Control Station (GCS Dashboard, 3D WebGL Twin, Replay, What-If)
```

## What the current build does

- **Engine Operational State Machine**: Four explicit engine states:
  - `ENGINE_OFF`: Runtime RPM = 0.0, zero fuel flow, stationary 3D pistons.
  - `ENGINE_STARTING`: Transitional starter cranking (800 RPM).
  - `ENGINE_RUNNING`: Dynamic thermodynamic Otto cycle coupled to throttle and altitude ($\ge 1400$ RPM).
  - `ENGINE_STOPPING`: Cooldown spin-down (400 RPM).
  - *Physical Invariant*: `ReducedOrderPistonEngine.IDLE_RPM` strictly remains `1400.0 RPM`. `ENGINE_OFF` is an application/runtime state outside the active combustion model.
- **Authoritative Data Flow**: Single backend propulsion assessment eliminating redundant or conflicting health/RUL calculations across REST, WebSocket, Replay, and What-If endpoints.
- **Four-state engine health classification**: **Normal / Watch / Warning / Critical** ([0.0, 100.0] index: $100$ nominal, $60$ warning boundary, $35$ critical threshold, $0$ failed).
- **Primary model trained from NASA ACES aero-piston telemetry**:
  - Held-out flight evaluation (`GroupShuffleSplit`, 20% test across 14 independent flights).
  - Leakage-safe training: `Robust_Anomaly_Score` and derived robust-z fields are excluded from health-model inputs.
  - Validated metrics: **86.92% Accuracy, 83.56% Balanced Accuracy, 83.83% Critical Recall, 80.97% Critical F1**.
- **Context-aware Digital Twin reference** for altitude, ambient temperature, endurance, and rapid-throttle scenarios.
- **Unsupervised Anomaly Detection**: Isolation Forest and Temporal Convolutional Autoencoder for out-of-distribution detection ($z \ge 2.0$).
- **Controlled, physically grounded fault injection**:
  - Overheating (CHT / Oil Temp rise)
  - Lubrication degradation (Oil pressure loss + friction drag)
  - Combustion misfire (Cylinder 1 EGT drop + RPM sag + elevated vibration)
  - Injector delivery restriction (Fuel flow drop + MAP rise)
  - Transducer drift/bias (Sensor trust reduction without modifying engine physics)
- **Sensor-Trust & Health Engine**: Multi-channel peer cross-checks and trust veto preventing failed sensors from corrupting consensus health.
- **RUL Prognostics (Physics-Stress Weighted Trend Extrapolation Method Demonstrator)**:
  - $\text{Health} \le 35.0 \implies \text{Critical maintenance required} \to \text{RUL} = 0.0\text{ h}$.
  - $\text{Health slope} < -0.15/\text{h} \implies \text{DEGRADING} \to \text{Finite extrapolated RUL}$.
  - $-0.15/\text{h} \le \text{Slope} \le +0.15/\text{h} \implies \text{STABLE\_OR\_NON\_DEGRADING} \to \text{RUL} = \text{None}$.
  - $\text{Health slope} > +0.15/\text{h} \implies \text{RECOVERY\_OR\_IMPROVING} \to \text{RUL} = \text{None}$ (improving health is strictly never inverted into degradation).
  - Single-count mission stress treatment (no double post-hoc divisors).
- **Offline-friendly GCS Dashboard**: Interactive Leaflet tactical map, Three.js WebGL 3D procedural piston assembly, CAN bus telemetry monitor, mission replay, and What-If comparison tool.

## Dataset Roles & Scientific Domain Boundaries

The supplied datasets originate from different platforms and sensing domains. AeroPulse-X enforces strict domain separation:

```text
NASA ACES (173,878 rows, 14 flights) ──► Altus II operational/mechanical flight telemetry (Rotax 912 piston engine)
CWRU Bearing Dataset (120 .npz files) ──► Proxy Benchmark: 2 hp Electric Motor Test Stand (Vibration DSP only)
ALFA UAV Dataset (47 autonomous runs) ──► Proxy Benchmark: Fixed-Wing UAV Flight Dynamics & Actuators
NASA C-MAPSS / N-CMAPSS (708 runs)    ──► Proxy Benchmark: Turbofan Run-to-Failure RUL Methodology
AeroPulse Synthetic Simulator         ──► Target-Domain: Physics-Informed ODE Engine Degradation Demonstrator
```

### Dataset Facts & Limitations:
1. **NASA ACES**: Real Altus II operational/mechanical flight telemetry (four-cylinder Rotax 912 piston engine) used for operational-envelope health classification and contextual validation. **Does NOT contain run-to-failure degradation trajectories or target-engine RUL ground truth** (all flights completed safely).
2. **CWRU Bearing**: High-frequency vibration data from a stationary electric motor rig. Used strictly for vibration DSP feature extraction benchmarking. **NOT aero-piston ground truth**.
3. **ALFA UAV**: Real flight-control and airframe actuator failure logs from a Carbon Z T-28 UAV. Used for tactical flight risk and navigation validation. **NOT engine ground truth**.
4. **NASA C-MAPSS**: Turbofan engine degradation simulation dataset. Used to validate prognostic regression algorithms. **NOT piston engine ground truth**.
5. **AeroPulse Synthetic Engine**: Physics-informed ODE model of reduced-order Otto-cycle degradation kinetics. Functions as an interactive real-time GCS demonstrator.

## Production Cloud Deployment (Vercel)

- **Live Production URL**: [https://aeropulse-x.vercel.app](https://aeropulse-x.vercel.app)
- **FastAPI Interactive API Docs**: [https://aeropulse-x.vercel.app/docs](https://aeropulse-x.vercel.app/docs)
- **Deployment Status**: Continuous zero-config FastAPI serverless deployment on Vercel Fluid compute with static asset acceleration.

## Quick start — Windows PowerShell (Local Development)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# Run the complete test suite (277 passed)
pytest -v

# Launch the real-time application
python run.py
```

Open local dashboard:

```text
http://127.0.0.1:8000/
```

FastAPI interactive documentation:

```text
http://127.0.0.1:8000/docs
```

## System Test Suite & CI

- **Verified Test Suite**: **277 passed, 0 failed, 0 skipped, 0 xfailed** across all test modules.
- **Continuous Integration (CI)**: GitHub Actions workflow running on Python 3.11 with PyTorch (CPU) and scikit-learn dependency management.

## Safety and Scientific Scope

This project is an **SIH / research software demonstrator**. It is not a certified flight-safety, airworthiness, maintenance-release, or operational defence system. Mission-risk, sensor-trust, and RUL outputs function as mathematically grounded decision-support tools and require physical dynamometer test-cell calibration before operational flight use.

## Repository structure

```text
AeroPulse-X/
├── app/
│   ├── main.py              # FastAPI routes and asset lifecycle
│   ├── inference.py         # AI health/anomaly inference
│   ├── digital_twin.py      # context-aware healthy reference twin
│   ├── simulator.py         # mission adjustments + fault injection
│   ├── sensor_health.py     # cross-sensor trust logic
│   ├── risk.py              # explainable mission-risk index
│   ├── degradation.py       # RUL/trend method demonstrator
│   ├── replay.py            # mission replay engine
│   ├── advisory.py          # fault evidence + maintenance advice
│   └── vibration.py         # isolated CWRU supporting model
├── scripts/
│   ├── train_models.py
│   └── train_rul_cmapss.py
├── static/index.html        # offline-friendly GCS dashboard
├── tests/
├── docs/
├── requirements.txt
└── run.py
```

## SIH pitch

> **AeroPulse-X continuously mirrors expected engine behaviour, compares it with observed telemetry, detects and explains emerging anomalies, evaluates sensor trust, projects degradation, replays mission behaviour, and translates engine condition into mission-level maintenance decision support.**

See `docs/SIH_DEMO.md` for the recommended live demonstration sequence.
