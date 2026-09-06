# BASELINE BEFORE SCIENTIFIC VALIDATION & HARDENING

**Recorded Git Tag / Commit**: `backup-before-hardening-2026-08-26` / `3ec6db7`  
**Dataset Reference**: NASA ACES General Aviation Piston Flight Telemetry (173,878 rows across 14 flight missions)  
**Evaluation Methodology**: GroupShuffleSplit (80% Train on 11 flights, 20% Test on 3 unseen flights: `aces1am_2002_191`, `aces1am_2002_225`, `aces1am_2002_235`)

---

## 1. Diagnostic ML Performance Baseline (HGB-PRO)

| Metric | Raw Baseline Value |
| :--- | :--- |
| **Overall Accuracy** | 89.19% |
| **Balanced Accuracy** | 87.67% |
| **Macro F1-Score** | 85.18% |
| **Critical Class Recall** | 91.31% (620 / 679) |
| **Critical Class F1-Score** | 79.74% |
| **Critical False Negative Rate (FNR)** | 8.69% (59 / 679) |
| **Flight Group K-Fold (5 folds)** | 89.26% +/- 4.05% |

---

## 2. Physics Model Baseline Errors (Uncalibrated Reduced-Order Engine)

| Telemetry Channel | Baseline MAE | Baseline RMSE | MAPE (%) | Baseline Bias |
| :--- | :--- | :--- | :--- | :--- |
| **Engine_RPM** | 0.00 RPM | 0.00 RPM | 0.0% | 0.00 RPM |
| **EGT1 (Cylinder 1)** | 61.65 °F | 76.55 °F | 4.8% | -60.25 °F |
| **EGT2 (Cylinder 2)** | 50.27 °F | 62.09 °F | 3.9% | -36.05 °F |
| **EGT3 (Cylinder 3)** | 67.31 °F | 84.44 °F | 5.3% | -63.26 °F |
| **CHT (Cylinder Head Temp)** | 133.37 °F | 138.49 °F | 65.5% | -133.37 °F |
| **Fuel Flow** | 15.72 L/h | 16.79 L/h | 82.8% | +6.28 L/h |
| **Oil Temperature** | 71.83 °C | 76.13 °C | 40.0% | +71.83 °C |
| **Oil Pressure** | 20.22 PSI | 22.19 PSI | 34.6% | -20.20 PSI |
| **Battery Voltage** | 0.40 V | 0.43 V | 1.4% | -0.37 V |
| **MAP (Manifold Pressure)** | 8.64 inHg | 9.00 inHg | 33.8% | +5.78 inHg |

---

## 3. Baseline RUL & Mission Risk Status

- **RUL Ground Truth**: UNAVAILABLE in target domain (continuous run-to-failure records absent in NASA ACES flight dataset).
- **RUL Status**: Designated as **PROGNOSTIC DEMONSTRATOR / SIMULATION** using nominal Weibull prior (beta=2.4, eta=2200 hrs) with mission-stress multipliers.
- **Mission Risk Formula**: Heuristic composite of route duration, cruising altitude density deficit, and degradation severity.
