# AeroPulse-X — Master Jury Defense & Adversarial Q&A Compendium
## 50 Highly Adversarial Technical Questions and Evidence-Backed Answers for DRDO, Avionics, AI/ML, and Reliability Panels

**Document ID:** AEROPULSE-X-JURY-QA-2026-09-06  
**Target Evaluation Panel:** DRDO Propulsion Engineers, UAV Flight Avionics Specialists, AI/ML Scientists, Reliability/Prognostics Engineers, and SIH Judges.

---

### PART 1 — DRDO Propulsion & Thermodynamics Engineering (Questions 1 to 10)

#### Q1: Why did you choose the Rotax 914 F engine as your baseline rather than an indigenous or turbofan engine?
- **Evidence-Based Answer:** The Rotax 914 F Turbo is the canonical operational powerplant for modern tactical MALE UAVs globally (including platforms in the class of TAPAS-BH-201 and Heron). It possesses fully documented civil certification envelopes (EASA TCDS E.122) and published thermodynamic limits (84.5 kW max continuous power, 135 °C CHT limit, 1.5–7.0 bar oil pressure), providing an auditable, unclassified ground truth for thermodynamic modeling. Furthermore, AeroPulse-X implements a protocol-based modular architecture (IEngineModel), allowing indigenous powerplants to be substituted via a single Python plugin (pp/plugins/rotax914.py).

#### Q2: How does your digital twin model internal combustion and thermal heat rejection?
- **Evidence-Based Answer:** We employ a reduced-order lumped-capacitance 4-stroke Otto cycle model (pp/engine_model.py). Mass air flow is calculated via speed-density dynamics ($\dot{m}_{air} = \frac{N}{120} V_d \rho_{man} \eta_v$), fuel flow is metered via speed-density air-fuel ratio ({actual}$), and heat release is computed from fuel Lower Heating Value ({in} = \dot{m}_{fuel} \cdot LHV \cdot \eta_{comb}$). Thermal rejection ({rej} = P_{ind} \cdot (1 - \eta_{th}) / \eta_{th}$) is partitioned across coolant and oil circuits with convective heat transfer scaling dynamically with airspeed and ISA ambient temperature lapse.

#### Q3: How is engine friction modeled, and why is it not treated as a constant?
- **Evidence-Based Answer:** Friction is non-linear and increases with rotational speed and oil degradation. We implement the Bishop-Heywood hydrodynamic friction correlation (pp/engine_model.py):
  P_{friction} = \left( P_{friction,base} + c \cdot \left(\frac{N}{N_{max}}\right)^{1.8} \right) \cdot \mu_{friction}
  This captures boundary and hydrodynamic shear losses. When oil degrades (e.g. viscosity loss), $\mu_{friction}$ dynamically increases, resulting in lower brake horsepower ({brake} = P_{ind} - P_{friction}$) and higher oil temperature.

#### Q4: How does atmospheric altitude affect the engine in your simulation?
- **Evidence-Based Answer:** We implement the standard International Standard Atmosphere (ISA) barometric lapse:
  T(h) = T_0 - L \cdot h, \quad P(h) = P_0 \left(1 - \frac{L \cdot h}{T_0}\right)^{\frac{g}{R \cdot L}}, \quad \rho(h) = \frac{P(h)}{R \cdot T(h)}
  As altitude climbs toward the critical turbocharger altitude (15,000 ft), manifold absolute pressure (MAP) is maintained by the turbo wastegate; above critical altitude, MAP decreases monotonically with density ratio $\sigma = \rho / \rho_0$, reducing indicated power and air cooling efficiency.

#### Q5: Is your engine model steady-state or dynamic transient?
- **Evidence-Based Answer:** It is a **quasi-steady thermodynamic cycle with first-order dynamic thermal lag**. While gas exchange is computed at discrete operational steps, thermal masses (cylinder head temperature, coolant, oil) integrate differential heat accumulation equations ( C_p \frac{dT}{dt} = Q_{in} - Q_{out}$), capturing thermal inertia during rapid throttle steps.

#### Q6: How are Exhaust Gas Temperatures (EGT) distributed across individual cylinders?
- **Evidence-Based Answer:** The model computes baseline manifold EGT from combustion enthalpy, then tracks individual cylinder offsets (EGT1, EGT2, EGT3, EGT4). In the event of a cylinder misfire or injector fouling on Cylinder 1, EGT1 experiences an immediate localized drop (-28%) while unburned fuel increases exhaust instability, isolating the fault to a specific cylinder.

#### Q7: What is the source of your thermal transfer coefficients?
- **Evidence-Based Answer:** Coefficients (, h_{conv}, k_{rad}$) were calibrated against Rotax 914 F operator limits and verified against NASA ACES Altus II flight envelopes (^2 = 0.9308$). They are explicitly documented in docs/ENGINE_PARAMETER_ASSUMPTIONS.md as fitted parameters rather than proprietary manufacturer test-cell data.

