# AeroPulse — Required Data Resource Specification

## Purpose

This document defines the data resources required for the AeroPulse MALE-UAV aero-piston Digital Twin prototype and separates:

- real operational telemetry,
- physics/simulation data,
- experimental vibration/fault data,
- operating-envelope reference data,
- methodology-only research resources.

**Do not concatenate these sources blindly into one training table.** Every record must retain provenance, engine identity, source type, and validation role.

---

## 1. Primary real-data source — NASA ACES

**Role:** Real operational telemetry, healthy/health-state classification baseline, operating-envelope validation.

**Required resource:**
- ACES telemetry dataset already used by the repository.
- Current project benchmark file:
  `FINAL_DATASET/ACES/aces_health.csv`

**Required identity fields:**
- `Flight`
- timestamp/sample ordering field when available
- engine/aircraft identifier when available
- source/provenance

**Required telemetry channels:**
- Engine_RPM
- EGT1
- EGT2
- EGT3
- CHT
- Fuel_Flow
- Oil_Temp
- Oil_Pressure
- Battery_Voltage
- Battery_Current
- Alternator_Temp
- EFI_Fuel_Temp
- EFI_Water_Temp
- MAP_Injector
- Operating_State

**Use:**
- leakage-safe health-state classification
- real operating-envelope characterization
- held-out flight validation
- temporal feature validation

**Important:** `Health_State` is a target for supervised evaluation, not an input feature. Ground-truth degradation labels must never be used as health/RUL inputs.

---

## 2. Engine Digital-Twin / physics-generated telemetry

**Role:** Controlled coverage of operating conditions and faults that are sparse or absent in real ACES telemetry.

Generate records from the existing engine model and mission simulator rather than inventing independent sensor noise.

### Required operating dimensions

- RPM
- throttle
- engine load
- MAP/manifold pressure
- ambient temperature
- ambient pressure
- altitude
- vertical speed
- fuel flow
- CHT
- EGT
- oil pressure
- oil temperature
- vibration
- battery/alternator state

### Required mission/environment cases

- idle
- cruise
- high-load operation
- takeoff/high-throttle transition
- landing/descent
- rapid throttle transitions
- altitude changes
- hot-weather operation
- endurance/degraded operation

### Required fault trajectories

Fault injection must be causal and physically coupled.

Minimum fault families:

- misfire
- injector abnormality
- lubrication/oil-pressure degradation
- overheating
- combustion instability
- abnormal vibration
- sensor drift
- sensor bias/failure
- battery/alternator abnormality

For each physical fault, record:

- fault type
- onset time
- severity
- degradation trajectory
- affected subsystem
- observable sensor response
- engine profile
- simulation seed/version
- provenance = `synthetic_physics`

**Do not use `Degradation_Severity` or equivalent ground truth as an input to the health model.**

---

## 3. Experimental vibration / misfire resource

**Source basis:** The provided Rotax 912 ULS cylinder-misfire experimental study.

**Role:** Constrain and validate the vibration/misfire branch.

The study supports a dedicated vibration-analysis methodology involving:

- high-frequency vibration measurement
- VMD / modal decomposition
- IMF-derived features
- linear statistical features
- recurrence-quantification features
- classification of healthy vs cylinder fuel-disable/misfire conditions

### Required data if the underlying experimental measurements are available

- vibration waveform
- sampling rate
- engine RPM
- MAP/load condition
- cylinder/fault label
- operating condition
- recording/window identifier

### Derived features

Linear:
- mean
- median
- RMS
- kurtosis
- skewness

RQA:
- determinism
- laminarity
- entropy
- maximum diagonal length
- maximum vertical length

**Do not fabricate high-frequency vibration waveforms.**

If only the paper is available and the raw measurements are unavailable, retain this resource as methodology/reference data rather than training rows.

---

## 4. Real piston-engine operating-envelope reference

**Source basis:** The provided real-operating-condition piston-engine study using a Rotax 912 ULT installation.

**Role:** Define plausible temporal/operating relationships and validate simulation envelopes.

Extract/use:

- RPM distributions
- MAP distributions
- idle/cruise/high-load regions
- takeoff/landing behavior
- rate-of-change characteristics
- available thermal/pressure channels
- flight-phase transitions

Derived temporal features for AeroPulse:

- dRPM/dt
- d²RPM/dt²
- dMAP/dt
- dCHT/dt
- dEGT/dt
- dOil_Temp/dt
- dOil_Pressure/dt
- short-window trends

**Important:** This is reference evidence for operating behavior. Do not relabel its measurements as NASA ACES data and do not assume the engine/airframe is identical to ACES.

---

## 5. Engine diagnostic / monitoring reference

**Source basis:** The provided engine diagnostic/monitoring research resource.

**Role:** Feature design, sensor cross-checking, and flight-phase monitoring.

