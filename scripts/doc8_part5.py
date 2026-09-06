
### PART 5 — Competitive Positioning, Judging & Project Truth (Questions 41 to 50)

#### Q41: In one sentence, what is AeroPulse-X?
- **Evidence-Based Answer:** **AeroPulse-X is a physics-informed, Software-in-the-Loop Digital Twin demonstrator that couples reduced-order Otto cycle thermodynamics with fast machine learning to deliver real-time health monitoring, sensor fault isolation, and stress-weighted RUL prognostics for MALE UAV aero-piston powerplants.**

#### Q42: What makes AeroPulse-X different from other SIH26054 student projects?
- **Evidence-Based Answer:** Most student projects build standalone UI dashboards with generic machine learning applied to static CSV files. AeroPulse-X implements a **complete end-to-end 4-tier SIL signal chain**: from physical Otto cycle thermodynamics and 12-bit ADC quantization, through CAN 2.0B bus framing and HMAC-SHA256 authenticated security, to closed-loop Virtual FADEC emergency derating and a 3D WebGL ground station.

#### Q43: What does the competing project DRDO-UAV-EngineTwin do better than AeroPulse-X?
- **Evidence-Based Answer:** DRDO-UAV-EngineTwin implements formal **Extended Kalman Filter (EKF)** state estimation for stochastic state tracking and integrates **SHAP** for granular post-hoc feature attribution. AeroPulse-X chose dynamic z-score residuals and physical causal scoring to achieve sub-0.02 ms latency for edge computing.

#### Q44: What does AeroPulse-X do better than DRDO-UAV-EngineTwin?
- **Evidence-Based Answer:** AeroPulse-X has a substantially more comprehensive **avionics SIL pipeline** (Virtual 12-bit ADC, CAN 2.0B with CRC-8, Virtual ECU, Virtual FADEC safety derating, Virtual Power/Watchdog), cryptographically authenticated HMAC-SHA256 telemetry, a zero-dependency 3D WebGL tactical ground station, and a formal dataset provenance registry cataloging domain boundaries.

#### Q45: Is AeroPulse-X flight-ready for deployment on an Indian Army or Navy UAV tomorrow?
- **Evidence-Based Answer:** **No.** AeroPulse-X is currently at **Technology Readiness Level 4 (TRL 4 — Software Demonstrator validated in laboratory environment)**. Flight deployment requires porting to DO-254 / DO-178C certified embedded hardware, physical CAN transceiver interfacing, and physical dynamometer test-cell calibration.

#### Q46: What datasets were actually used, and what does each prove?
- **Evidence-Based Answer:**
  1. AeroPulse Synthetic Corpus (180,000 samples): Primary training & testing benchmark with exact mathematical RUL ground truth.
  2. NASA ACES (Altus II UAV): Validates real flight operational envelopes and sensor distributions (R^2 = 0.9308).
  3. NASA C-MAPSS: Algorithmic proxy validating temporal TCN and Weibull prognostic performance.
  4. CWRU Bearing Data: Calibration proxy for mechanical bearing vibration harmonics.
  5. CMU ALFA UAV: Avionics proxy for tactical GCS replay and RTL navigation logic.

#### Q47: What are the top 3 scientific limitations of this project?
- **Evidence-Based Answer:**
  1. Reliance on synthetic ODE degradation kinetics rather than physical run-to-failure engine test-cell measurements.
  2. Quasi-steady thermodynamic modeling with lumped thermal mass approximations rather than 3D computational fluid dynamics.
  3. Edge benchmarks measured on desktop host CPU rather than physical embedded ARM SBC hardware.

#### Q48: How many automated tests exist, and what is their status?
- **Evidence-Based Answer:** The test suite contains **277 automated tests**, covering unit physics, ML classification, RUL uncertainty, CAN framing, HMAC security, virtual hardware SIL, and production APIs. **100% (277/277) pass green in 67 seconds.**

#### Q49: What is the production deployment status of AeroPulse-X?
- **Evidence-Based Answer:** AeroPulse-X is live in production on **Vercel Serverless (Fluid Compute ASGI)** at https://aeropulse-x.vercel.app, supporting responsive desktop/mobile tactical visualization with zero external database dependencies.

#### Q50: What is the Phase 2 deployment roadmap for DRDO / ADE integration?
- **Evidence-Based Answer:**
  1. Hardware Integration (Months 1–3): Deploy UAV Edge Node to Raspberry Pi CM4 / NVIDIA Jetson Orin Nano connected to physical MCP2515 CAN transceiver.
  2. Test-Cell Calibration (Months 4–6): Calibrate thermodynamic coefficients on DRDO instrumented engine dynamometer test bench.
  3. Flight Testing (Months 7–12): Interface with MALE UAV avionics bus for non-intrusive shadow flight telemetry monitoring.
