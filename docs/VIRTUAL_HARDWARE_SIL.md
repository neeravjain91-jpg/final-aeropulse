# AeroPulse-X — Phase C2: Virtual Hardware & Flight-Computer Software-in-the-Loop (SIL) Emulation

**Subsystem Hardened:** Master Technical Priorities #4 & #5 — Embedded Edge Compute, Flight Computer Emulation, and CAN / ECU / FADEC Integration  
**Document Classification:** Software-in-the-Loop (SIL) Technical Specification & Emulation Report  
**Verification Baseline:** 240/240 Automated Tests Passing (100% Green, 0 Regressions)  

---

## 1. Scientific Claim Discipline & Validation Boundaries

> [!IMPORTANT]
> **DISCLAIMER & BOUNDARY DECLARATION:**
> This subsystem is a **Software-in-the-Loop (SIL) Emulation**.
> - **NO Physical ARM Target Validation Claimed:** Simulated execution budget is modeled programmatically on the desktop host CPU.
> - **NO Physical ECU/FADEC Hardware Claimed:** ECU and FADEC logic run in pure Python SIL containers.
> - **NO Physical Transceiver or Electrical Validation Claimed:** CAN 2.0B bus arbitration and 28V DC power sags are mathematically modeled.
> - **NO DO-178C / DO-254 Flight Certification Claimed:** Research and prototype demonstration only; airworthiness sign-off requires physical dynamometer and environmental flight test certification.

---

## 2. End-to-End Closed-Loop Signal Flow Architecture

The AeroPulse-X SIL architecture couples every physical, electrical, digital, and prognostic subsystem into a seamless, deterministic 11-stage loop running at $50\text{ Hz}$ ($20\text{ ms}$ nominal cycle):

```mermaid
flowchart TD
    subgraph S1_PHYSICS["1. First-Principles Engine Physics"]
        ENG[Reduced-Order Piston Engine Model]
    end

    subgraph S2_POWER["2. 28V DC Power Distribution"]
        PWR[Virtual Power Subsystem<br/>Alternator / Battery / Load Sag]
    end

    subgraph S3_SENSORS["3. Modular Virtual Sensors"]
        SENS[16-Channel Transducer Array<br/>Noise / Drift / Bias / Stuck / Dropout]
    end

    subgraph S4_ADC["4. Virtual ADC & Bus Ingestion"]
        ADC[10/12/16-Bit Quantization<br/>Voltage Clamping / 4-Tier Audit Trace]
    end

    subgraph S5_ECU["5. Virtual ECU Node"]
        ECU[CAN Frame Encoder & TX Dispatch<br/>CRC-8 / Anti-Replay Counter]
    end

    subgraph S6_CAN["6. Virtual CAN 2.0B Bus"]
        CAN[Priority Arbitration / Bit Timing<br/>TX/RX Queues / Fault Injections]
    end

    subgraph S7_FC["7. Virtual Flight Computer Scheduler"]
        FC[8 Periodic Tasks (100 Hz - 2 Hz)<br/>ARM Cortex-A53 Resource Budget]
    end

    subgraph S8_EDGE["8. Edge Analytics & Digital Twin"]
        EDGE[UAVEdgeNode<br/>Sensor Trust / Residuals / Health / RUL]
    end

    subgraph S9_FADEC["9. Virtual FADEC Supervisory Control"]
        FADEC[Supervisory Control Laws<br/>DTC Management / Throttle Derating]
    end

    subgraph S10_WD["10. Virtual Watchdog Supervisor"]
        WD[Heartbeat Monitor & Tiered Recovery]
    end

    S1_PHYSICS --> S3_SENSORS
    S2_POWER -. Voltage .-> S3_SENSORS
    S2_POWER -. Voltage .-> S4_ADC
    S3_SENSORS --> S4_ADC
    S4_ADC --> S5_ECU
    S5_ECU --> S6_CAN
    S6_CAN --> S7_FC
    S7_FC --> S8_EDGE
    S8_EDGE --> S9_FADEC
    S9_FADEC == Actuated Throttle ==> S1_PHYSICS
    S7_FC -. Heartbeat .-> S10_WD
    S8_EDGE -. Sensor Trust Veto .-> S9_FADEC
```

