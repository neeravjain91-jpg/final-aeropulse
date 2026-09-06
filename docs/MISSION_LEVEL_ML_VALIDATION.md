# MISSION-LEVEL / CROSS-FLIGHT ML VALIDATION REPORT

**Methodology**: Group evaluation treating each of the 14 flight missions as an independent operational log.

---

## 1. Flight-by-Flight Validation Breakdown

| Flight ID | Role / Partition | Sample Count | Accuracy (%) | Critical Support | Critical Recall (%) | Critical F1 (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `aces1am_2002_191` | **HELD_OUT_TEST** | 4,009 | **90.25%** | 87 | **79.31%** | **78.41%** |
| `aces1am_2002_192` | TRAIN | 11,268 | **97.67%** | 557 | **100.00%** | **94.81%** |
| `aces1am_2002_193` | TRAIN | 13,530 | **97.95%** | 85 | **100.00%** | **83.74%** |
| `aces1am_2002_214` | TRAIN | 7,657 | **99.02%** | 5 | **80.00%** | **80.00%** |
| `aces1am_2002_216` | TRAIN | 13,018 | **96.07%** | 14 | **92.86%** | **74.29%** |
| `aces1am_2002_218` | TRAIN | 6,243 | **98.21%** | 7 | **100.00%** | **82.35%** |
| `aces1am_2002_220` | TRAIN | 14,333 | **98.97%** | 388 | **100.00%** | **96.04%** |
| `aces1am_2002_222` | TRAIN | 29,556 | **98.99%** | 350 | **100.00%** | **95.24%** |
| `aces1am_2002_224` | TRAIN | 6,764 | **99.48%** | 275 | **100.00%** | **97.69%** |
| `aces1am_2002_225` | **HELD_OUT_TEST** | 10,910 | **89.75%** | 592 | **93.07%** | **81.51%** |
| `aces1am_2002_227` | TRAIN | 19,846 | **98.69%** | 434 | **99.77%** | **94.55%** |
| `aces1am_2002_235` | **HELD_OUT_TEST** | 15,142 | **88.51%** | 0 | *N/A (0 faults)* | *N/A* |
| `aces1am_2002_237` | TRAIN | 9,381 | **97.14%** | 23 | **100.00%** | **90.20%** |
| `aces1am_2002_242` | TRAIN | 12,221 | **95.84%** | 11 | **90.91%** | **71.43%** |

---

## 2. Statistical Summary across All 14 Missions
- **Mean Accuracy**: **96.18% +/- 3.65%**
- **Min Flight Accuracy**: **88.51%** (`aces1am_2002_235`)
- **Max Flight Accuracy**: **99.48%** (`aces1am_2002_224`)
- **Mean Critical Recall**: **94.69% +/- 7.82%**
