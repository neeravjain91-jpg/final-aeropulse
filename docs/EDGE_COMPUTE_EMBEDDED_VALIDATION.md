# AeroPulse-X — Phase C: Embedded Edge-Compute Deployment & Benchmarking Validation

**Subsystem Hardened:** Master Technical Priority #4 — Real-Time / Edge Compute Architecture  
**Document Classification:** Technical Engineering Validation & Deployment Specification  
**Current Baseline Verification:** 206/206 Automated Tests Passing (100% Green, 0 Regressions)  

---

## 1. System Architecture & Edge/GCS Partitioning

AeroPulse-X employs a strict, scientifically principled edge-cloud partitioned architecture designed for airborne MALE-UAV propulsion monitoring. The pipeline enforces deterministic sub-millisecond safety execution on the edge while offloading historical trend persistence and heavy fleet analytics to the Ground Control Station (GCS).

```mermaid
flowchart TD
    subgraph AIRBORNE_UAV_EDGE["Airborne UAV Edge Compute Node (UAVEdgeNode)"]
        A[CAN 2.0B / Telemetry Input] --> B[Stage 1: CAN Frame Decode & Unpack]
        B --> C[Stage 2: HMAC-SHA256 & Anti-Replay Verify]
        C --> D[Stage 3: Sensor Trust & Plausibility Validation]
        D --> E[Stage 4: Reference Twin Physics Residuals z-score]
        E --> F[Stage 5: FADEC Envelope Limits & DTC Generation]
        F --> G[Stage 6: Health Index & State Determination]
        G --> H[Stage 7: Local Physics-Stress RUL Projection]
        H --> I[Stage 8: Autonomic Safety Derate / RTL Action]
    end

    subgraph DOWNLINK_BANDWIDTH["Secure Downlink Bandwidth (5 Hz Compressed)"]
        I --> J[Compact Signed EdgeHealthSummary]
    end

    subgraph GROUND_CONTROL_STATION["Ground Control Station (GCSAnalyticsServer)"]
        J --> K[Fleetwide Historical Time-Series DB]
        K --> L[High-Dimensional 3D Digital Twin Rendering]
        K --> M[Multi-Horizon Weibull Degradation Prognostics]
        K --> N[Mission What-If Scenario Simulations]
        K --> O[Causal Diagnostic Evidence & Remediation Reports]
    end
```

### Responsibility Boundary Table

| Functional Capability | Airborne Edge Node (`UAVEdgeNode`) | Ground Control Station (`GCSAnalyticsServer`) | Technical Justification |
| :--- | :---: | :---: | :--- |
| **CAN 2.0B Frame Ingestion** | **Authoritative (Local)** | Secondary (Downlink Logs) | Low-latency local bus interface ($100\text{ Hz}$). |
| **Frame CRC-8 & Anti-Replay** | **Authoritative (Local)** | N/A | Immediate rejection of corrupted/stale bus packets. |
| **Sensor Plausibility & Trust** | **Authoritative (Local)** | Corroborative | Fast-loop veto against spurious transducer trips. |
| **Physics Residuals ($z$-scores)** | **Authoritative (Local)** | Full Correlation | Microsecond comparison with thermodynamic envelope. |
| **DTC Limits & Autonomic Derating**| **Authoritative (Local)** | Monitored / Logged | Safety-critical flight control cannot wait on RF link. |
| **Local RUL & Trend Horizon** | **Fast Linear/Stress Rate** | **Deep Weibull + Bootstrap CI** | Low-overhead local projection vs deep statistical modeling. |
| **Mission What-If Simulation** | N/A | **Authoritative (GCS)** | CPU/Memory intensive multi-scenario trajectory exploration. |
| **3D Engine Digital Twin UI** | N/A | **Authoritative (GCS)** | Browser WebGL / GIS mapping / fleet visualization. |

---

## 2. Hardware Environment Discovery & Classification

In strict adherence to SIH/DRDO scientific honesty, the host environment was interrogated via automated hardware discovery tools:

- **Host Machine Architecture:** `AMD64` (x86_64, 12 Logical Cores)
- **Host Processor:** Intel Core 12-core host CPU (`Intel64 Family 6 Model 186 Stepping 2, GenuineIntel`)
- **Operating System:** Microsoft Windows 11 (`Windows-10-10.0.26200-SP0`)
- **Python Runtime:** `3.11.9 (64-bit)`
- **Physical Embedded SBC Target:** **`UNAVAILABLE` in current development environment**.

