# AeroPulse-X — Master Technical & Research References Directory
## Authoritative Bibliography of Government Standards, Propulsion Literature, and Dataset Citations

**Document ID:j* AEROPULSE-X-REF-2026-09-06  
**Classification:** Authoritative Technical Reference Document

---

### 1. Primary Engine & Government Aerospace Standards

1. **BRP-Rotax GmbH & Co KG (2018)**
   - *Title:* Operators Manual for Rotax Engine Type 914 Series.
   - *Reference:* Ref. MM-914, Ed. 2, Rev. 0. BRP-Rotax, Gunskirchen, Austria.
   - *What it Proves:* Authoritative operational limits: Max Continuous Power 84.5 kW @ 5500 RPM, Take-Off Power 84.5 kW @ 5800 RPM (5 min limit), CHT Max 135 C, Oil Pressure 1.5 - 7.0 bar, Displacement 1211 cm3.
   - *What it Does NOT Prove:* Does not provide internal component wear rates or run-to-failure degradation kinetics.

2. **European Aviation Safety Agency (EASA) (2010)**
   - *Title:* Type Certificate Data Sheet No. E.122 for Rotax 914 Series Engines.
   - *Reference:* EASA TCDSE.122, Issue 03. EASA, Cologne, Germany.
   - *What it Proves:* Official civil certification envelope, compression ratio (9.0:1), turbocharger critical altitude (15,000 ft), and manifold pressure ceilings.
   - *What it Does NOT Prove:* Does not contain in-flight sensor time-series telemetry.

3. **Defence Research and Development Organisation (DRDO) / ADE (2020-2024)**
   - *Title:* Technical Overview and Flight Testing of TAPSS-BH-201 (Rustom-II) and Archer MALE UAV£.
   - *Reference:* Press Information Bureau (PIB) / DRDO Aeronautical Development Establishment (ADE), Bengaluru, India.
   - *What it Proves:* Establishes target platform operational profile: Twin-engine / Single-engine turbocharged aero-piston MALE UAF, operating altitude up to 28,000 ft, endurance >18-24 hours.
   - *What it Does NOT Prove:* Specific internal flight telemetry is restricted/classified.

---

### 2. Internal Combustion Engine Thermodynamics & Friction Literature

4. **Heywood, John B. (1988)**
   - *Title:* Internal Combustion Engine Fundamentals.
   - *Reference:* McGraw-Hill Series in Mechanical Engineering, New York.
   - *What it Proves:* Speed-density manifold filling, Otto cycle thermal efficiency scaling, and lumped-capacitance heat rejection formulations.

5. **Bishop, I. N. (1964)**
   - *Title:* Effect of Design Variables on Top Ring End Gap and Engine Friction.
   - *Reference:* SAE Technical Paper 640807, doi:10.4271/640807.
   - *What it Proves:* Hydrodynamic friction correlation ($P_{friction} \\propto c_1 N + c_2 N^2$) for reciprocating internal combustion engines.

6. **Taylor, Charles Fayette (1985)**
   - *Title:* The Internal-Combustion Engine in Theory and Practice: Vol. 1 & 2.
   - *Reference:* MIT Press, Cambridge, MA.
   - *What it Proves:* Aircraft engine volumetric efficiency scaling across altitude and ambient temperature lapse.

---

### 3. Open Aerospace Datasets & Prognostic Benchmarks

7. **NASA Dryden Flight Research Center (ACES Program)**
   - *Title:* Airborne Telemetry and Flight Research Data for Altus II UAV.
   - *What it Proves:* In-flight operational sensor distributions (RPM, CHT, EGT, Oil Temp, MAP) for high-altitude reciprocating UAV powerplants.
   - *What it Does NOT Prove:* Contains zero run-to-failure degradation flights.

8. **Saxena, A., Goebel, K., Simon, D., & Eklund, N. (2008)**
   - *Title:* Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation.
   - *Reference:* International Conference on Prognostics and Health Management (PHM08), Denver, CO (NASA C-MAPS�dataset).
   - *What it Proves:* Standardized prognostic evaluation methodology for RUL metrics and scoring functions.
   - *What it Does NOT Prove:* Turbofan cycle physics do not transfer to reciprocating piston engines.

9. **Carnegie Mellon University AirLab (2020)**
   - *Title:* @LFA: AirLab Failure and Anomaly Dataset for Fixed-Wing Autonomous UAVs.
   - *What it Proves:* In-flight anomaly dynamics and control surface failure signatures in autonomous fixed-wing aircraft.

10. **Case Western Reserve University (CURW) Bearing Data Center (2003)**
    - *Title:* Seeded Fault Bearing Vibration Database.
    - *What it Proves:* Accelerometer harmonic frequencies corresponding to inner/outer raceway spalling and mechanical bearing degradation.