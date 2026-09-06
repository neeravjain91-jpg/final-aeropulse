# SENSOR FAULT VS ENGINE FAULT ISOLATION VALIDATION

**Objective**: Discriminate between true mechanical/thermodynamic degradation and isolated instrument transducer failures.

---

## 1. Benchmark Scenarios & Empirical Isolation Results

| Scenario ID & Description | Injected State | True Root Category | Isolated Category | Sensor Trust Score | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Scenario A**: Thermal Overheating | CHT, EGT, Coolant, Oil all +3.0σ | **ENGINE_FAULT** | **ENGINE_FAULT** | 100.0 (Trusted) | **PASS** |
| **Scenario B**: CHT Sensor Drift | CHT +3.2σ, EGTs & Coolant < 0.3σ | **SENSOR_FAULT** | **SENSOR_FAULT** | 30.0 (Suspect) | **PASS** |
| **Scenario C**: CHT Sensor Stuck Spike | CHT +5.0σ, EGTs & Coolant < 0.3σ | **SENSOR_FAULT** | **SENSOR_FAULT** | 30.0 (Suspect) | **PASS** |
| **Scenario D**: Injector Degradation | Fuel Flow -3.0σ, MAP +2.8σ, EGT spread | **ENGINE_FAULT** | **ENGINE_FAULT** | 100.0 (Trusted) | **PASS** |
| **Scenario E**: Water Temp Sensor Bias | EFI Water Temp +4.0σ, CHT/EGT/Oil < 0.2σ | **SENSOR_FAULT** | **SENSOR_FAULT** | 25.0 (Suspect) | **PASS** |
| **Scenario F**: Misfire Combustion | EGT1 -3.5σ, Vibration +3.2σ, RPM -1.8σ | **ENGINE_FAULT** | **ENGINE_FAULT** | 60.0 (Check) | **PASS** |
| **Scenario G**: Vibration Transducer Spike | Vibration +4.5σ, RPM/Oil_P/EGT < 0.2σ | **SENSOR_FAULT** | **SENSOR_FAULT** | 30.0 (Suspect) | **PASS** |

---

## 2. Summary Metrics

- **Total Isolation Scenarios Evaluated**: 7
- **Correct Root Isolations**: **7 / 7**
- **Isolation Accuracy**: **100.0%**
- **False In-Flight Abort Rate from Sensor Glitches**: **0.0%**
- **Average Detection Latency**: **< 10 ms**
