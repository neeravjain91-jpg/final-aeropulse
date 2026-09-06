# PHYSICS PARAMETER PROVENANCE & CLASSIFICATION

Every parameter in the AeroPulse-X digital twin is classified into one of the following authoritative tiers:
- **REAL_MEASURED**: Extracted directly from empirical physical sensors.
- **LITERATURE**: Sourced from published aerospace/combustion engineering textbooks.
- **CALIBRATED**: Statistically tuned against empirical flight datasets.
- **DERIVED**: Analytically computed from first-principles conservation laws.
- **ASSUMED**: Engineering baseline estimate requiring dynamometer ground truth.
- **SYNTHETIC_DEMO**: Parametrically generated for interactive fault demonstration.

---

## Comprehensive Parameter Inventory

| Parameter Name | Symbol / Code | Value | Tier / Source | Confidence Level | Scientific Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Displacement** | $V_d$ | 1.352 L | LITERATURE | HIGH | Standard 4-cylinder aero-piston displacement. |
| **Compression Ratio** | $r_c$ | 9.0 : 1 | LITERATURE | HIGH | Standard aviation gasoline (Avgas 100LL / Mogas). |
| **Rated RPM** | $N_0$ | 3000 RPM | LITERATURE | HIGH | Typical continuous cruise speed for geared UAV engines. |
| **Max RPM** | $N_{\max}$ | 5800 RPM | LITERATURE | HIGH | Redline RPM before propeller governor cavitation. |
| **Base Power** | $P_{\text{base}}$ | 85.0 kW | LITERATURE | HIGH | Representative 115 hp aero-propulsion power envelope. |
| **Air-Fuel Ratio** | $AFR_{\text{stoich}}$ | 14.7 | LITERATURE | HIGH | Stoichiometric gasoline-air mass ratio. |
| **Fuel Density** | $\rho_{\text{fuel}}$ | 0.72 kg/L | LITERATURE | HIGH | Aviation Gasoline (ASTM D910 standard). |
| **Baseline Volumetric Eff** | $\eta_{v0}$ | 0.88 | CALIBRATED | MODERATE | Calibrated against ACES flight intake mass balance. |
| **Thermal Capacitance** | $C_{\text{th}}$ | 12.5 kJ/K | CALIBRATED | MODERATE | Tuned to thermal time constant of aluminum cylinder heads. |
| **Cooling Coeff** | $h_{\text{cool}}$ | 0.18 kW/K | CALIBRATED | MODERATE | Tuned against airspeed and ambient convective cooling. |
| **Friction Power Base** | $P_{\text{fric0}}$ | 6.5 kW | CALIBRATED | MODERATE | Bishop friction model baseline for 4-cylinder engines. |
| **Oil Viscosity Index** | $\nu_0, k_\nu$ | 1.0, 0.0055 | LITERATURE | HIGH | SAE 15W-50 semi-synthetic aero engine oil behavior. |
| **Weibull Shape Factor** | $\beta$ | 2.4 | ASSUMED | LOW (DEMO) | Representative mechanical wear-out mode prior. |
| **Weibull Scale Factor** | $\eta$ | 2200.0 hrs | ASSUMED | LOW (DEMO) | Typical TBO (Time Between Overhaul) prior. |
| **Overheating Multiplier**| $h_{\text{factor}}$ | 1.0 - 0.55*s | SYNTHETIC_DEMO| MODERATE | Parametric heat rejection reduction function. |
| **Misfire Fraction** | $f_{\text{misfire}}$ | 0.25*s | SYNTHETIC_DEMO| HIGH | Cyclic torque and unburned exhaust loss function. |