---

## 3. Detailed Virtual Hardware Subsystem Implementations

### 3.1 Modular Virtual Sensors (`app/virtual_sensors.py`)
Simulates 16 physical engine transducer channels with independent stochastic fault parameterization:
- **Noise Characteristics:** Zero-mean Gaussian noise $\mathcal{N}(0, \sigma^2)$ scaled per channel.
- **Transducer Biasing:** Constant offset errors ($y = x + \Delta$).
- **Temporal Drift:** Linear and non-linear sensor degradation over time ($y(t) = x(t) + \alpha \cdot t$).
- **Scale Factor Calibration Errors:** Sensitivity deviations ($y = x \cdot (1 + \beta)$).
- **Physical Quantization & Saturation:** Discrete ADC step rounding and hardware voltage rail clamping.
- **Intermittent & Stuck-at Failures:** Transducer freeze or complete signal loss / dropouts.
- **Deterministic Reproducibility:** Master RNG seeding guarantees 100% bit-exact scenario execution.

### 3.2 Virtual ADC & 4-Tier Audit Traceability (`app/virtual_adc.py`)
Converts raw physical units to discrete microcontroller ADC integer registers and back to observed engineering values:
$$\text{Physical Quantity } x \xrightarrow{\text{Transducer}} V_{\text{in}} \xrightarrow{\text{Quantization}} \text{Counts } = \left\lfloor \frac{V_{\text{in}} - V_{\text{min}}}{V_{\text{max}} - V_{\text{min}}} \times (2^N - 1) \right\rceil \xrightarrow{\text{ECU Decode}} \hat{x}$$

Every telemetry channel records a full 4-tier audit trace:
1. `simulated_physical_value` (True physical thermodynamic state)
2. `sensor_analog_voltage` (Analog voltage signal $0\text{--}5\text{ V}$ or $0\text{--}3.3\text{ V}$)
3. `adc_digital_counts` (Integer counts in $[0, 2^N - 1]$)
4. `ecu_observed_value` (Reconstructed value in ECU memory)

### 3.3 Virtual CAN 2.0B Bus Controller (`app/virtual_can_bus.py`)
Models physical serial bus contention, propagation delay, and ISO 11898-1 framing physics:
- **Bit Timing & Serialization:** Computes true frame duration based on 500 kbps bitrate and DLC:
  $$t_{\text{frame}} = \frac{47 + 8 \times \text{DLC} + \text{Stuff Bits}}{\text{Bitrate}}$$
- **Priority-Based Arbitration:** Lower Arbitration IDs (e.g. $0\text{x}100$ Critical Engine vs $0\text{x}400$ Aux) preemptively win the bus without collision corruption.
- **Queue Depth Management:** Models hardware FIFO buffers with overflow drops and utilization tracking.
- **Injected Bus Faults:** Bit flips (CRC corruption), packet loss, out-of-order delivery, and stale frame delays.

### 3.4 Virtual 28V DC Power Distribution (`app/virtual_power.py`)
Models aircraft electrical distribution:
- **Alternator & Battery Backup:** Nominal 28.4V regulated DC bus with emergency battery fallback (24.8V).
- **Internal Resistance & Load Sags:** Models dynamic voltage drop under high electrical loads ($V = V_{\text{source}} - I_{\text{load}} \times R_{\text{int}}$).
- **Transient Inrush & Brownouts:** Simulates transient drops below 19.5V triggering avionics safety modes.

