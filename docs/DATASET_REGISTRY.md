# Dataset Registry & Scientific Provenance Catalog

## 1. Master Dataset Catalog

| Dataset ID | Name | Domain | Type | Provenance & Relevance | Ground Truth RUL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AERO_PULSE_SYNTHETIC` | AeroPulse-X Synthetic Aero-Piston Degradation & SIL Corpus | Reciprocating IC Aero-Piston | Synthetic | Primary physics-informed aero-piston/RUL demonstrator | Exact Mathematical RUL ($H=35.0$) |
| `NASA_ACES` | NASA ACES — Altus II Operational Flight Telemetry | General Aviation Reciprocating IC | Real Operational | Operational-envelope & contextual cross-domain validation | None (Contains NO run-to-failure RUL ground truth) |
| `NASA_CMAPSS` | NASA C-MAPSS Turbofan Degradation Benchmark (FD001-FD004) | Turbofan Gas Turbine | Cross-Domain Proxy | Turbofan cross-domain RUL/prognostics proxy | Run-to-Failure Cycle Ground Truth |
| `CWRU_BEARING` | Case Western Reserve University Bearing Vibration Benchmark | Rotating Machinery | Cross-Domain Proxy | Rotating-machinery/bearing vibration proxy | Seeded Fault Diameters (EDM) |
| `ALFA_UAV` | CMU AirLab Failure & Anomaly Dataset for Fixed-Wing UAVs | Fixed-Wing UAV Flight Dynamics | Cross-Domain Proxy | UAV flight/failure/anomaly proxy | In-Flight Injected Actuator Faults |

---

## 2. Scientific Boundaries & Disclaimers
1. **Target Engine Ground Truth**: Real run-to-failure telemetry for the Rotax 914 F is unavailable in open literature. Therefore, `AERO_PULSE_SYNTHETIC` serves as the physics-informed benchmark.
2. **NASA ACES Disclosure**: NASA ACES provides real Altus II operational/mechanical flight telemetry used strictly for operational-envelope and contextual cross-domain validation; it contains **NO run-to-failure RUL ground truth** and is **not** target-engine Rotax 914 data.
3. **Cross-Domain Proxy Disclosure**: NASA C-MAPSS (turbofan gas turbine), CWRU (electric motor bearing), and ALFA (electric fixed-wing UAV) are utilized strictly as cross-domain algorithmic proxies.
