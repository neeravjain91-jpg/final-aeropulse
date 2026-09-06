# PHYSICS EQUATION AUDIT: REDUCED-ORDER AERO-PISTON MODEL

This audit reviews every mathematical relationship in `app/engine_model.py` and `app/engine_config.py`.

---

## 1. Atmospheric Barometric Lapse & Air Density
- **Equation**: 
  $$T(h) = T_{\text{amb}} - 0.0065 \cdot h_{\text{m}}, \quad P(h) = P_0 \cdot \left(1 - \frac{0.0065 \cdot h_{\text{m}}}{T_{\text{amb}} + 273.15}\right)^{5.25588}$$
  $$\rho(h) = \frac{P(h)}{R_{\text{spec}} \cdot T(h)}, \quad \sigma = \frac{\rho(h)}{\rho_0}$$
- **Type**: First-Principles (ISA Standard Atmosphere / Ideal Gas Law).
- **Inputs**: Geopotential Altitude $h$ (ft), Ambient Temperature $T_{\text{amb}}$ (°C).
- **Outputs**: Pressure $P$ (kPa), Density $\rho$ (kg/m³), Relative Density $\sigma$.
- **Operating Range**: Altitude: 0 to 45,000 ft; Ambient Temp: -50°C to +55°C.
- **Numerical Stability**: Bounded $\sigma \in [0.15, 1.40]$ with singularity guards.
- **Validation Status**: Formally Validated against ICAO Doc 7488/3 Standard Atmosphere tables.

---

## 2. Volumetric Efficiency & Intake Air Mass Flow
- **Equation**:
  $$\eta_v = \eta_{v0} \cdot \left(0.55 + 0.45 \cdot \theta^{0.85}\right) \cdot \sqrt{\sigma} \cdot \left(1.0 - 0.12 \cdot \left(\frac{N - N_0}{N_{\max}}\right)^2\right)$$
  $$\dot{m}_a = \left(\frac{N}{120}\right) \cdot \left(\frac{V_d}{1000}\right) \cdot \rho_{\text{amb}} \cdot \eta_v$$
- **Type**: Semi-Empirical (Taylor & Heywood internal combustion intake flow formulation).
- **Inputs**: RPM $N$, Throttle fraction $\theta \in [0, 1]$, Relative Density $\sigma$, Displacement $V_d$ (L).
- **Outputs**: Volumetric Efficiency $\eta_v$, Air Mass Flow $\dot{m}_a$ (kg/s).
- **Assumptions**: 4-stroke cycle intake stroke frequency ($N/120$ rev/s per cylinder pair).
- **Validation Status**: Calibrated against generic 1.35L - 2.0L naturally aspirated piston engine dyno curves.

---

## 3. Fuel Mass Flow & Stoichiometric Metering
- **Equation**:
  $$\dot{m}_f = \left(\frac{\dot{m}_a}{AFR_{\text{stoich}}}\right) \cdot \text{Ratio}_{\text{inj}} \cdot 1000 \quad (\text{g/s})$$
- **Type**: First-Principles Conservation of Mass.
- **Inputs**: Air mass flow $\dot{m}_a$ (kg/s), Stoichiometric Air-Fuel Ratio $AFR = 14.7$, Injection multiplier.
- **Outputs**: Fuel Flow (g/s and L/h conversion $\dot{V}_f = \frac{\dot{m}_f \cdot 3.6}{\rho_{\text{fuel}}}$).
- **Assumptions**: Homogeneous charge stoichiometric combustion with lambda=1.0 at nominal cruise.

---

## 4. Indicated Power, Friction Losses & Brake Power
- **Equation**:
  $$P_{\text{ind}} = P_{\text{base}} \cdot \left(\frac{\text{MAP}}{101.325}\right) \cdot \eta_v \cdot \left(\frac{N}{N_0}\right) \cdot 1.12 \cdot (1 - f_{\text{misfire}})$$
  $$P_{\text{fric}} = \left(P_{\text{fric0}} + 8.5 \cdot \left(\frac{N}{N_{\max}}\right)^{1.8}\right) \cdot \mu_{\text{fric}}$$
  $$P_{\text{brake}} = \max(3.0, P_{\text{ind}} - P_{\text{fric}})$$
- **Type**: Semi-Empirical (Bishop-Heywood friction scaling).
- **Inputs**: Indicated base power $P_{\text{base}}$ (kW), Friction multiplier $\mu_{\text{fric}}$, Misfire fraction $f_{\text{misfire}}$.
- **Outputs**: Brake Power $P_{\text{brake}}$ (kW), Thermal efficiency $\eta_{\text{th}}$.
- **Operating Range**: $N \in [800, 6000]\text{ RPM}$, $P_{\text{brake}} \in [3.0, 150.0]\text{ kW}$.

---

## 5. First-Principles Thermal System (CHT, Coolant, Oil)
- **Equation**:
  $$\dot{Q}_{\text{in}} = P_{\text{ind}} \cdot \left(\frac{1 - \eta_{\text{th}}}{\eta_{\text{th}}}\right), \quad \dot{Q}_{\text{cool}} = h_{\text{cool}} \cdot A \cdot (T_{\text{cht}} - T_{\text{amb}})$$
  $$C_{\text{th}} \frac{dT_{\text{cht}}}{dt} = \dot{Q}_{\text{in}} - \dot{Q}_{\text{cool}}$$
- **Type**: First-Principles Lumped Parameter Thermal Network.
- **Inputs**: Indicated thermal rejection $\dot{Q}_{\text{in}}$ (kW), Cooling coefficient $h_{\text{cool}}$, Thermal capacitance $C_{\text{th}}$ (kJ/K).
- **Outputs**: In-cylinder CHT (°C/°F), Coolant temperature (°C), Oil circuit temperature (°C).
- **Assumptions**: Lumped capacitance with constant heat transfer surface area.
