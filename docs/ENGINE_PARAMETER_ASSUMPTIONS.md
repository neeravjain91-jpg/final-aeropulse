# AEROPULSE-X ENGINE PARAMETER ASSUMPTIONS
## Parameterization Schema & Mathematical Assumptions for UAV Propulsion Digital Twin

**Document Version**: 2.0.0-SIH  
**Release Date**: August 26, 2026  
**Class/Target**: Generic 4-Cylinder 4-Stroke Spark-Ignited MALE UAV Engine (1.35L Class)

---

## 1. Parameterization Architecture
To ensure scalability, AeroPulse-X separates the **Digital Twin Core** from the **Engine Parameterization Layer**. Any UAV piston engine can be modeled by specifying an `EngineConfig` instance without modifying the underlying solver or diagnostic pipelines.

```
+---------------------+
|  Digital Twin Core  |
+----------+----------+
           |
           v
+---------------------+
|   Engine Adapter    |
+----------+----------+
           |
           v
+---------------------+
| EngineConfig Schema |
+---------------------+
```

---

## 2. Configurable Parameter Schema & Default Assumptions

| Parameter Name | Symbol | Default Value | Units | Physical Justification / Description |
| :--- | :--- | :--- | :--- | :--- |
| **Engine Name** | `name` | `AeroPiston-4C-1.35L` | - | Model identifier for reference |
| **Displacement** | $V_d$ | `1.352` | Liters ($10^{-3}\text{ m}^3$) | Total swept volume for 4 cylinders |
| **Bore** | $B$ | `84.0` | mm | Cylinder bore diameter |
| **Stroke** | $S$ | `61.0` | mm | Piston stroke length |
| **Number of Cylinders** | $N_{\text{cyl}}$ | `4` | - | Horizontally-opposed or inline 4-cylinder layout |
| **Compression Ratio** | $r_c$ | `9.0` | : 1 | Geometric compression ratio ($V_{\max} / V_{\min}$) |
| **Specific Heat Ratio** | $\gamma$ | `1.33` | - | Average ratio of specific heats ($C_p / C_v$) for combustion gases |
| **Fuel LHV** | $LHV_{\text{fuel}}$ | `43.5` | MJ/kg | Lower heating value of standard 100LL Avgas / Mogas |
| **Stoichiometric AFR** | $AFR_{\text{stoich}}$ | `14.7` | : 1 | Air-fuel mass ratio for complete combustion |
| **Base Rated Power** | $P_{\text{base}}$ | `84.5` | kW (~115 HP) | Maximum continuous sea-level brake power |
| **Nominal Cruise Speed** | $N_{\text{nom}}$ | `3000.0` | RPM | Standard cruise operating point |
| **Maximum Rated Speed**| $N_{\max}$ | `5800.0` | RPM | Redline / maximum takeoff RPM limit |
| **Idle Speed** | $N_{\text{idle}}$ | `1400.0` | RPM | Minimum flight idle RPM |
| **Base Friction Loss** | $P_{\text{fric0}}$ | `6.5` | kW | Pumping and mechanical hydrodynamic drag at idle |
| **Thermal Mass ($C_{\text{th}}$)**| $C_{\text{th}}$ | `35000.0` | J / K | Cylinder head aluminum alloy lumped thermal capacity |
| **Cooling Surface Area**| $A_{\text{cool}}$ | `0.85` | $\text{m}^2$ | Effective cylinder head and water jacket cooling area |
| **Nominal Heat Transfer**| $h_{\text{cool}}$ | `120.0` | $\text{W}/(\text{m}^2 \cdot \text{K})$ | Forced convection heat transfer coefficient |
| **Oil Circuit Volume** | $V_{\text{oil}}$ | `3.5` | Liters | Sump oil capacity |
| **Nominal Oil Viscosity**| $\nu_0$ | `14.0` | cSt @ 100°C | Kinematic viscosity (SAE 15W-50 Aero Oil) |

---

## 3. Disclaimers & Non-Classified Status
> [!IMPORTANT]
> **SIH / RESEARCH DISCLAIMER**:  
> The parameter values listed above represent engineering approximations for general 100–120 HP aero piston engines (such as Rotax 912/914 or equivalent UAV propulsion units). They do NOT represent classified, proprietary, or restricted data from any specific defense manufacturer or military agency. All values are fully open-source and customizable.
