# AEROPULSE-X PHYSICS RESIDUAL GENERATION METHODOLOGY
## Mathematical Formulation of Physics-Expected State, Z-Score Normalization & Innovation Tracking

**Document Version**: 2.0.0-SIH  
**Release Date**: August 26, 2026  
**Module**: `app/digital_twin.py` & `app/engine_model.py`

---

## 1. Principles of Physics-Informed Residual Tracking
In AeroPulse-X, a **Physics Residual** represents the difference between a real-time sensor measurement and the deterministic prediction produced by the thermodynamic physics Digital Twin operating under identical environmental conditions (altitude, ambient temperature, airspeed, throttle).

$$\text{Residual}_i(t) = y_{i,\text{measured}}(t) - \hat{y}_{i,\text{physics}}(t, h, T_{\text{amb}}, \theta, N)$$

```
                                  Telemetry y_meas(t)
                                           |
                                           v
Environment & Control (h, T_amb, RPM, θ) -> [ Physics Digital Twin ] -> y_expected(t)
                                                                             |
                                                                             v
                                            Residual = y_meas - y_expected  <+
                                                           |
                                                           v
                                            Z_Score = Residual / σ_ref
                                                           |
                                                           v
                                         [ Sensor Trust & Diagnostics ]
```

---

## 2. Mathematical Normalization (Robust Z-Scores)
Raw residuals have different units and natural variances (e.g. CHT in °C vs Oil Pressure in PSI). To enable cross-subsystem diagnostics, residuals are normalized into scale-invariant robust Z-scores:

$$Z_i(t) = \frac{y_{i,\text{measured}}(t) - \hat{y}_{i,\text{physics}}(t)}{\sigma_{i,\text{ref}}(\text{Operating\_State})}$$

where $\sigma_{i,\text{ref}}$ is the standard deviation under nominal healthy conditions for the active flight state (`CRUISE`, `CRUISE_LOW`, `HIGH`).

### Operational Decision Thresholds:
- $|Z_i| \le 1.5$: **Nominal** (Sensor within 87% statistical band).
- $1.5 < |Z_i| \le 2.8$: **Watch / Elevated Deviation** (Early onset drift).
- $2.8 < |Z_i| \le 4.5$: **Warning / Serious Anomaly** (Actionable subsystem fault).
- $|Z_i| > 4.5$: **Critical / Immediate Hazard** (Severe failure or structural excursion).

---

## 3. Residual Innovation Trend Tracking
To distinguish rapid transients from progressive mechanical wear, the residual rate of change is tracked over a moving window of $W = 10$ frames (~2.5 seconds):

$$\Delta Z_i(t) = Z_i(t) - Z_i(t-1)$$
$$\text{Trend}_i(t) = \frac{1}{W} \sum_{k=0}^{W-1} \Delta Z_i(t-k)$$

---

## 4. Multi-Channel Residual Root-Mean-Square (RMS)
The aggregate engine health residual is quantified as:

$$\text{RMS}_{\text{residual}}(t) = \sqrt{\frac{1}{K} \sum_{i=1}^{K} Z_i(t)^2}$$

If $\text{RMS}_{\text{residual}} \ge 2.0$, an unsupervised anomaly trigger is asserted in parallel with the machine learning diagnostic classifier.