Useful channels/relationships include:

- OAT
- pressure/altitude
- MAP
- MAT
- per-cylinder EGT
- oil temperature
- oil pressure
- crankcase/head-cover pressure
- RPM
- vibration
- CHT cooling rate
- EGT span
- battery voltage/ripple
- fuel consumption/pressure

Use this resource to implement **multi-sensor consistency checks**, not as an independent training dataset unless its underlying raw data is actually available.

---

## 6. Multi-fidelity Digital Twin / residual methodology

**Source basis:** The provided Digital Twin + FMEA + residual-generation research resource.

**Role:** Architecture and feature methodology.

Required conceptual pipeline:

`fault state → physical parameter change → engine physics → sensor response → residual → diagnosis`

Useful concepts:

- paired healthy Digital Twin
- physics-informed residuals
- FMEA-driven fault injection
- degradation trajectories
- interpretable fault reports
- temporal residual features

Residuals used in AeroPulse must be clearly labelled according to how they were produced:

- `healthy_reference_residual`
- `engine_model_residual`
- `paired_twin_residual`

Do not describe statistical healthy-reference residuals as high-fidelity paired-twin residuals.

---

## 7. Required provenance schema

Every derived dataset should carry:

| Field | Meaning |
|---|---|
| `source_id` | Stable source identifier |
| `source_type` | real / synthetic_physics / experimental / reference |
| `engine_profile` | Exact engine profile |
| `aircraft_profile` | Aircraft/UAV profile when known |
| `flight_id` | Flight/run identifier |
| `sample_id` | Sample/window identifier |
| `timestamp` | Original time when available |
| `operating_state` | Operating/flight phase |
| `fault_type` | Fault class or healthy |
| `fault_onset` | Fault onset marker when applicable |
| `fault_severity` | Metadata only; never an unintended model input |
| `simulation_seed` | Synthetic reproducibility |
| `generator_version` | Data-generation version |
| `unit_system` | Explicit units |
| `provenance_notes` | Source/assumption notes |

---

## 8. Dataset separation required for validation

The repository should maintain logical separation:

```
FINAL_DATASET/
├── ACES/                  # real operational telemetry
├── ENGINE_SIM/            # physics-generated telemetry
├── FAULT_INJECTION/       # controlled synthetic faults
├── VIBRATION_MISFIRE/     # experimental/raw vibration when available
├── OPERATING_ENVELOPE/    # reference measurements
└── manifests/             # provenance and dataset definitions
```

Do not merge these into a single file until the training protocol explicitly defines source weighting, domain adaptation, and provenance.

---

## 9. Validation protocol

### Classification

Use flight/run-level separation.

Never allow samples from the same flight/run to appear in both train and test.

Report:

- Accuracy
- Balanced Accuracy
- Macro-F1
- Critical Precision
- Critical Recall
- Critical F1
- per-class F1
- false-negative rate
- inference latency
- model size

### Physics validation

Report:

- MAE
- RMSE
- residual bias
- directional fault response
- operating-envelope coverage
- cross-sensor consistency

### RUL

Report separately:

- RUL error
- monotonicity
- uncertainty coverage
- early-warning lead time

Do not use C-MAPSS turbofan results as direct aero-piston RUL validation.

---

## 10. Resource priority for the prototype

### Tier 1 — Required now

1. NASA ACES real telemetry
2. Existing AeroPulse physics/mission simulator
3. Causal synthetic fault trajectories
4. Temporal/cross-sensor feature generation
5. Provenance metadata

### Tier 2 — Strongly recommended

6. Experimental vibration/misfire data, if raw measurements can be obtained
7. Operating-envelope measurements from the provided piston-engine study
8. Flight-phase-specific monitoring rules

### Tier 3 — Methodology/reference only

9. Digital Twin/FMEA/residual research papers
10. Diagnostic-monitoring research papers

**A paper is not a dataset unless its underlying machine-readable measurements are available and legally usable.**

---

## 11. Integrity rules

1. Never use ground-truth degradation severity as a health-model feature.
2. Never mix engine profiles.
3. Never mix real and synthetic records without provenance.
4. Never claim synthetic performance as real-flight performance.
5. Never transfer published classification accuracy to AeroPulse.
6. Never fabricate vibration measurements.
7. Never silently convert units.
8. Never split individual samples randomly when flight/run grouping is available.
9. Keep the held-out real-flight test set untouched during feature/model selection.
10. Record the exact dataset version and code commit for every benchmark.

---

## Current implementation target

The immediate Part-3 objective is **not to add every available resource to training**.

It is to establish a reproducible data layer in which:

**real ACES telemetry + physically coupled simulation + experimentally grounded fault features + operating-envelope constraints**

can be evaluated independently and then combined only when a leakage-safe benchmark demonstrates a benefit.
