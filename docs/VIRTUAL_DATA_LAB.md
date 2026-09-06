# AeroPulse-X Virtual Data Laboratory (VDL)

## 1. Executive Summary & Purpose
The **AeroPulse-X Virtual Data Laboratory** is a software-in-the-loop (SIL) data generation, validation, and closed-loop replay platform designed for MALE UAV aero-piston digital twin prognostics (SIH Problem Statement SIH26054).

Because physical test-cell dynamometer wear experiments, physical ECU/FADEC benches, and aircraft flight testbeds are unavailable, the Virtual Data Lab provides a rigorous, physics-grounded synthetic telemetry generator and provenance catalog. It simulates reciprocating internal combustion thermodynamics, continuous wear kinetics, transducer corruptions, electrical bus sag, virtual CAN 2.0B bus framing, and flight computer scheduler metrics under reproducible conditions.

---

## 2. High-Level Architecture
```
+-----------------------------------------------------------------------------------+
|                        AEROPULSE-X VIRTUAL DATA LABORATORY                         |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ Mission & Environment ]  --> 8 Flight Phases, ISA Barometric Profile (0-18k ft)|
|              |                                                                    |
|              v                                                                    |
|  [ First-Principles Physics] --> Otto Cycle, MAP, Friction, Lumped Capacitance    |
|              |                                                                    |
|              v                                                                    |
|  [ Degradation Kinetics ]   --> Arrhenius/Power-Law Wear to H_failure = 35.0      |
|              |                                                                    |
|              v                                                                    |
|  [ Virtual Sensors & ADC ]  --> Noise, Bias, Drift, Saturation, 12-bit ADC        |
|              |                                                                    |
|              v                                                                    |
|  [ Virtual ECU & CAN 2.0B]  --> ISO 11898 Framing, IDs 0x100..0x104, CRC-8       |
|              |                                                                    |
|              v                                                                    |
|  [ Flight Computer & Watchdog]-> Periodic Task Schedulers, Deadline Monitoring   |
|              |                                                                    |
|              v                                                                    |
|  [ Edge & Digital Twin ]    --> Residual Diagnosis, Sensor Trust, RUL Prognosis  |
|              |                                                                    |
|              v                                                                    |
|  [ Virtual FADEC Control ]  --> Supervisory Derate Clamping & Closed-Loop Action |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 3. Key Capabilities & Functional Modules
1. **Canonical Telemetry Schema v2.0 (`app/data_schema.py`)**:
   - 50+ strongly typed parameters covering all layers of the aero-propulsion twin.
   - Physical plausibility bounds validation.
   - Exact mathematical ground-truth RUL ($y_{\text{true}} = \max(0, t_{\text{failure}} - t)$).
2. **Dataset Registry (`app/dataset_registry.py`)**:
   - Master catalog of 5 datasets (`AERO_PULSE_SYNTHETIC` primary demonstrator, `NASA_ACES` operational context, `NASA_CMAPSS` turbofan proxy, `CWRU_BEARING` vibration proxy, `ALFA_UAV` flight anomaly proxy).
   - Clear disclosure of synthetic boundaries and proxy domains.
3. **Data Generation Engine (`app/data_engine.py`)**:
   - Multi-phase healthy mission trajectories across 8 flight phases.
   - Progressive degradation trajectories across 7 failure modes down to critical $H = 35.0$.
   - Sensor fault isolation (transducer corrupted without altering engine physics).
   - Strict trajectory-level train/test partitioning (`Trajectory-level leakage audit: PASS`).
4. **Data Quality Validator (`app/data_validator.py`)**:
   - Automated auditing for NaNs, physical bounds, timestamp monotonicity, causal coupling, and split leakage.
5. **Closed-Loop Replay Engine (`app/data_replay.py`)**:
   - Point-by-point playback through the entire SIL digital twin pipeline.
6. **Web API & Interactive Dashboard (`app/main.py`, `static/index.html`)**:
   - 8 REST endpoints under `/api/v1/data/*`.
   - Dedicated "Virtual Data Lab" UI tab with Scenario Generator, 10-node Live Visual Causal Flow Ribbon, side-by-side Ground Truth vs Model Prognostics table, and Quality Audit view.

---

## 4. Scientific Positioning & Verification Boundaries
- **Software-Only Demonstrator**: All aero-piston data is generated via first-principles mathematical and empirical models.
- **No Physical Measurements Claimed**: Hardware dynamometer, physical ECU, physical CAN transceivers, and flight computers remain unattached.
- **NASA ACES Provenance**: NASA ACES — Altus II operational/mechanical flight telemetry used for operational-envelope/contextual cross-domain validation; contains NO run-to-failure RUL ground truth.
- **Proxy Dataset Disclosure**: NASA C-MAPSS is an algorithmic turbofan proxy; CWRU is a rotating bearing proxy; ALFA is an autonomous UAV flight anomaly proxy.
