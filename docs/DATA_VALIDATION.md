# Data Quality & Scientific Validation Methodology

## 1. Automated Validation Suite (`app/data_validator.py`)
Every generated dataset or corpus is subjected to automated auditing against 7 rigorous criteria:

1. **Completeness & Numerical Integrity**:
   - Zero `NaN`, `Inf`, or `null` values in required canonical telemetry fields.
2. **Physical Bounds Plausibility**:
   - RPM $\in [0, 7000]$
   - Throttle $\in [0.0, 1.0]$
   - Ambient Temp $\in [-60, +80]^\circ\text{C}$
   - CHT $\in [0, 350]^\circ\text{C}$
   - Oil Pressure $\in [0, 150]\text{ psi}$
   - Bus Voltage $\in [0, 40]\text{ V}$
   - Health Index $\in [0.0, 100.0]$
3. **Temporal Monotonicity & Continuity**:
   - Strict timestamp progression: $t_{k+1} > t_k$.
   - Zero duplicate timestamps within any single trajectory.
4. **Causal Directional Coupling**:
   - Verifies that thermal wear increases CHT, lubrication wear reduces oil pressure, and misfire increases vibration.
5. **Sensor vs Engine Fault Separation**:
   - Verifies that pure transducer faults lower `sensor_trust` while leaving `health_index` unaffected ($H \ge 90.0$).
6. **Mathematical RUL Ground-Truth Exactness**:
   - Verifies that $y_{\text{true}}(t) = \max(0, t_{\text{failure}} - t)$ holds across all degradation steps.
7. **Trajectory-Level Partitioning & Leakage Audit**:
   - Partitions train and test sets strictly by `trajectory_id`.
   - Formally audits that $\mathcal{T}_{\text{train}} \cap \mathcal{T}_{\text{test}} = \emptyset$ to guarantee zero adjacent time-step leakage.
