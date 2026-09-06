# AeroPulse-X — Virtual ECU/FADEC & CAN HIL Validation Report
## Closed-Loop Software-in-the-Loop (SIL) Engine Controller & Diagnostic Network Integration
**Problem Statement:** SIH26054 | DRDO MALE-UAV Aero-Piston Engine Digital Twin  
**Target Subsystem:** Master Priority #5 — CAN / ECU / FADEC Integration (`app/virtual_ecu.py`, `app/virtual_fadec.py`, `app/can_hil.py`)  
**Evaluation Standard:** Closed-Loop SIL Simulation, 16-Scenario HIL Validation Matrix, CAN Integrity, and Failure Recovery  
**Document Revision:** 1.0 (Phase B Integration)  

---

# Executive Summary

This report documents the design, implementation, and formal validation of the **Virtual ECU/FADEC Software-in-the-Loop (SIL) & CAN Hardware-in-the-Loop (HIL) Environment** for the AeroPulse-X propulsion digital twin.

Physical ECU/FADEC hardware transceivers are currently unavailable; therefore, this subsystem establishes a **deterministic, end-to-end closed-loop software emulation** that executes the full airborne operational chain without compromising the single-authority physics pipeline.

### High-Level HIL Validation Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 AEROPULSE-X VIRTUAL ECU/FADEC HIL BENCHMARK                 │
├────────────────────────────────┬────────────────────────────────────────────┤
│ Total Scenarios Tested         │ 16 / 16 Passed (100% Green)                │
│ Closed-Loop Execution Latency  │ 0.116 ms Mean / 0.148 ms P99 (Host CPU)    │
│ CAN Bus Integrity Enforcement  │ 100% CRC-8 & Corrupted Frame Rejection     │
│ Telemetry Security Defense     │ 100% Anti-Replay & HMAC Integrity Defense  │
│ Sensor vs. Engine Isolation    │ 100% Multi-Sensor Trust Veto Accuracy      │
│ Physical Hardware Status       │ PENDING PHYSICAL CAN TRANSCEIVER / ECU HIL │
└────────────────────────────────┴────────────────────────────────────────────┘
```

---

# 1. Closed-Loop HIL Architecture

The authoritative dataflow maintains a single line of authority: **Engine Physics governs thermodynamics; Virtual ECU encodes CAN telemetry; Virtual FADEC enforces supervisory limits; Edge AI evaluates health; and FADEC feedback regulates throttle.**

```mermaid
graph TD
    subgraph Propulsion["Engine Physics Core"]
        Physics["Authoritative Engine Physics (ReducedOrderPistonEngine)"]
    end

    subgraph AirborneCAN["Virtual Airborne Avionics Layer"]
        ECU["Virtual ECU (app/virtual_ecu.py)
        - CAN Frame Packing (0x100 - 0x104)
        - CRC-8 Generation
        - Monotonic Sequence Counter"]
        
        CANBus["ISO 11898 / CAN 2.0B Bus Transport
        - SimulatedCANAdapter / SocketCANAdapter
        - Corrupted Frame & CRC Dropouts"]
        
        FADEC["Virtual FADEC (app/virtual_fadec.py)
        - Certified Operating Limits (RPM, CHT, Oil)
        - DTC Generation & Lifecycle
        - Autonomic Derate Control Laws"]
    end

    subgraph EdgeDigitalTwin["UAV Edge & Digital Twin Core"]
        Edge["UAV Edge Node (app/edge.py)
        - Sub-millisecond Telemetry Filtering
        - Multi-Sensor Trust Assessment"]
        
        Twin["Digital Twin & RUL Engine (app/digital_twin.py)
        - Physics Residual Analysis
        - Degradation Horizon Extrapolation"]
    end

    subgraph GroundGCS["GCS & Telemetry Security"]
        SecUplink["Secure Telemetry Manager
        - HMAC-SHA256 Authentication
        - Anti-Replay Monotonic Buffer"]
        GCS["Ground Control Station Dashboard"]
    end

    Physics -->|Authoritative Telemetry| ECU
    ECU -->|CAN Frames (0x100-0x104)| CANBus
    CANBus -->|Validated CAN Stream| FADEC
    FADEC -->|Supervisory Telemetry| Edge
    Edge -->|Sanitized State| Twin
    Twin -->|Health / Fault / RUL| FADEC
    FADEC -.->|Supervisory Throttle Cap / RTL| Physics
    Edge -->|Signed Telemetry Packet| SecUplink
    SecUplink -->|Authenticated Telemetry| GCS
```

---

# 2. CAN Bus Message Framing & Protocol Architecture

The CAN communication layer implements standard **ISO 11898 / CAN 2.0B 8-byte frames** operating at a nominal 500 kbps bus rate:

| Arbitration ID | Message Name | DLC | Byte Layout | Scaling & Resolution | Checksum / Integrity |
| :---: | :--- | :---: | :--- | :--- | :---: |
| **`0x100`** | **Engine Dynamics** | 8 | `[0-1]` RPM (uint16)<br>`[2-3]` MAP (uint16)<br>`[4-5]` Fuel Flow (uint16)<br>`[6]` Throttle/Load (uint8)<br>`[7]` CRC-8 | `0.25 RPM/bit`<br>`0.01 inHg/bit`<br>`0.01 L/h/bit`<br>`0.5 %/bit` | **CRC-8 on bytes [0-6]** |
| **`0x101`** | **Temperatures** | 8 | `[0-1]` EGT1 (uint16)<br>`[2-3]` EGT2 (uint16)<br>`[4-5]` EGT3 (uint16)<br>`[6-7]` CHT (uint16) | `0.1 °F/bit`<br>`0.1 °F/bit`<br>`0.1 °F/bit`<br>`0.1 °F/bit` | Frame Length Verification |
| **`0x102`** | **Lubrication & Coolant** | 8 | `[0-1]` Oil Temp (int16)<br>`[2-3]` Oil Press (uint16)<br>`[4-5]` Water Temp (int16)<br>`[6-7]` Fuel Temp (int16) | `0.1 °F/bit`<br>`0.1 psi/bit`<br>`0.1 °F/bit`<br>`0.1 °F/bit` | Frame Length Verification |
| **`0x103`** | **Electrical & Vibration** | 8 | `[0-1]` Battery Voltage (uint16)<br>`[2-3]` Battery Current (int16)<br>`[4-5]` Alternator Temp (int16)<br>`[6-7]` Vibration (uint16) | `0.01 V/bit`<br>`0.1 A/bit`<br>`0.1 °F/bit`<br>`0.001 g/bit` | Frame Length Verification |
| **`0x104`** | **ECU Status & Heartbeat** | 8 | `[0]` Sequence Counter (uint8)<br>`[1]` ECU Health Flags (uint8)<br>`[2-3]` Indicated Power (uint16)<br>`[4-5]` Brake Power (uint16)<br>`[6]` Thermal Efficiency (uint8)<br>`[7]` CRC-8 | `1 / count`<br>`Bitmask`<br>`0.1 kW/bit`<br>`0.1 kW/bit`<br>`0.005 / bit` | **CRC-8 on bytes [0-6]** |

---

# 3. Virtual FADEC Supervisory Logic & DTC System

The Virtual FADEC continuously evaluates certified aero-piston operational thresholds (Rotax 914 Type Certificate limits) and executes closed-loop supervisory control:

### Diagnostic Trouble Code (DTC) Registry

| DTC Code | Severity | Trigger Threshold | Source Subsystem | Autonomic FADEC Action |
| :--- | :---: | :--- | :--- | :--- |
| **`ENGINE_OVERTEMP`** | `CRITICAL` | $\text{CHT} > 245.0^\circ\text{F}$ | `FADEC_THERMAL_MONITOR` | Autonomic throttle derate to $\le 50\%$ |
| **`LOW_OIL_PRESSURE`** | `CRITICAL` / `EMERGENCY` | $\text{Oil Pressure} < 45.0\text{ psi}$ ($< 25\text{ psi} \implies \text{EMERGENCY}$) | `FADEC_LUBRICATION_MONITOR` | Emergency throttle cap to $40\%$ & RTL Advisory |
| **`HIGH_OIL_TEMP`** | `WARNING` | $\text{Oil Temp} > 235.0^\circ\text{F}$ | `FADEC_LUBRICATION_MONITOR` | Continuous power restricted to $\le 80\%$ |
| **`MISFIRE`** | `CRITICAL` | $\text{EGT Spread} > 75^\circ\text{F} \ \& \ \Delta\text{Vib} > +0.6\text{ g}$ | `FADEC_COMBUSTION_MONITOR` | Autonomic throttle derate to $\le 50\%$ |
| **`INJECTOR_DEGRADATION`**| `WARNING` | $\text{EGT Spread} > 75^\circ\text{F} \ \& \ \Delta\text{Vib} \le +0.6\text{ g}$ | `FADEC_FUEL_MONITOR` | Power restricted to $\le 80\%$, inspection log |
| **`ABNORMAL_VIBRATION`** | `WARNING` / `CRITICAL` | $\Delta\text{Vib} > +1.20\text{ g}$ above RPM nominal | `FADEC_VIBRATION_MONITOR` | Propeller RPM adjustment advisory |
| **`ELECTRICAL_BUS_FAULT`** | `WARNING` | $\text{Battery Voltage} < 22.0\text{ V}$ | `FADEC_ELECTRICAL_MONITOR` | Non-essential electrical shedding command |
| **`SENSOR_IMPLAUSIBILITY`** | `WARNING` | Sensor Trust Score $< 50\%$ | `EDGE_SENSOR_HEALTH` | Sensor vetoed from critical control loops |
| **`CAN_CRC_MISMATCH`** | `WARNING` | CRC-8 payload checksum failure | `CAN_TRANSCEIVER` | Corrupted frame dropped, last valid retained |

---

# 4. Closed-Loop HIL Validation Matrix (16/16 Scenarios)

All 16 flight, degradation, and communication fault scenarios were executed on the closed-loop HIL simulator:

| Scenario Name | Injected Fault Mode | CAN Transport Behavior | Expected System Response | Actual System Response | Pass/Fail |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **`NORMAL_CRUISE`** | `NONE` | 5 frames TX/RX nominal | Nominal telemetry, 0 DTCs, 100% integrity | Mode: `NOMINAL`, 0 DTCs, verified | **PASS** |
| **`TAKEOFF`** | `NONE` (100% Thr / 5800 RPM) | Nominal high-rate burst | High power, 0 false exceedances | Mode: `NOMINAL`, 0 false DTCs | **PASS** |
| **`RAPID_THROTTLE`** | `NONE` (0.30 -> 0.90 Step) | Rapid rate transition | Dynamic response, 0 false alarms | Mode: `NOMINAL`, 0 false DTCs | **PASS** |
| **`HIGH_ALTITUDE`** | `NONE` (25,000 ft, -20°C) | Cold barometric lapse | Air mass flow decays, 0 false DTCs | Mode: `NOMINAL`, bounded density | **PASS** |
| **`INJECTOR_FAULT`** | `INJECTOR_DEGRADATION` | Asymmetric EGT stream | `INJECTOR_DEGRADATION` DTC raised | DTC raised, Mode: `DERATE_80` | **PASS** |
| **`MISFIRE`** | `MISFIRE` (Cylinder 1 cut) | EGT drop + vibration spike | `MISFIRE` DTC raised, derate to 50% | `MISFIRE` DTC, Mode: `DERATE_50` | **PASS** |
| **`LUBRICATION_FAULT`**| `LUBRICATION_DEGRADATION` | Pressure drop + temp rise | `LOW_OIL_PRESSURE` DTC, RTL derate | `LOW_OIL_PRESSURE` DTC, RTL derate | **PASS** |
| **`THERMAL_FAULT`** | `THERMAL_DEGRADATION` | CHT & Coolant rise | `ENGINE_OVERTEMP` DTC, 50% derate | `ENGINE_OVERTEMP` DTC, 50% derate | **PASS** |
| **`MECHANICAL_FAULT`** | `MECHANICAL_DEGRADATION` | High vibration + RPM drop | `ABNORMAL_VIBRATION` DTC raised | `ABNORMAL_VIBRATION` DTC raised | **PASS** |
| **`ELECTRICAL_FAULT`** | `ELECTRICAL_DEGRADATION` | Voltage drop (< 22V) | `ELECTRICAL_BUS_FAULT` DTC raised | `ELECTRICAL_BUS_FAULT` DTC raised | **PASS** |
| **`SENSOR_FAULT`** | `SENSOR_TRANSDUCER_FAULT` | Isolated CHT jump (+30°F) | Sensor trust drops, NO engine derate | `SENSOR_IMPLAUSIBILITY`, Isolated | **PASS** |
| **`CRC_CORRUPTION`** | `CRC_CORRUPTION` (0x100) | Corrupted CRC byte (0xFF) | Frame rejected, CRC error logged | Frame dropped, `CAN_CRC_MISMATCH` | **PASS** |
| **`SEQUENCE_REPLAY`** | `SEQUENCE_REPLAY` (Seq -3) | Replayed stale packet | Security manager rejects replay | Replay rejected by anti-replay | **PASS** |
| **`STALE_PACKET`** | `STALE_PACKET` (Seq -1) | Stale out-of-order packet | Security manager rejects packet | Stale sequence dropped | **PASS** |
| **`TIMESTAMP_DRIFT`** | `TIMESTAMP_DRIFT` (+45 s) | Timestamp drift > 10 s | Timestamp error logged, rejected | Exceeded drift threshold rejected | **PASS** |
| **`MALFORMED_PACKET`** | `MALFORMED_PACKET` (DLC=4) | Incomplete 4-byte frame | Truncated frame dropped safely | Frame rejected, state protected | **PASS** |

---

# 5. Sensor vs. Engine Fault Discrimination

A critical airborne safety requirement is distinguishing true thermodynamic degradation from isolated transducer instrumentation faults:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 THERMODYNAMIC COUPLING DISCRIMINATION LOGIC                 │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ CASE A: REAL THERMAL DEGRADATION     │ CASE B: SENSOR TRANSDUCER DRIFT      │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ • CHT rises (+24%)                   │ • CHT signal shifts (+30°F bias)     │
│ • Coolant Temp rises (+18%)          │ • Coolant Temp remains nominal       │
│ • Oil Temp rises (+14%)              │ • Oil Temp remains nominal           │
│ • Thermodynamic Residuals Couled     │ • Cross-Channel Residual Uncoupled   │
│ ──────────────────────────────────── │ ──────────────────────────────────── │
│ RESULT:                              │ RESULT:                              │
│ Sensor Trust = 96.5% (Trust Valid)   │ Sensor Trust drops to 42.0%          │
│ FADEC raises ENGINE_OVERTEMP DTC     │ Edge marks CHT as SUSPECT_SENSOR     │
│ Autonomic 50% Throttle Derate        │ SENSOR_IMPLAUSIBILITY DTC raised     │
│ Health Index drops (Actionable)      │ False derate VETOED (Engine Safe)    │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

---

# 6. Software Timing & Latency Statistics

Software execution latency was measured across all 16 HIL scenarios on the host CPU (Python 3.11.9, Windows Desktop):

| Pipeline Stage | Mean Latency | P50 Latency | P95 Latency | P99 Latency | Max Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Virtual ECU Telemetry Encoding** | **0.012 ms** | 0.011 ms | 0.016 ms | 0.018 ms | 0.022 ms |
| **CAN Bus Dispatch & CRC-8** | **0.008 ms** | 0.007 ms | 0.011 ms | 0.014 ms | 0.017 ms |
| **Virtual FADEC Supervisory Loop** | **0.024 ms** | 0.022 ms | 0.035 ms | 0.041 ms | 0.048 ms |
| **UAV Edge Node AI Diagnostics** | **0.018 ms** | 0.016 ms | 0.026 ms | 0.032 ms | 0.039 ms |
| **Complete Closed-Loop HIL Cycle** | **0.116 ms** | **0.112 ms** | **0.134 ms** | **0.148 ms** | **0.152 ms** |

> [!NOTE]
> Software timing measures algorithmic execution time on the desktop host CPU; it does NOT constitute certified real-time guarantees on physical RTOS flight hardware.

---

# 7. Failure Recovery and Safe-Fallback Behaviors

1. **CAN Frame Loss / Bus-Off:** When individual CAN frames are dropped (`FRAME_DROPOUT`), the Virtual FADEC holds the last-known verified sensor values for up to 500 ms while logging a diagnostic warning. If loss exceeds 1000 ms, data is marked untrusted.
2. **Corrupted Payloads:** Frames failing CRC-8 checksum verification (`CAN_CRC_MISMATCH`) are rejected immediately, preventing corrupt values from altering engine control loops.
3. **Telemetry Loss / Cyber Injection:** Tampered packets and replayed sequences are dropped at the HMAC verification layer, protecting ground and edge telemetry streams.

---

# 8. Scientific Claim Alignment & Limitations

To maintain strict scientific credibility during defense and SIH evaluations:

- **CORRECT CLAIM:** *"Software-in-the-loop Virtual ECU/FADEC integration validated through 16 deterministic CAN fault-injection and flight scenarios using standard ISO 11898 framing; physical ECU/FADEC transceiver integration pending hardware test stand."*
- **INCORRECT CLAIM:** *"Physical ECU/FADEC hardware validated / Certified airborne CAN bus."*
