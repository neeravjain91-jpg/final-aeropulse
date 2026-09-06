# Data Generation Engine & Kinetic Models

## 1. Thermodynamic & Kinetic Foundations
The `VirtualDataLabEngine` generates synthetic time-series using first-principles thermodynamic, kinetic, and virtual hardware models.

### 1.1 First-Principles Engine Physics
- **Intake Manifold Pressure ($P_{\text{MAP}}$)**:
  $$P_{\text{MAP}} = P_{\text{amb}} \cdot (0.35 + 0.65 \cdot \theta) \cdot (0.60 + 0.40 \cdot \sigma)$$
- **Volumetric Efficiency ($\eta_v$)**:
  $$\eta_v = \left(0.84 + 0.12 \cdot \theta - 0.05 \left(\frac{N}{N_0} - 1\right)^2\right) \cdot \sqrt{\sigma}$$
- **Brake Power ($P_{\text{brake}}$)**:
  $$P_{\text{brake}} = P_{\text{ind}} - P_{\text{friction}} = \eta_{\text{thermal}} \cdot \dot{m}_f \cdot \text{LHV} - (P_{\text{fric0}} + k_f N^{1.6})$$

---

## 2. Progressive Degradation Kinetics (7 Failure Modes)
Continuous wear severity $s(t) \in [0, 1]$ evolves according to:
$$s(t) = \min\left(1.0, k_{\text{wear}} \cdot (t - t_{\text{onset}})^p\right), \quad t > t_{\text{onset}}$$
$$H(t) = \max\left(0.0, 100.0 - 65.0 \cdot s(t)\right)$$
Critical failure occurs deterministically when $H(t) = 35.0$.

### 2.1 Causal Physical Couplings
1. **Thermal Degradation**: Heat rejection deficit causes non-linear elevation of CHT ($+24\%$), coolant temp ($+18\%$), and oil temp ($+14\%$).
2. **Lubrication Degradation**: Oil film thinning reduces oil pressure (down to $50\%$), increases friction, and raises vibration ($+45\%$).
3. **Mechanical Bearing Wear**: Spalling increases tri-axial vibration ($+95\%$), induces speed flutter, and drops brake power ($-15\%$).
4. **Injector Fouling**: Reduced fuel delivery drops fuel flow ($-22\%$), increases MAP ($+25\%$), and introduces EGT cylinder asymmetry.
5. **Combustion Misfire**: Partial combustion failure drops affected cylinder EGT ($-28\%$) and injects severe torsional vibration ($+1.30\text{ g}$).
6. **Electrical Alternator Decay**: Diode bridge wear degrades bus voltage (sag to $16\text{ V}$) and elevates alternator stator temperature ($+28\%$).
7. **Compound Degradation**: Simultaneous thermal-lubrication-mechanical degradation representing cascading end-of-life failures.

---

## 3. Transducer Sensor Fault Isolation
Sensor faults corrupt only the reported transducer channel without modifying the underlying engine state:
- **Bias**: $y(t) = x(t) + \delta_{\text{bias}}$
- **Linear Drift**: $y(t) = x(t) + \alpha \cdot (t - t_0)$
- **Gaussian Noise**: $y(t) = x(t) + \mathcal{N}(0, \sigma^2)$
- **Saturation**: $y(t) = \min(y_{\max}, x(t))$
- **Stuck-At**: $y(t) = x(t_{\text{fault}})$
- **Dropout / Intermittent**: $y(t) = 0.0$ or missing packets.

When a sensor fault is active, `sensor_trust` drops, but `health_index` remains high, validating the Digital Twin's residual diagnostic capability.
