# AEROPULSE-X FAULT PROPAGATION & SIGNATURE CATALOG
## Physically Grounded Fault Mechanics, Observable Signatures, and Sensor Isolation

**Document Version**: 2.0.0-SIH  
**Release Date**: August 26, 2026  
**Module**: `app/degradation_model.py` & `app/simulator.py`

---

## 1. Fault Architecture & Physical Propagation Chains

```
[ Injected Physical Degradation (Severity λ ∈ [0, 1]) ]
                          |
                          v
        [ Physics Engine Internal State Perturbation ]
  (Cooling Efficiency, Fuel Metering, Cyclic Torque, Friction)
                          |
                          v
         [ Coupled Sensor Stream Telemetry (y_meas) ]
                          |
                          v
            [ Physics Residual & ML Diagnosis ]
```

---

## 2. Comprehensive Fault Catalog

### FAULT 1: Thermal Degradation & Overheating
- **Physical Cause**: Radiator blockage, coolant pump cavitation, or cooling air duct restriction.
- **Governing Parameter**: Cooling heat transfer coefficient reduced: $h_{\text{cool}} = h_{\text{cool,0}} \cdot (1 - 0.55 \lambda)$.
- **Thermodynamic Chain**: Heat accumulation $\dot{Q}_{\text{in}} - \dot{Q}_{\text{cool}} > 0 \implies \frac{dT_{\text{cht}}}{dt} > 0$.
- **Sensor Manifestations**:
  - `CHT`: Rapidly increases ($+20\%$ to $+35\%$).
  - `EFI_Water_Temp`: Coolant loop spikes ($+18\%$ to $+28\%$).
  - `Oil_Temp`: Elevated through engine block conduction ($+12\%$ to $+20\%$).
  - `EGT1..3`: Secondary rise due to increased cylinder wall temperature ($+8\%$ to $+15\%$).
  - `Indicated_Power_kW`: Drops slightly due to air charge heating ($\rho_{\text{charge}}$ drop).

### FAULT 2: Injector Delivery Degradation
- **Physical Cause**: Fuel injector nozzle coking, partial orifice clogging, or rail pressure regulator drift.
- **Governing Parameter**: Effective fuel discharge coefficient reduced on cylinder: $C_{d,\text{inj}} = C_{d0} \cdot (1 - 0.35 \lambda)$.
- **Thermodynamic Chain**: Local Air-Fuel Ratio becomes excessively lean ($AFR > 16.5$), reducing flame speed and pushing peak heat release into the exhaust stroke.
- **Sensor Manifestations**:
  - `Fuel_Flow`: Decreases by $10\%$ to $25\%$.
  - `EGT1..3`: Asymmetric spread; affected cylinder EGT rises sharply or fluctuates.
  - `MAP_Injector`: Compensation regulator increases pulse width / pressure.
  - `Brake_Power_kW`: Loss of $8\%$ to $16\%$ engine torque.

### FAULT 3: Combustion Misfire
- **Physical Cause**: Spark plug fouling, ignition coil breakdown, or severe lean flameout.
- **Governing Parameter**: Misfire fraction $f_{\text{misfire}} = \lambda \cdot 0.30$.
- **Thermodynamic Chain**: Complete failure of fuel burn during power stroke; unburned fuel expelled into exhaust manifold.
- **Sensor Manifestations**:
  - `EGT`: Sharp drop on affected cylinder ($T_{\text{egt}} \downarrow 25\%$).
  - `Engine_RPM`: Cyclic rotational speed fluctuations and jitter ($\Delta N \approx \pm 80\text{ RPM}$).
  - `Vibration`: Pronounced 0.5X and 1X rotational harmonic vibration spikes ($+60\%$ to $+120\%$).

### FAULT 4: Lubrication Degradation
- **Physical Cause**: Oil pump relief valve sticking, oil aeration, or thermal viscosity shearing.
- **Governing Parameter**: Hydrodynamic friction coefficient increased $\mu_{\text{fric}} = \mu_0 \cdot (1 + 0.80 \lambda)$ and pump head reduced.
- **Thermodynamic Chain**: Loss of boundary lubrication film $\implies$ elevated boundary friction power loss $\implies$ oil shear heating.
- **Sensor Manifestations**:
  - `Oil_Pressure`: Critical drop ($-35\%$ to $-65\%$, dropping below 25 PSI).
  - `Oil_Temp`: Rises steadily ($+15\%$ to $+30\%$).
  - `Vibration`: Elevated high-frequency mechanical noise.
  - `Engine_RPM`: Small drag-induced loss if throttle is fixed.

### FAULT 5: Sensor Specific Faults (Electrical / Signal)
- **Physical Cause**: Transducer drift, wiring harness short/open, ADC quantization fault, or loose connector.
- **Key Differentiation**: **Sensor faults modify ONLY the measured signal and DO NOT affect engine thermodynamic power or physical state.**
- **Types Supported**:
  1. *Bias*: Constant offset ($y = y_{\text{true}} + \Delta B$).
  2. *Drift*: Progressive ramp ($y = y_{\text{true}} + k \cdot t$).
  3. *Spike*: Single-frame transient outlier ($y = y_{\text{true}} + 150$).
  4. *Stuck-at*: Constant frozen value with zero variance.
  5. *Dropout*: Value collapses to zero or NaN.
