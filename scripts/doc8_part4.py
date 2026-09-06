
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