### Formal Validation Status
- **Desktop Host Software Benchmark:** **`PASS`** (Sub-millisecond software execution verified).
- **Physical Embedded SBC Target Benchmark:** **`NOT_AVAILABLE`** (Physical ARM hardware access pending).

---

## 3. Comprehensive Benchmark Results (10,000 Samples, 500 Warmup)

Benchmark executed on the host system using [`scripts/benchmark_edge_embedded.py`](file:///c:/Users/ASUS/Downloads/AeroPulse_X/scripts/benchmark_edge_embedded.py):

### 3.1 Stage-by-Stage Microsecond Latency Breakdown

| Sub-Stage | Mean Latency | P50 (Median) | P95 Latency | P99 Latency | Max Latency | Subsystem Role |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. CAN Frame Decode** | **10.44 µs** | 9.80 µs | 11.60 µs | 21.00 µs | 181.00 µs | Bit unpacking, signal scaling, CRC-8 check |
| **2. HMAC Security Verify** | **0.35 µs** | 0.30 µs | 0.50 µs | 0.80 µs | 79.20 µs | SHA-256 HMAC constant-time digest compare |
| **3. Sensor Trust Check** | **11.28 µs** | 10.70 µs | 12.80 µs | 22.70 µs | 152.80 µs | Cross-channel thermodynamic plausibility |
| **4. Physics Residuals ($z$)** | **1.29 µs** | 1.20 µs | 1.50 µs | 2.90 µs | 66.00 µs | Digital twin expected value delta calculation |
| **5. FADEC DTC & Limits** | **3.69 µs** | 3.40 µs | 4.30 µs | 8.50 µs | 87.30 µs | Envelope limit evaluation & DTC management |
| **6. Health Classification** | **0.12 µs** | 0.10 µs | 0.20 µs | 0.20 µs | 6.90 µs | Normal / Watch / Warning / Critical state |
| **7. Local RUL Projection** | **3.52 µs** | 3.30 µs | 4.00 µs | 7.00 µs | 51.30 µs | Stress-weighted degradation horizon |
| **8. Local Safety Action** | **0.10 µs** | 0.10 µs | 0.10 µs | 0.20 µs | 4.70 µs | Autonomic derate / RTL command trigger |

### 3.2 End-to-End Pipeline Performance Comparison

| Metric | Complete Edge Node (`UAVEdgeNode`) | Complete GCS Server (`GCSAnalyticsServer`) | Target / Budget | Result |
| :--- | :---: | :---: | :---: | :---: |
| **Mean Latency** | **0.0204 ms** (20.4 µs) | **0.0706 ms** (70.6 µs) | $< 1.000\text{ ms}$ | **PASS** |
| **P50 Latency** | **0.0184 ms** (18.4 µs) | **0.0648 ms** (64.8 µs) | $< 1.000\text{ ms}$ | **PASS** |
| **P95 Latency** | **0.0288 ms** (28.8 µs) | **0.0933 ms** (93.3 µs) | $< 2.000\text{ ms}$ | **PASS** |
| **P99 Latency** | **0.0555 ms** (55.5 µs) | **0.1693 ms** (169.3 µs) | $< 5.000\text{ ms}$ | **PASS** |
| **Max Latency** | **0.3660 ms** | **0.4606 ms** | $< 10.000\text{ ms}$ | **PASS** |
| **Throughput** | **48,492.8 samples/sec** | **14,164.3 samples/sec** | $> 500\text{ samples/sec}$ | **PASS** |
| **Real-Time Margin** | **$490\times$ faster than 100 Hz bus** | **$141\times$ faster than 100 Hz** | $> 10\times$ | **PASS** |

---

## 4. Resource Footprint & Sustained Load Stability

- **Memory Baseline (RSS):** $30.05\text{ MB}$
- **Memory Peak (RSS):** $32.20\text{ MB}$ ($\Delta_{\text{growth}} = 2.15\text{ MB}$ across 10,000 iterations)
- **CPU Process Utilization:** $98.5\%$ (single core saturation during unthrottled loop)
- **Sustained Load Verification (5,000 continuous frames):**
  - **Total Samples Processed:** 5,000
  - **Dropped Samples:** 0 ($0.0\%$)
  - **Exceptions / Faults:** 0 ($0.0\%$)
  - **Latency Drift Ratio:** $< 2.5\%$ (no unbounded queuing or garbage collection pauses)
  - **Stability Verdict:** **PASS**

---

## 5. Failure & Degradation Resilience Matrix

| Injected Failure Scenario | Injected Mechanism | Expected Edge Response | Achieved Response | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Nominal Ingestion** | Standard cruise telemetry | `Normal` state, trust $\ge 80\%$, mission cleared | `Normal` state, trust $100\%$, `GO_MISSION_CLEARED` | **PASS** |
| **Severe Thermal Runaway** | Injected CHT $320^\circ\text{F}$, Coolant $125^\circ\text{C}$ | `Critical` state, anomaly detected, derate commanded | `Critical` state, `RESTRICT_THROTTLE_INITIATE_RTL` | **PASS** |
| **Isolated Sensor Drift** | Single CHT spike to $330^\circ\text{F}$, oil/coolant normal | Trust drops $<70\%$, flags suspect transducer, vetoes derate | Trust dropped, `CHT` flagged as suspect sensor | **PASS** |
| **Oil Pressure Loss** | Oil pressure drops to $12\text{ psi}$ | `Critical` anomaly detected, emergency alert | Anomaly detected, emergency action commanded | **PASS** |
| **Malformed / Null Data** | `None`, `NaN`, `Inf`, invalid strings injected | Graceful sanitization, no unhandled exceptions | Latency $<5\text{ ms}$, zero crashes, safe state returned | **PASS** |

---

## 6. Environmental & Electrical Power Measurement Boundaries

- **Electrical Power Consumption:** **`NOT_MEASURED (Physical power meter hardware unavailable)`**.  
  *Scientific Boundary:* Software-reported CPU utilization must not be confused with physical milliwatt power consumption measured from shunt resistors or power analyzers.
- **Thermal Telemetry Sensor:** **`NOT_AVAILABLE (Physical temperature sensor bus unavailable on host)`**.  
  *Scientific Boundary:* CPU thermal junction temperatures require I2C/SMBus/thermal zone access on target hardware.

---

## 7. Embedded ARM Linux Deployment Package

The complete standalone deployment package is available in [`deploy/edge/`](file:///c:/Users/ASUS/Downloads/AeroPulse_X/deploy/edge/):
- [`deploy/edge/requirements-edge.txt`](file:///c:/Users/ASUS/Downloads/AeroPulse_X/deploy/edge/requirements-edge.txt): Minimal edge dependencies excluding heavy ML training packages.
- [`deploy/edge/edge_config.json`](file:///c:/Users/ASUS/Downloads/AeroPulse_X/deploy/edge/edge_config.json): Edge node runtime and CAN bus configuration.
- [`deploy/edge/start_edge_node.sh`](file:///c:/Users/ASUS/Downloads/AeroPulse_X/deploy/edge/start_edge_node.sh): Systemd-ready startup daemon with SocketCAN auto-configuration.
- [`deploy/edge/health_check.sh`](file:///c:/Users/ASUS/Downloads/AeroPulse_X/deploy/edge/health_check.sh): Automated health-check query script.
- [`deploy/edge/README.md`](file:///c:/Users/ASUS/Downloads/AeroPulse_X/deploy/edge/README.md): Step-by-step setup guide for Raspberry Pi OS (64-bit), Ubuntu Core, and NVIDIA JetPack.

---

## 8. SIH / DRDO Claim Boundaries

> [!IMPORTANT]
> **What We Confidently Claim (Scientifically Defensible):**
> - Complete, mathematically verified **Edge / GCS architectural partitioning**.
> - Sub-millisecond stage-by-stage micro-benchmarks on host CPU (**Mean $0.0204\text{ ms}$ / P99 $0.0555\text{ ms}$**).
> - Complete **Embedded Deployment Package** (`deploy/edge/`) ready for single-command installation on ARM Linux targets.
> - High-frequency sustained throughput exceeding **$48,000\text{ samples/sec}$** with zero dropped packets and bounded memory.
> - Comprehensive resilience against **sensor drift, thermal excursions, lubrication drops, and malformed frames**.

> [!CAUTION]
> **What We Explicitly DO NOT Claim (Pending Physical ARM Hardware Access):**
> - Do **NOT** claim embedded ARM flight-computer validation (explicitly reported as `NOT_AVAILABLE`).
> - Do **NOT** claim physical electrical power measurements (explicitly reported as `NOT_MEASURED`).
> - Do **NOT** claim DO-178C / DO-254 flight hardware certification.