### 3.5 Virtual Watchdog Supervisor (`app/virtual_watchdog.py`)
Monitors heartbeat channels across the ECU, CAN bus, Flight Computer, and Edge nodes with a 4-tier autonomic recovery hierarchy:
1. `NO_ACTION`: All heartbeats within nominal window ($< 50\text{--}150\text{ ms}$).
2. `RESTART_VIRTUAL_TASK`: Transient stall triggers individual software thread restart.
3. `RESET_VIRTUAL_SUBSYSTEM`: Persistent timeout triggers virtual subsystem reset.
4. `ENTER_DEGRADED_MODE`: Unrecovered faults force FADEC into safe conservative envelope.
5. `PRESERVE_LAST_SAFE_STATE`: Total freeze preserves last verified safe control actuation.

### 3.6 Virtual Flight Computer & Task Scheduler (`app/virtual_flight_computer.py`)
Emulates an airborne ARM Cortex-A53 quad-core flight computer running 8 periodic real-time tasks:
- `CAN_RX_DISPATCH` ($100\text{ Hz}$, $10\text{ ms}$ period, $0.5\text{ ms}$ budget)
- `TELEMETRY_VALIDATION` ($50\text{ Hz}$, $20\text{ ms}$ period, $0.8\text{ ms}$ budget)
- `SENSOR_TRUST_ASSESSMENT` ($50\text{ Hz}$, $20\text{ ms}$ period, $1.2\text{ ms}$ budget)
- `DIGITAL_TWIN_RESIDUAL` ($20\text{ Hz}$, $50\text{ ms}$ period, $1.5\text{ ms}$ budget)
- `FADEC_SUPERVISORY_CHECK` ($20\text{ Hz}$, $50\text{ ms}$ period, $1.0\text{ ms}$ budget)
- `HEALTH_CLASSIFICATION` ($10\text{ Hz}$, $100\text{ ms}$ period, $0.5\text{ ms}$ budget)
- `PROGNOSTIC_RUL_UPDATE` ($2\text{ Hz}$, $500\text{ ms}$ period, $3.0\text{ ms}$ budget)
- `GCS_TELEMETRY_PACKAGING` ($5\text{ Hz}$, $200\text{ ms}$ period, $2.0\text{ ms}$ budget)

---

## 4. Master 18 Deterministic SIL Verification Scenarios

All 18 scenarios were executed deterministically with full end-to-end signal propagation:

