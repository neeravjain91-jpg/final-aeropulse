# NEXT PHASE BASELINE AUDIT

**Recorded Git Tag / Baseline Commit**: `backup-before-temporal-ai-2026-08-26` / `9d28021`  
**Dataset Reference**: NASA ACES General Aviation Piston Flight Telemetry (173,878 rows across 14 flight missions)  
**Strict Evaluation Methodology**: GroupShuffleSplit (80% Train on 11 flights, 20% Test on 3 unseen flights: `aces1am_2002_191`, `aces1am_2002_225`, `aces1am_2002_235`)

---

## 1. Verified Baseline Numbers on Unseen Test Missions

> [!IMPORTANT]
> The primary scientific performance claim is **89.19% held-out test accuracy** (single-sample static benchmark on 3 unseen flights, 30,061 rows). The 96.18% figure is an unweighted mean across all 14 missions including training logs, and is strictly used only as supporting context for cross-flight stability.

| Metric | Raw Telemetry Baseline (Model A) | Physics + Residual Baseline (Model B) | Calibrated Physics + Slopes (Model E) |
| :--- | :--- | :--- | :--- |
| **Held-Out Test Accuracy** | **87.41%** (or 89.19% with full features) | **87.41%** | **88.29%** |
| **Balanced Accuracy** | 81.69% | 81.69% | **83.60%** (+1.91%) |
| **Macro F1-Score** | 81.88% | 81.88% | **83.78%** (+1.90%) |
| **Critical Class Recall** | 76.73% | 76.73% | **81.44%** (+4.71%) |
| **Critical Class F1-Score** | 77.25% | 77.25% | **80.12%** (+2.87%) |
| **Critical False Negative Rate (FNR)** | 23.27% | 23.27% | **18.56%** (-4.71%) |

---

## 2. Uncalibrated Physics Model Baseline Discrepancies

| Telemetry Channel | Ground Truth Mean | Uncalibrated Pred Mean | Baseline MAE | Baseline MAPE (%) | Baseline Bias |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Engine_RPM** | 4544.0 RPM | 4544.0 RPM | 0.00 RPM | 0.00% | 0.00 RPM |
| **EGT1 (Cylinder 1)** | 1281.98 °F | 1180.00 °F | 33.45 °F | 9.22% | -101.98 °F |
| **EGT2 (Cylinder 2)** | 1301.45 °F | 1180.00 °F | 40.45 °F | 10.23% | -121.45 °F |
| **EGT3 (Cylinder 3)** | 1294.96 °F | 1180.00 °F | 48.32 °F | 9.36% | -114.96 °F |
| **CHT (Cylinder Head Temp)** | 202.51 °F | 73.93 °F | 128.58 °F | **63.69%** | -128.58 °F |
| **Fuel Flow** | 34.86 L/h | 28.68 L/h | 18.95 L/h | **102.41%** | -6.18 L/h |
| **Oil Temperature** | 159.80 °F | 85.00 °F | 74.80 °F | **50.10%** | -74.80 °F |
| **Oil Pressure** | 61.00 PSI | 28.10 PSI | 32.90 PSI | **52.84%** | -32.90 PSI |
| **EFI Water Temp** | 177.80 °F | 86.23 °F | 91.57 °F | **51.96%** | -91.57 °F |
| **MAP Injector** | 31.03 inHg | 35.62 inHg | 11.05 inHg | **54.50%** | +4.59 inHg |
| **Battery Voltage** | 27.60 V | 27.81 V | 0.21 V | **0.57%** | +0.21 V |
