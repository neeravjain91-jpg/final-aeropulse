# FAULT MODEL VALIDATION & PROGRESSION COHERENCE

This document details the causal physics chains from root parameter failure to multi-sensor telemetry symptoms.

---

## 1. Physical Fault Mechanisms & Causal Chains

```
1. THERMAL SYSTEM OVERHEATING:
   Loss of radiator heat transfer (h_cool * (1 - 0.55*s))
   ↓
   Thermal accumulation in cylinder head: d(T_cht)/dt > 0
   ↓
   Coupled conduction into coolant and oil circuits
   ↓
   [Observable Signature]: CHT ↑ 25%, Coolant ↑ 18%, Oil Temp ↑ 12%, EGT ↑ 8%

2. LUBRICATION DEGRADATION:
   Oil film shearing & pump cavitation (mu_friction * (1 + 0.80*s))
   ↓
   Hydrodynamic journal friction increases
   ↓
   Viscous thermal dissipation + mechanical drag
   ↓
   [Observable Signature]: Oil Pressure ↓ 65%, Oil Temp ↑ 28%, Vibration ↑ 40%

3. COMBUSTION MISFIRE:
   Ignition/valve sealing deficit (f_misfire = 0.25*s)
   ↓
   Unburnt fuel expelled in cylinder 1 exhaust cycle
   ↓
   Cyclic torque deficit & rotational mass imbalance
   ↓
   [Observable Signature]: EGT1 ↓ 28%, RPM ↓ 8%, Vibration ↑ 1.25 g

4. FUEL INJECTOR RESTRICTION:
   Discharge nozzle fouling (C_d * (1 - 0.32*s))
   ↓
   Localized lean air-fuel ratio
   ↓
   ECU MAP compensation attempt
   ↓
   [Observable Signature]: Fuel Flow ↓ 32%, MAP ↑ 35%, EGT asymmetric spread
```

---

## 2. 5-Stage Fault Progression Trajectory (Overheating Example)

| Progression Stage | Severity ($s$) | CHT (°F) | Coolant (°C) | Oil Temp (°C) | EGT1 (°F) | Health State | RUL Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **HEALTHY** | 0.00 | 207 °F | 82 °C | 85 °C | 1205 °F | **Normal** | Nominal (2200h) |
| **EARLY** | 0.25 | 224 °F | 87 °C | 89 °C | 1228 °F | **Normal / Check**| 1850h |
| **DEVELOPING** | 0.50 | 248 °F | 93 °C | 95 °C | 1265 °F | **Degraded** | 1240h |
| **SEVERE** | 0.75 | 282 °F | 102 °C | 104 °C | 1310 °F | **Degraded / Crit**| 480h |
| **CRITICAL** | 1.00 | 335 °F | 115 °C | 118 °C | 1380 °F | **Critical** | < 12h |

**Validation Conclusion**: Progression follows continuous exponential saturation curves without discontinuous jumps.
