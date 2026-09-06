# Canonical Telemetry Schema v2.0 Specification

## 1. Overview
The Canonical Telemetry Schema (Schema v2.0) defines a standardized, strongly typed data structure (`CanonicalTelemetryPoint`) representing multivariate engine, electrical, network, prognostic, and flight supervisory states at each discrete simulation time step.

---

## 2. Field Definitions & Data Dictionary

| Group | Field Name | Type | Units / Format | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Metadata** | `timestamp` | `float` | seconds | Simulation timestamp since trajectory start |
| | `trajectory_id` | `str` | alphanumeric | Unique trajectory identifier |
| | `engine_id` | `str` | alphanumeric | Target engine serial / model ID |
| | `mission_id` | `str` | alphanumeric | Assigned mission identifier |
| | `mission_phase` | `str` | enum | STARTUP, TAKEOFF, CLIMB, CRUISE, HIGH_ALTITUDE, ENDURANCE, DESCENT, LANDING |
| **Kinetics & Ambient** | `RPM` | `float` | RPM [0, 7000] | Crankshaft rotational speed |
| | `throttle` | `float` | fraction [0.0, 1.0] | Commanded / actual throttle opening |
| | `engine_load` | `float` | fraction [0.0, 1.0] | Relative mechanical load |
| | `MAP` | `float` | inHg | Manifold Absolute Pressure |
| | `manifold_pressure` | `float` | kPa | Manifold Absolute Pressure in metric units |
| | `ambient_temperature` | `float` | deg C [-60, +80] | Free-stream ambient air temperature |
| | `ambient_pressure` | `float` | kPa | Barometric atmospheric pressure |
| | `altitude` | `float` | feet [0, 50000] | Barometric pressure altitude |
| | `vertical_speed` | `float` | ft/min | Climb (+) or descent (-) rate |
| | `ground_speed` | `float` | knots | Aircraft horizontal ground speed |
| **Thermodynamics** | `CHT` | `float` | deg C [0, 350] | Cylinder Head Temperature |
| | `coolant_temperature`| `float` | deg C | Water / Coolant temperature |
| | `EGT` | `float` | deg C | Mean Exhaust Gas Temperature |
| | `oil_pressure` | `float` | psi [0, 150] | Engine lubrication pressure |
| | `oil_temperature` | `float` | deg C | Engine oil sump temperature |
| | `fuel_flow` | `float` | L/h | Volumetric fuel consumption rate |
| | `airflow` | `float` | kg/h | Induction air mass flow |
| | `AFR_or_lambda` | `float` | ratio | Air-to-fuel equivalence ratio |
| | `torque` | `float` | N*m | Shaft brake torque |
| | `brake_power` | `float` | kW | Shaft brake power output |
| **Vibration & Power** | `vibration` | `float` | g RMS [0, 15] | Tri-axial engine vibration |
| | `bus_voltage` | `float` | Volts [0, 40] | 28V DC avionics bus voltage |
| | `current` | `float` | Amperes | Total electrical current draw |
| | `battery_SOC` | `float` | % [0, 100] | Battery state of charge |
| | `alternator_temperature` | `float` | deg C | Alternator stator temperature |
| **Health & Degradation** | `health_index` | `float` | score [0, 100] | Continuous engine health index ($H$) |
| | `degradation_severity` | `float` | fraction [0.0, 1.0] | Normalized wear progression ($s$) |
| | `degradation_stage` | `str` | enum | HEALTHY, EARLY, MODERATE, SEVERE, CRITICAL |
| **Physical Faults** | `fault_present` | `bool` | True/False | Physical engine failure active |
| | `fault_type` | `str` | enum | none, thermal, lubrication, mechanical, injector, misfire, electrical, compound |
| | `fault_severity` | `float` | fraction [0.0, 1.0] | Magnitude of active physical fault |
| | `failure_mode` | `str` | str | Degradation root cause mechanism |
| **Sensor Quality** | `sensor_fault_present` | `bool` | True/False | Sensor transducer corruption active |
| | `sensor_fault_type` | `str` | enum | none, bias, drift, noise, scale_error, saturation, stuck_at, dropout, intermittent |
| | `sensor_trust` | `float` | % [0, 100] | Transducer signal validity score |
| **Ground Truth RUL** | `true_failure_time` | `float` | hours | Exact timestamp where $H(t) \le 35.0$ |
| | `true_RUL` | `float` | hours | Exact mathematical RUL: $\max(0, t_{\text{fail}} - t)$ |
| **Model Prognostics** | `predicted_RUL` | `float` | hours | Digital twin estimated remaining life |
| | `RUL_lower` | `float` | hours | 5th percentile uncertainty bound |
| | `RUL_upper` | `float` | hours | 95th percentile uncertainty bound |
| | `RUL_confidence` | `float` | % [0, 100] | Predictive confidence interval score |
| **ECU & FADEC** | `ECU_state` | `str` | enum | OFF, CRANKING, ACTIVE_RUN, DERATED, EMERGENCY_STOP |
| | `FADEC_state` | `str` | enum | NOMINAL, MONITORING, DERATED_WARN, DERATED_CRITICAL, EMERGENCY_RTL |
| | `DTC` | `list[str]` | list of codes | Active Diagnostic Trouble Codes |
| | `derate_command` | `float` | fraction [0.0, 1.0] | Commanded throttle limit |
| | `safety_action` | `str` | enum | NONE, ADVISORY, DERATE_80, DERATE_50, EMERGENCY_RTL |
| **Virtual CAN 2.0B** | `CAN_ID` | `str` | hex string | Primary arbitration ID (`0x100`..`0x104`) |
| | `CAN_DLC` | `int` | bytes (= 8) | ISO 11898 payload length |
| | `CAN_sequence` | `int` | int [0..15] | Rolling sequence counter |
| | `CAN_CRC_status` | `str` | enum | VALID, CRC_ERROR, STALE, CORRUPTED |
| | `CAN_packet_loss` | `float` | fraction [0.0, 1.0] | Instantaneous packet loss |
| | `CAN_latency` | `float` | milliseconds | Transport latency |
| **Flight Computer** | `flight_computer_state` | `str` | enum | OPERATIONAL, OVERLOADED, RECOVERING |
| | `watchdog_state` | `str` | enum | HEALTHY, WARNING, TRIPPED, RESTARTED |
| | `deadline_missed` | `bool` | True/False | Periodic cycle deadline flag |
