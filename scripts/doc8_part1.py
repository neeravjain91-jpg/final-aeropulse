# AeroPulse-X — Master Jury Defense & Adversarial Q&A Compendium
## 50 Highly Adversarial Technical Questions and Evidence-Backed Answers for DRDO, Avionics, AI/ML, and Reliability Panels

**Document ID:** AEROPULSE-X-JURY-QA-2026-09-06  
**Target Evaluation Panel:** DRDO Propulsion Engineers, UAV Flight Avionics Specialists, AI/ML Scientists, Reliability/Prognostics Engineers, and SIH Judges.

---

### PART 1 — DRDO Propulsion & Thermodynamics Engineering (Questions 1 to 10)

#### Q1: Why did you choose the Rotax 914 F engine as your baseline rather than an indigenous or turbofan engine?
- **Evidence-Based Answer:** The Rotax 914 F Turbo is the canonical operational powerplant for modern tactical MALE UAVs globally (including platforms in the class of TAPAS-BH-201 and Heron). It possesses fully documented civil certification envelopes (EASA TCDS E.122) and published thermodynamic limits (84.5 kW max continuous power, 135 °C CHT limit, 1.5–7.0 bar oil pressure), providing an auditable, unclassified ground truth for thermodynamic modeling. Furthermore, AeroPulse-X implements a protocol-based modular architecture (IEngineModel), allowing indigenous powerplants to be substituted via a single Python plugin (pp/plugins/rotax914.py).

#### Q2: How does your digital twin model internal combustion and thermal heat rejection?
- **Evidence-Based Answer:** We employ a reduced-order lumped-capacitance 4-stroke Otto cycle model (pp/engine_model.py). Mass air flow is calculated via speed-density dynamics ($\dot{m}_{air} = \frac{N}{120} V_d \rho_{man} \eta_v$), fuel flow is metered via speed-density air-fuel ratio ({actual}$), and heat release is computed from fuel Lower Heating Value ({in} = \dot{m}_{fuel} \cdot LHV \cdot \eta_{comb}$). Thermal rejection ({rej} = P_{ind} \cdot (1 - \eta_{th}) / \eta_{th}$) is partitioned across coolant and oil circuits with convective heat transfer scaling dynamically with airspeed and ISA ambient temperature lapse.

#### Q3: How is engine friction modeled, and why is it not treated as a constant?
- **Evidence-Based Answer:** Friction is non-linear and increases with rotational speed and oil degradation. We implement the Bishop-Heywood hydrodynamic friction correlation (pp/engine_model.py):
  P_{friction} = \left( P_{friction,base} + c \cdot \left(\frac{N}{N_{max}}\right)^{1.8} \right) \cdot \mu_{friction}
  This captures boundary and hydrodynamic shear losses. When oil degrades (e.g. viscosity loss), $\mu_{friction}$ dynamically increases, resulting in lower brake horsepower ({brake} = P_{ind} - P_{friction}$) and higher oil temperature.

#### Q4: How does atmospheric altitude affect the engine in your simulation?
- **Evidence-Based Answer:** We implement the standard International Standard Atmosphere (ISA) barometric lapse:
  T(h) = T_0 - L \cdot h, \quad P(h) = P_0 \left(1 - \frac{L \cdot h}{T_0}\right)^{\frac{g}{R \cdot L}}, \quad \rho(h) = \frac{P(h)}{R \cdot T(h)}
  As altitude climbs toward the critical turbocharger altitude (15,000 ft), manifold absolute pressure (MAP) is maintained by the turbo wastegate; above critical altitude, MAP decreases monotonically with density ratio $\sigma = \rho / \rho_0$, reducing indicated power and air cooling efficiency.

#### Q5: Is your engine model steady-state or dynamic transient?
- **Evidence-Based Answer:** It is a **quasi-steady thermodynamic cycle with first-order dynamic thermal lag**. While gas exchange is computed at discrete operational steps, thermal masses (cylinder head temperature, coolant, oil) integrate differential heat accumulation equations ( C_p \frac{dT}{dt} = Q_{in} - Q_{out}$), capturing thermal inertia during rapid throttle steps.

#### Q6: How are Exhaust Gas Temperatures (EGT) distributed across individual cylinders?
- **Evidence-Based Answer:** The model computes baseline manifold EGT from combustion enthalpy, then tracks individual cylinder offsets (EGT1, EGT2, EGT3, EGT4). In the event of a cylinder misfire or injector fouling on Cylinder 1, EGT1 experiences an immediate localized drop (-28%) while unburned fuel increases exhaust instability, isolating the fault to a specific cylinder.

#### Q7: What is the source of your thermal transfer coefficients?
- **Evidence-Based Answer:** Coefficients (, h_{conv}, k_{rad}$) were calibrated against Rotax 914 F operator limits and verified against NASA ACES Altus II flight envelopes (^2 = 0.9308$). They are explicitly documented in docs/ENGINE_PARAMETER_ASSUMPTIONS.md as fitted parameters rather than proprietary manufacturer test-cell data.

#### Q8: What happens during a rapid throttle transition?
- **Evidence-Based Answer:** Rapid throttle increases MAP and combustion heat instantaneously, while RPM ramps up according to propeller load inertia, and CHT accumulates heat over a 15–30 second thermal transient window, preventing false-positive thermal spike alarms.

#### Q9: Can this model simulate detonation or pre-ignition?
- **Evidence-Based Answer:** Detonation is captured empirically via the combustion instability mode (pp/degradation_model.py), where severe thermal runaway and lean AFR trigger high-frequency vibration harmonics and rapid CHT accumulation.

#### Q10: Has this engine model been validated on a physical dynamometer test cell?
- **Evidence-Based Answer:** **No.** Physical test-cell validation is currently UNAVAILABLE. The model has been verified mathematically, calibrated against published OEM type certificates (EASA E.122), and cross-checked against NASA ACES flight logs. Physical test-cell runs represent the next phase in our deployment roadmap.
