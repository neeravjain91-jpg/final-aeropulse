# AEROPULSE-X PHYSICS MODEL AUDIT
## Comprehensive Assessment of Reduced-Order Propulsion Physics & Digital Twin Equations

**Document Version**: 2.0.0-SIH  
**Release Date**: August 26, 2026  
**Module Audited**: \pp/engine_model.py\ & \pp/digital_twin.py\  
**Target Architecture**: 4-Cylinder 4-Stroke Spark-Ignited MALE UAV Aero Piston Engine (Rotax 914 / ACES Class)

---

## 1. Current Model Overview
The baseline AeroPulse-X propulsion physics module implements a reduced-order thermodynamic cycle model calibrated for Medium-Altitude Long-Endurance (MALE) UAV piston engines. It combines:
1. **International Standard Atmosphere (ISA)** equations for barometric pressure, ambient temperature, and air density ratio ($\\sigma = \\rho / \\rho_0$).
2. **Volumetric Efficiency & Intake Flow**: Parameterized by throttle position, RPM ratio, and density ratio.
3. **Otto Cycle Thermal Efficiency**: Based on compression ratio ( = 9.0$) and specific heat ratio ($\\gamma = 1.33$).
4. **Indicated & Brake Power Generation**: Indicated power calculated from air mass flow, with empirical speed-dependent mechanical friction losses.
5. **Sensor-Channel Mapping**: Generates synthetic telemetry for 14 primary UAV engine channels.

---

## 2. Core Equations in Current Implementation

### 2.1 Atmospheric Model (ISA Standard)
\\begin{aligned}
T_{\\text{amb}}(h) &= T_0 - L \\cdot h \\quad (L = 0.0065\\text{ K/m}) \\\\
P_{\\text{amb}}(h) &= P_0 \\cdot \\left(\\frac{T_{\\text{amb}}}{T_0}\\right)^{\\frac{g}{L \\cdot R}} \\\\
\\rho_{\\text{amb}}(h) &= \\frac{P_{\\text{amb}}}{R \\cdot T_{\\text{amb}}} \\\\
\\sigma(h) &= \\frac{\\rho_{\\text{amb}}(h)}{\\rho_0} \\quad (\\rho_0 = 1.225\\text{ kg/m}^3, P_0 = 101.325\\text{ kPa})
\\end{aligned}

### 2.2 Manifold Absolute Pressure (MAP) & Volumetric Efficiency
\\begin{aligned}
\\text{MAP} &= P_0 \\cdot (0.35 + 0.65 \\cdot \\theta) \\cdot (0.60 + 0.40 \\cdot \\sigma) \\\\
\\eta_v &= \\left[0.84 + 0.12 \\cdot \\theta - 0.05 \\cdot \\left(\\frac{N}{N_0} - 1\\right)^2\\right] \\cdot \\sqrt{\\sigma}
\\end{aligned}
where $\\theta \\in [0, 1]$ is throttle, $ is engine RPM, and  = 3000\\text{ RPM}$.

### 2.3 Power & Thermodynamics
\\begin{aligned}
\\dot{m}_{\\text{air,index}} &= \\frac{\\text{MAP}}{P_0} \\cdot \\eta_v \\cdot \\frac{N}{N_0} \\\\
P_{\\text{ind}} &= P_{\\text{base}} \\cdot \\dot{m}_{\\text{air,index}} \\cdot 1.12 \\\\
P_{\\text{fric}} &= 6.5 + 8.5 \\cdot \\left(\\frac{N}{N_{\\max}}\\right)^{1.8} \\\\
P_{\\text{brake}} &= \\max(3.0, P_{\\text{ind}} - P_{\\text{fric}}) \\\\
\\eta_{\\text{th}} &= 0.32 \\cdot \\left(1 - \\frac{1}{r_c^{\\gamma - 1}}\\right) \\cdot (0.85 + 0.15 \\cdot \\theta)
\\end{aligned}

### 2.4 Thermal & Sensor Predictions
\\begin{aligned}
T_{\\text{egt,base}} &= 1180 + 220 \\cdot \\theta + 40 \\cdot \\left(\\frac{h_{\\text{ft}}}{10000}\\right) + 1.2 \\cdot T_{\\text{amb,C}} \\\\
T_{\\text{cht}} &= 195 + 110 \\cdot \\left(\\frac{P_{\\text{ind}}}{P_{\\text{base}}}\\right) + 0.9 \\cdot T_{\\text{amb,C}} + 8.0 \\cdot \\left(\\frac{h_{\\text{ft}}}{10000}\\right) \\\\
T_{\\text{oil}} &= 82 + 18 \\cdot \\left(\\frac{P_{\\text{ind}}}{P_{\\text{base}}}\\right) + 0.38 \\cdot (T_{\\text{amb,C}} - 25) + 3.0 \\cdot \\left(\\frac{h_{\\text{ft}}}{10000}\\right) \\\\
P_{\\text{oil}} &= \\left[32 + 38 \\cdot \\left(\\frac{N}{N_0}\\right)\\right] \\cdot \\max(0.65, 1.0 - 0.005 \\cdot (T_{\\text{oil}} - 85))
\\end{aligned}

---

## 3. Assumptions & Reusable Foundations
- **Strengths Already Present**:
  1. Real-time compute speed ($< 0.01\\text{ ms}$ execution per telemetry step).
  2. Bounded, deterministic numerical behavior across entire flight envelope ($ to ,000\\text{ ft}$, $-20\\text{ \u00b0C}$ to $+55\\text{ \u00b0C}$).
  3. Continuous air density lapse correctly integrated into volumetric efficiency and indicated power.
  4. Non-linear viscosity correction dynamically coupling oil pressure to oil temperature.

---

## 4. Known Limitations & Missing Physics
1. **Static Thermal Equilibrium vs Thermal Mass Lag**: Current CHT and oil temperatures compute instantaneous equilibrium values without thermal inertia ({\\text{th}} \\frac{dT}{dt} = \\dot{Q}_{\\text{in}} - \\dot{Q}_{\\text{out}}$). Real engines take 30–90 seconds to heat up after a step throttle increase.
2. **Fixed Parameter Hardcoding**: Engine displacement (.352\\text{ L}$), compression ratio (.0$), and cooling parameters are embedded directly in class methods rather than being parameterized through an extensible configuration schema.
3. **Simplified Air-Fuel Ratio (AFR) & Stoichiometry**: Fuel flow is calculated from an empirical curve rather than derived from physical mass air flow $\\dot{m}_a$ and combustion stoichiometry ( \\approx 14.7$).
4. **Decoupled Fault Propagation**: Previous fault injection applied post-hoc scaling multipliers directly on telemetry outputs rather than perturbing internal physical parameters (e.g. cooling heat transfer coefficient $, injector discharge coefficient $, friction coefficient $\\mu_f$).

---

## 5. Physics Engine V2 Upgrade Strategy
- Implement modular \EngineConfig\ and \EngineAdapter\ architecture.
- Integrate dynamic first-order thermal accumulation (/dt$).
- Formulate physical mass flow: $\\dot{m}_a = V_d \\cdot \\frac{N}{120} \\cdot \\rho \\cdot \\eta_v$.
- Ground fault mechanisms directly in physical parameter degradation.
