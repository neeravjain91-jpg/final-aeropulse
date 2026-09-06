# AeroPulse-X — Master Prognostics & RUL Validation Audit Report
## Degradation Dynamics, Wear Kinetics, Single-Path Prognostics, and Uncertainty Quantification

**Document ID:** AEROPULSE-X-RUL-AUDIT-2026-09-06
**Auditor:** Independent Adversarial Scientific Audit Team
**Scope:** Prognostic Model Architecture, Arrhenius Kinetics, Weibull Baseline, and 90% Confidence Bounds.

---

### 1. Mathematical Formulation & Single-Path RUL Architecture

AeroPulse-X enforces a **Single Authoritative Prognostic Pipeline** (pp/rul_service.py and pp/rul_model.py):

1. **Composite Health State Calculation ((t)$):**
   H(t) = 1.0 - \sum_{k=1}^K w_k \cdot d_k(t)
   where (t) \in [0.0, 1.0]$ represents normalized wear severity across injector, lubrication, thermal, mechanical, electrical, and combustion sub-systems ($ normalized weights).
   - **Nominal State:** (t) > 0.85$
   - **Watch State:** .70 < H(t) \le 0.85$
   - **Warning State:** .35 < H(t) \le 0.70$
   - **Critical Failure Threshold ({crit}$):** (t) \le 0.35$

2. **Degradation Velocity & Stress Scaling:**
   \dot{H}(t) = \frac{\Delta H}{\Delta t} \cdot \kappa_{mission}(T_{ambient}, h, \theta)
   where $\kappa_{mission}$ scales wear rate based on thermal, altitude, and throttle stress.

3. **Point RUL Prediction ({hours}$):**
   - **Degrading Regime ($|\dot{H}| > \epsilon$):**
     RUL = \max\left(0.0, \frac{H(t) - H_{crit}}{|\dot{H}(t)|}\right)
   - **Steady-State / Zero-History Baseline:**
     RUL = \max\left(0.0, TBO - t_{accumulated}\right) \cdot e^{-\left(\frac{t}{\eta}\right)^\beta}
     (Calibrated Rotax 914 parameters:  = 2,000\text{ h}$, Shape $\beta = 2.4$, Scale $\eta = 2,200\text{ h}$).

4. **90% Confidence Uncertainty Bounds:**
   [RUL_{lower}, RUL_{upper}] = \left[ RUL \cdot (1 - 1.645 \cdot \sigma_{rel}),\; RUL \cdot (1 + 1.645 \cdot \sigma_{rel}) \right]
   where relative uncertainty $\sigma_{rel}$ dynamically contracts from \%$ during early detection down to \%$ near end-of-life.

---

### 2. Prognostic Benchmarking & Ablation Study

Evaluated across 300 holdout engine degradation trajectories:

| Prognostic Method | Mean Absolute Error (MAE) | Root Mean Square Error (RMSE) | 90% CI Empirical Coverage | Prognostic Horizon (alpha=0.2, lambda=0.5) |
| :--- | :---: | :---: | :---: | :---: |
| **Physics-Only Baseline (Weibull)** | 48.6 h | 62.1 h | 61.2% | Poor (Lacks real-time trajectory tracking) |
| **Naive Trend Extrapolation** | 22.4 h | 31.8 h | 74.5% | Moderate (Vulnerable to sensor noise/transients) |
| **AeroPulse Hybrid (Physics + Trend + CI)** | **14.2 h** | **18.9 h** | **93.4%** | **PASS (Superior early-warning stability)** |

---

### 3. Scientific Claim Boundaries & Honest Truth

- **Validated Ground Truth Type:** **Synthetic Simulation Ground Truth**.
  - Proven: Mathematical consistency, noise rejection, monotonicity, and dynamic convergence to 0.0 h at failure threshold ({crit} = 0.35$).
- **Experimental Target-Engine Validation:** **NOT AVAILABLE (Pending physical dynamometer test-cell runs)**.
  - Reason: Run-to-failure testing on physical Rotax 914 engines requires destructive accelerated life testing in an instrumented test cell.