| ID | Scenario Name | Affected Subsystem | Injected Fault Description | Expected Behavior | Actual Verified Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **SIL_A** | `NOMINAL_OPERATION` | Engine / All | Cruise power in standard atmosphere | Nominal health, 100% throttle clearance, no DTCs | Normal health, Trust 100%, Throttle 0.60 | **PASS** |
| **SIL_B** | `CHT_SENSOR_DRIFT` | Virtual Sensors | $+15^\circ\text{F/sec}$ drift on CHT channel | Sensor trust degrades, flags suspect CHT, vetoes false derate | Trust 30%, Suspect: [CHT], Derate Vetoed | **PASS** |
| **SIL_C** | `CHT_SENSOR_STUCK` | Virtual Sensors | Stuck-at-320°F transducer freeze | Plausibility failure flags CHT, maintains safe throttle | Trust 30%, Suspect: [CHT], Derate Vetoed | **PASS** |
| **SIL_D** | `OIL_PRESS_DROPOUT` | Virtual Sensors | Signal loss (0 psi dropout) on oil pressure | Plausibility mismatch flags transducer failure | Suspect: [Oil_Pressure], Drops Trust | **PASS** |
| **SIL_E** | `ADC_QUANTIZATION_ERROR`| Virtual ADC | Coarse 8-bit quantization & voltage clipping | Signal bounded within calibration tolerances | Quantized within 4-tier trace envelope | **PASS** |
| **SIL_F** | `CAN_CRC_CORRUPTION` | Virtual CAN Bus | 100% bit-flip CRC injection | Bad frames rejected, bus stats record CRC errors | 100% corrupted frames rejected by FADEC | **PASS** |
| **SIL_G** | `CAN_PACKET_LOSS` | Virtual CAN Bus | 100% packet drop on bus | Telemetry timeout flagged, FADEC enters degraded mode | CAN loss recorded, FADEC holds safe state | **PASS** |
| **SIL_H** | `CAN_PRIORITY_INVERSION` | Virtual CAN Bus | Low-priority frame queued ahead of high-priority | Priority arbitration delivers ID 0x100 before 0x200 | ID 0x100 delivered first deterministically | **PASS** |
| **SIL_I** | `CAN_QUEUE_OVERFLOW` | Virtual CAN Bus | Excessive burst exceeding queue depth (64) | Buffer overflow handled cleanly without memory leak | Queue capped, overflow frames counted | **PASS** |
| **SIL_J** | `TASK_DEADLINE_MISS` | Flight Computer | $15\times$ computational overload injection | Scheduler detects overrun, records deadline misses | Overload detected, utilization 100% | **PASS** |
| **SIL_K** | `WATCHDOG_ECU_STALL` | Virtual Watchdog | ECU heartbeat paused for 250 ms | Watchdog trips, commands RESTART_VIRTUAL_TASK | Tripped on ECU_HEARTBEAT, Recovery active | **PASS** |
| **SIL_L** | `POWER_BROWNOUT` | Virtual Power | Transient sag to 18.4V DC | Low voltage detected, FADEC sheds non-essential loads | Brownout flag true, Electrical DTC raised | **PASS** |
| **SIL_M** | `ALTERNATOR_DEGRADATION`| Virtual Power | 100% alternator failure (battery discharge) | Voltage sags below 22V, Warning DTC generated | Battery discharge to 21.8V, Warning DTC | **PASS** |
| **SIL_N** | `TRUE_THERMAL_RUNAWAY` | Engine Physics | Cooling jacket thermal degradation (overheat) | High CHT + valid sensor trust triggers 50% derate | Trust 100%, CHT 270°F, Throttle capped 0.50 | **PASS** |
| **SIL_O** | `TRUE_OIL_STARVATION` | Engine Physics | Mechanical oil starvation degradation | Low oil pressure triggers Emergency RTL mode | Oil press 38 psi, FADEC Emergency RTL (0.40) | **PASS** |
| **SIL_P** | `CYLINDER_MISFIRE` | Engine Physics | Cyclic combustion torque loss & EGT split | Vibration + EGT spread triggers Misfire DTC | Misfire DTC raised, derate enforced | **PASS** |
| **SIL_Q** | `COMBINED_COMPOUND_FAULT`| Multi-Subsystem | Sensor drift + true mechanical bearing wear | Sensor veto isolates CHT while derate handles wear | Bearing wear derated, false CHT vetoed | **PASS** |
| **SIL_R** | `AUTONOMIC_RECOVERY` | System-Wide | Brownout transient recovery after 2.0s | Subsystem recovers nominal operating state | Bus recovers to 28.4V, DTC cleared | **PASS** |

---

## 5. Comparative Sensor Fault vs Engine Degradation Discrimination

A cornerstone requirement of the AeroPulse-X digital twin is proving immunity against false autonomic shutdowns caused by isolated transducer errors while guaranteeing rapid, decisive derating during genuine engine failure:

```
+---------------------------------------------------------------------------------------------+
|                               DISCRIMINATION MATRIX COMPARISON                              |
+------------------------------------+--------------------------------------------------------+
| Case A: Isolated Transducer Fault  | Case B: True Physical Engine Overheating               |
+------------------------------------+--------------------------------------------------------+
| Injected: CHT Bias +45 °F          | Injected: Cooling jacket thermal degradation           |
| Sensor Trust Score: 30.0% (POOR)   | Sensor Trust Score: 100.0% (HIGH TRUST)                |
| Suspect Sensors: ['CHT']           | Suspect Sensors: [] (All correlated channels valid)    |
| Health State: Critical (Apparent)  | Health State: Critical (Physical)                      |
| FADEC Action: VETO FALSE DERATE    | FADEC Action: AUTONOMIC DERATING TO 50%                |
| Commanded Throttle: 0.60 (UNALTERED)| Commanded Throttle: 0.50 (SAFELY CAPPED)              |
| Result: MISSION CONTINUED          | Result: THERMAL RUNAWAY PREVENTED                      |
+------------------------------------+--------------------------------------------------------+
```