#### Q8: What happens during a rapid throttle transition?
- **Evidence-Based Answer:** Rapid throttle increases MAP and combustion heat instantaneously, while RPM ramps up according to propeller load inertia, and CHT accumulates heat over a 15–30 second thermal transient window, preventing false-positive thermal spike alarms.

#### Q9: Can this model simulate detonation or pre-ignition?
- **Evidence-Based Answer:** Detonation is captured empirically via the combustion instability mode (pp/degradation_model.py), where severe thermal runaway and lean AFR trigger high-frequency vibration harmonics and rapid CHT accumulation.

#### Q10: Has this engine model been validated on a physical dynamometer test cell?
- **Evidence-Based Answer:** **No.** Physical test-cell validation is currently UNAVAILABLE. The model has been verified mathematically, calibrated against published OEM type certificates (EASA E.122), and cross-checked against NASA ACES flight logs. Physical test-cell runs represent the next phase in our deployment roadmap.

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

### PART 3 — AI/ML, Data Quality & Scientific Leakage (Questions 21 to 30)

#### Q21: Why did you select HistGradientBoostingClassifier over Deep Neural Networks (LSTM/Transformers)?
- **Evidence-Based Answer:** Tabular and physical sensor residuals in edge environments benefit significantly from tree-based histogram gradient boosting (scikit-learn). HGB achieves **96.8% accuracy and 96.1% macro F1** while executing inference in **0.005 ms (<5 microseconds)** with a model size of only **1.1 MB**, compared to heavy neural networks that require GPU acceleration and introduce non-deterministic edge latency.

#### Q22: How did you prevent data leakage during ML model training?
- **Evidence-Based Answer:** We enforced strict **Trajectory-Level GroupKFold Partitioning** (GroupKFold with 5 splits grouped by trajectory_id). Zero flight trajectories are shared between train and test splits, eliminating temporal autocorrelation cross-talk. All preprocessors (StandardScaler) are fit strictly on training folds.

#### Q23: Isn't your ML model just learning the rules of your own synthetic simulator (Circular Validation)?
- **Evidence-Based Answer:** **Yes, this is an inherent scientific constraint of synthetic data validation.** The ML model is trained on physics-generated trajectories; therefore, high test accuracy proves that the classifier has successfully learned the non-linear degradation relationships of our physics simulation. We explicitly declare this in docs/AEROPULSE_X_DATASET_AUDIT.md and do NOT claim it represents physical experimental ground truth.

#### Q24: How does your system distinguish between a Genuine Engine Overheat and a Faulty CHT Sensor?
- **Evidence-Based Answer:** Through our **Multi-Sensor Trust Matrix** (app/sensor_trust.py and tests/test_virtual_sil.py). A genuine engine overheat creates thermodynamic cross-coupling: CHT rises, coolant temperature rises, and oil temperature rises. If the CHT sensor spikes or drifts while coolant and oil temperatures remain nominal, the Sensor Trust Matrix vetoes the CHT reading, isolates it as a transducer fault (96.5% isolation accuracy), and prevents false FADEC derating.

#### Q25: What is the role of the Temporal Convolutional Autoencoder (TCN)?
- **Evidence-Based Answer:** app/tcn_model.py implements a Causal Dilated 1D Convolutional Autoencoder. It reconstructs multi-channel temporal windows of healthy baseline telemetry. When unmodeled, out-of-distribution anomalies occur, the reconstruction error (L2 norm) spikes, providing unsupervised anomaly detection without requiring prior fault labeling.

#### Q26: How do you handle extreme class imbalance between Healthy (90%) and Critical (2%) flight states?
- **Evidence-Based Answer:** We employ cost-sensitive class weighting (class_weight='balanced'), stratified grouping, and focal loss penalties on critical transitions, ensuring **96.5% Critical Fault Recall** and a **0.0% Critical-to-Normal false dismissal rate**.

#### Q27: What is the detection delay of your AI diagnostic pipeline?
- **Evidence-Based Answer:** Sensor anomalies are flagged within **1 to 3 time steps (100–300 ms)**. Progressive degradation states (Watch/Warning) are confirmed over a 5-step rolling persistence filter to prevent transient false alarms.

#### Q28: Why do you not use SHAP (SHapley Additive exPlanations) for real-time edge explainability?
- **Evidence-Based Answer:** SHAP TreeExplainer requires evaluating thousands of tree permutations per sample, taking 20–100 ms per inference. In an edge node running at 50 Hz, this violates real-time deadlines. Instead, AeroPulse-X uses a **Deterministic Physical Causal Evidence Engine** (app/explainability.py) that ranks |z|-score deviations and thermodynamic coupling scores in <0.01 ms.

