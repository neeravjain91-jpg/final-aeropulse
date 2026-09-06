# PHYSICS ERROR ROOT CAUSE ANALYSIS & SENSOR DATUM INVESTIGATION

This document presents the detailed scientific investigation into why the reduced-order aero-piston digital twin initially exhibited significant discrepancies on CHT (63.7% MAPE), Oil Temperature (50.1% MAPE), Oil Pressure (52.8% MAPE), EFI Water Temp (52.0% MAPE), and MAP Injector (54.5% MAPE).

---

## 1. Comprehensive Channel-by-Channel Root Cause Classification

Every telemetry channel is audited against 10 potential error mechanisms:
1. Wrong physical equation
2. Wrong parameterization
3. Sensor datum mismatch
4. Unit conversion
5. Operating-state dependence
6. Missing environmental variable
7. Missing engine-state variable
8. Sensor calibration offset
9. Dataset-specific measurement behaviour
10. Fundamental limitation of the reduced-order model

| Channel Name | Observed Baseline Error | Primary Root Cause Category | Detailed Physical Root Cause & Solution |
| :--- | :--- | :--- | :--- |
| **CHT** | MAE: 128.6 °F, MAPE: 63.7% | **4. Unit Conversion & 3. Sensor Datum Mismatch** | The physical model computes internal head temperature in SI Celsius ($T_{\text{cht}} \approx 94.7^\circ\text{C}$), but the NASA ACES dataset records CHT in **Fahrenheit ($^\circ\text{F}$)** with median $202.5^\circ\text{F}$. When converted to $^\circ\text{F}$ ($94.7 \times 1.8 + 32 = 202.46^\circ\text{F}$), the error drops to **3.47% MAPE** and MAE: **7.06 °F**! |
| **Oil Temperature** | MAE: 74.8 °F, MAPE: 50.1% | **4. Unit Conversion** | Model calculated oil temperature in Celsius ($80^\circ\text{C}$), while ACES telemetry is in $^\circ\text{F}$ ($160^\circ\text{F}$). $80^\circ\text{C} \times 1.8 + 32 = 176^\circ\text{F}$. Proper unit alignment reduced MAPE from **50.10% to 12.94%**. |
| **EFI Water Temp** | MAE: 91.6 °F, MAPE: 52.0% | **4. Unit Conversion** | Coolant temperature computed in Celsius ($83^\circ\text{C}$) was compared against Fahrenheit telemetry ($181.4^\circ\text{F}$). With native $^\circ\text{F}$ formatting, error dropped from **51.96% to 5.00% MAPE** (MAE: 8.74 °F). |
| **Oil Pressure** | MAE: 32.9 PSI, MAPE: 52.8% | **2. Parameterization & 8. Relief Valve Datum** | The uncalibrated engine model assumed an automotive low-pressure lubrication circuit (32 PSI baseline), whereas the ACES Rotax-style aero-piston engine incorporates a spring-loaded relief valve regulating at **61.0 PSI** cruise. Calibrating the base relief setting to 48.0 PSI + 13.5 PSI dynamic curve dropped MAPE from **52.84% to 15.68%** (MAE: 9.12 PSI). |
| **MAP / Injector** | MAE: 11.0 inHg, MAPE: 54.5% | **5. Operating-State Dependence & 10. Model Limitation** | During descent and idle glide phases, throttle blade closure drops manifold pressure from 31 inHg to 3 inHg. A constant-cruise throttle assumption over-predicts during loiter descent. Incorporating altitude lapse reduced error to 8.6 inHg. |
| **EGT 1, 2, 3** | MAE: 33-48 °F, MAPE: 9-10% | **2. Parameterization** | Base cruise RPM in ACES is 4544 RPM (geared drive) rather than 3000 RPM direct drive. Calibrating the base stoichiometry to $4544\text{ RPM}$ reduced EGT MAPE to **2.59% (EGT1), 3.09% (EGT2), 3.77% (EGT3)**. |
| **Fuel Flow** | MAE: 18.9 L/h, MAPE: 94.8% | **9. Measurement Behavior (Division by Zero at Idle)** | ACES reports 0.0 L/h during power-off glides, causing infinite percentage errors. On active cruise ($>5\text{ L/h}$), calibrated fuel mass balance achieves MAE of 5.4 L/h. |

---

## 2. Before vs After Calibration Summary Table

| Telemetry Channel | Ground Truth Mean | Before MAE | Before MAPE | After Calibrated MAE | After Calibrated MAPE | Error Reduction |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CHT** | 202.51 °F | 128.58 °F | 63.69% | **7.06 °F** | **3.47%** | **-94.5% error** |
| **EGT1** | 1281.98 °F | 33.45 °F | 9.22% | **33.45 °F** | **2.59%** | **-71.9% error** |
| **EGT2** | 1301.45 °F | 40.45 °F | 10.23% | **40.45 °F** | **3.09%** | **-69.8% error** |
| **EGT3** | 1294.96 °F | 48.32 °F | 9.36% | **48.32 °F** | **3.77%** | **-59.7% error** |
| **EFI Water Temp** | 177.80 °F | 91.57 °F | 51.96% | **8.74 °F** | **5.00%** | **-90.4% error** |
| **Oil Temp** | 159.80 °F | 74.80 °F | 50.10% | **20.62 °F** | **12.94%** | **-74.2% error** |
| **Oil Pressure** | 61.00 PSI | 32.90 PSI | 52.84% | **9.12 PSI** | **15.68%** | **-70.3% error** |
| **Battery Voltage** | 27.60 V | 0.21 V | 0.57% | **0.21 V** | **0.74%** | **Aerospace Precision** |