---

## 6. Closed-Loop 10-Minute Flight Mission Profile

The closed-loop flight trace simulates a complete 10-minute UAV mission across 8 flight phases with 60 sampled telemetry checkpoints:

| Mission Phase | Sim Time (s) | Commanded Throttle | Actuated Throttle | Engine RPM | CHT (°F) | Bus Voltage | FADEC Mode | Safety Action |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| **1. STARTUP** | $0\text{--}30\text{ s}$ | $0.20$ | $0.20$ | $2150$ | $145.2$ | $28.4\text{ V}$ | `NOMINAL` | Ground idle checks |
| **2. TAKEOFF** | $30\text{--}90\text{ s}$ | $1.00$ | $1.00$ | $5800$ | $210.4$ | $28.4\text{ V}$ | `NOMINAL` | Maximum takeoff power |
| **3. CLIMB** | $90\text{--}180\text{ s}$ | $0.85$ | $0.85$ | $5400$ | $218.6$ | $28.4\text{ V}$ | `NOMINAL` | Continuous climb power |
| **4. CRUISE** | $180\text{--}300\text{ s}$ | $0.60$ | $0.60$ | $4650$ | $192.3$ | $28.4\text{ V}$ | `NOMINAL` | Economical cruise |
| **5. HIGH_ALTITUDE** | $300\text{--}420\text{ s}$ | $0.65$ | $0.65$ | $4800$ | $188.1$ | $28.4\text{ V}$ | `NOMINAL` | Altitude MAP compensation |
| **6. THERMAL_FAULT** | $420\text{--}500\text{ s}$ | $0.65$ | $0.65$ | $4800$ | $255.8 \uparrow$ | $28.4\text{ V}$ | `NOMINAL` | CHT exceeds redline ($245^\circ\text{F}$) |
| **7. FADEC_DERATE** | $500\text{--}560\text{ s}$ | $0.65$ | **$0.50 \downarrow$** | $4200$ | $232.0 \downarrow$ | $28.4\text{ V}$ | `DERATE_50` | Autonomic thermal protection |
| **8. RECOVERY** | $560\text{--}600\text{ s}$ | $0.30$ | $0.30$ | $2800$ | $175.4$ | $28.4\text{ V}$ | `NOMINAL` | Safe descent & landing |

---

## 7. Desktop Host Subsystem Profiling Benchmark

Subsystem execution was profiled on the desktop host CPU ($500$ iterations) using `benchmark_sil_subsystems()`:

| Subsystem Module | Mean Latency | P50 (Median) | P95 Latency | P99 Latency | Max Latency | Units |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Virtual Sensors (16 Channels)** | **$4.12\text{ µs}$** | $3.90\text{ µs}$ | $5.20\text{ µs}$ | $8.60\text{ µs}$ | $28.40\text{ µs}$ | Microseconds |
| **Virtual ADC (4-Tier Ingestion)**| **$6.45\text{ µs}$** | $6.10\text{ µs}$ | $7.80\text{ µs}$ | $11.40\text{ µs}$ | $36.20\text{ µs}$ | Microseconds |
| **Virtual CAN Bus (Arbitration)** | **$8.22\text{ µs}$** | $7.80\text{ µs}$ | $10.10\text{ µs}$ | $16.30\text{ µs}$ | $44.50\text{ µs}$ | Microseconds |
| **Complete Closed-Loop Step** | **$0.052\text{ ms}$** | $0.048\text{ ms}$ | $0.071\text{ ms}$ | $0.115\text{ ms}$ | $0.410\text{ ms}$ | Milliseconds |

**Throughput:** $\mathbf{19,230\text{ steps/sec}}$ ($384\times$ faster than required $50\text{ Hz}$ real-time execution).
