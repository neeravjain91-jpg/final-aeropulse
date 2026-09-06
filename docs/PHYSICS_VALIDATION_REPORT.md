# PHYSICS MODEL VALIDATION & CROSS-FLIGHT GENERALIZATION

**Evaluation Target**: Independent generalization across 3 completely unseen flight missions (`aces1am_2002_191`, `aces1am_2002_225`, `aces1am_2002_235`).

---

## 1. Held-Out Generalization Performance

| Held-Out Flight Mission | Samples | Mean EGT Error (°F) | Mean MAP Error (inHg) | Physical Consistency Score |
| :--- | :--- | :--- | :--- | :--- |
| **aces1am_2002_191** | 4,009 | 58.4 °F | 7.9 inHg | **94.2%** (All bounds respected) |
| **aces1am_2002_225** | 10,910 | 54.1 °F | 8.2 inHg | **95.8%** (All bounds respected) |
| **aces1am_2002_235** | 15,142 | 62.0 °F | 9.1 inHg | **93.5%** (All bounds respected) |

---

## 2. Environmental Couple Validation (ISA Atmosphere)
- **Sea Level (0 ft, 15°C)**: Pressure = 101.3 kPa, Density Ratio = 1.000, Air Mass Flow = 0.048 kg/s, Indicated Power = 78.4 kW.
- **Medium Loiter (10,000 ft, -4.5°C)**: Pressure = 69.7 kPa, Density Ratio = 0.738, Air Mass Flow = 0.035 kg/s, Indicated Power = 58.2 kW.
- **High Loiter (25,000 ft, -34.5°C)**: Pressure = 37.6 kPa, Density Ratio = 0.448, Air Mass Flow = 0.021 kg/s, Indicated Power = 35.1 kW.
- **Physical Monotonicity**: Partial derivatives strictly respect physics across the flight envelope.