#### Q29: What features are most important in your ML model?
- **Evidence-Based Answer:** Permutation feature importance rankings show:
  1. CHT and Water_Temp (Thermal runaway & radiator faults)
  2. Oil_Pressure and Oil_Temp (Lubrication breakdown)
  3. EGT1-4 cylinder spread (Combustion misfire & injector degradation)
  4. Battery_Voltage and Alternator_Temp (Electrical bus decay).

#### Q30: What is your model's False Negative Rate for critical catastrophic failures?
- **Evidence-Based Answer:** On our holdout evaluation partition (36,000 samples), the Critical Fault False Negative Rate is **3.5% (all misclassified as Warning, with 0 samples misclassified as Normal)**.

### PART 4 — Embedded Systems, Hardware & RUL Prognostics (Questions 31 to 40)

#### Q31: What is the Virtual ADC, and why did you implement 12-bit quantization?
- **Evidence-Based Answer:** Physical engine transducers emit continuous analog voltages (0.0 - 5.0 V). In real avionics, these are digitized by an Analog-to-Digital Converter. app/virtual_adc.py emulates 12-bit (4096 steps) and 16-bit quantization, voltage clamping, thermal drift, and quantization noise, ensuring downstream ML algorithms are tested against realistic digitized sensor noise rather than idealized floating-point numbers.

#### Q32: Where were your edge latency numbers measured?
- **Evidence-Based Answer:** Latency was benchmarked on a **Desktop Host CPU (AMD64 12-Core, Windows 10, Python 3.11.9)**. The entire Edge Node pipeline executes in **0.018 ms (18.9 microseconds)**. While an embedded profile is configured, physical measurement on an ARM Cortex-A72 Single-Board Computer (e.g. Raspberry Pi CM4) is designated for Phase 2 hardware integration.

#### Q33: How does the Hardware Watchdog and Power Brownout recovery work?
- **Evidence-Based Answer:** app/virtual_power.py models 28V DC avionics bus power. When alternator voltage drops below 18V (brownout), a tiered recovery watchdog triggers heartbeat timeouts, logs system crash dumps, and executes a deterministic soft-reset within 50 ms.

#### Q34: How is Remaining Useful Life (RUL) defined and calculated?
- **Evidence-Based Answer:** RUL is defined as the operating time remaining until the composite engine health index H(t) degrades to the critical failure threshold (H_crit = 0.35). We use a **Single Authoritative Hybrid Path** (app/rul_service.py): in steady-state, it defaults to calibrated Rotax 914 Weibull hazard baseline (TBO = 2,000 h, beta=2.4); once active wear is detected, it projects degradation velocity scaled by mission thermal/altitude stress (RUL = (H - H_crit) / |dH/dt|).

#### Q35: How do you compute the 90% Confidence Uncertainty Bounds for RUL?
- **Evidence-Based Answer:** We apply empirical residual variance scaling:
  [RUL_lower, RUL_upper] = [RUL * (1 - 1.645 * sigma_rel), RUL * (1 + 1.645 * sigma_rel)]
  Relative uncertainty sigma_rel dynamically contracts from 25% during early degradation down to 6% near the failure threshold, achieving **93.4% empirical ground-truth coverage** across 300 test trajectories.

#### Q36: What is the Mean Absolute Error (MAE) of your RUL predictions?
- **Evidence-Based Answer:** **14.2 hours** across the entire degradation lifecycle, and **6.98 hours** in the critical terminal wear phase (RUL < 50 h).

#### Q37: How does mission context (altitude, hot weather) affect RUL?
- **Evidence-Based Answer:** Higher ambient temperature and high-altitude climbs increase thermal stress multiplier kappa_mission. Operating continuously at 100% throttle in 45 C ambient conditions increases wear velocity by 1.85x, reducing projected RUL proportionally.

#### Q38: Can your RUL model predict sudden fatigue fracture (e.g. broken connecting rod)?
- **Evidence-Based Answer:** **No.** Prognostic RUL models track **progressive, continuous degradation modes** (wear, fouling, thermal degradation). Sudden, unmodeled brittle mechanical fractures without prior sensor precursor signatures cannot be forecasted by trend extrapolation.

#### Q39: What is the Prognostic Horizon of your system?
- **Evidence-Based Answer:** Using the standard ISO/IEEE prognostic metric with bounds alpha = 0.20 and confidence lambda = 0.50, the system achieves stable prognostic convergence at 78% of the component degradation lifespan.

#### Q40: How would you validate RUL on real physical engines?
- **Evidence-Based Answer:** By conducting **Accelerated Life Testing (ALT)** on an instrumented dynamometer test cell, running engines under elevated cyclic thermal and mechanical loads until components reach overhaul wear limits.

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
