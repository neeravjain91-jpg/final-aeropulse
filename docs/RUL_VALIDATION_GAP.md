# RUL PROGNOSTICS METHODOLOGY & VALIDATION GAP REPORT

**Scientific Status**: **PROGNOSTIC DEMONSTRATOR / SIMULATION** (NOT CERTIFIED FLIGHT PROGNOSTICATOR).

---

## 1. Theoretical RUL Formulation
$$\text{RUL}(t) = \eta_{\text{prior}} \cdot \left(-\ln(H(t))\right)^{1/\beta} \cdot \frac{1}{M_{\text{stress}}(t)}$$
Where:
- $\beta = 2.4$ (Weibull shape factor representing accelerated mechanical wear-out).
- $\eta_{\text{prior}} = 2200.0\text{ hours}$ (Nominal Time Between Overhaul).
- $H(t) \in [0, 1]$ (Estimated component health index).
- $M_{\text{stress}}(t) = 1.0 + 0.4 \cdot \left(\frac{N}{N_0} - 1\right) + 0.3 \cdot \left(\frac{T_{\text{oil}}}{85} - 1\right)$ (Mission operating stress multiplier).

---

## 2. Statistical Uncertainty Interval
$$[\text{RUL}_{\text{lower}}, \text{RUL}_{\text{upper}}] = [\text{RUL} \cdot (1 - 1.96 \cdot \sigma_{\text{deg}}), \; \text{RUL} \cdot (1 + 1.96 \cdot \sigma_{\text{deg}})]$$

---

## 3. Ground Truth Data Gap Analysis
- **Current Data Limitation**: The NASA ACES dataset contains 14 discrete flight logs ranging from 1 to 5 hours each. No single engine was flown continuously to structural or mechanical failure.
- **Why RUL Cannot be Claimed as Fully Validated**: Without empirical run-to-failure continuous records (such as C-MAPSS or dyno failure testing), ground truth remaining life $RUL^* = t_{\text{failure}} - t$ is physically unobservable.
- **Required Physical Experiment**: A 500-hour continuous dynamometer accelerated life test (ALT) under controlled thermal/lubrication stress is required to calibrate $\beta$ and $\eta$.
