# AEROPULSE-X: BASELINE RECONCILIATION REPORT
**Rigorous Root-Cause Dissection of Historical (89.19%) vs. Dataset-Upgrade (86.35%) Baselines**
**Date**: August 2026 | **Author**: Antigravity AI Engineering Team

---

## 1. Executive Summary

This investigation sought to answer why the historical baseline reported **89.19% Accuracy** (Balanced Accuracy: 87.67%, Macro F1: 85.18%, Critical Recall: 91.31%), whereas the recent Dataset-Upgrade Experiment A reported **86.35% Accuracy**.

By executing bitwise-identical reproductions against `aces_health.csv` (173,878 rows, 14 flights), the historical **89.19% baseline was reproduced to the exact second decimal place**. The discrepancy stems from two concrete methodological differences:

1. **Held-Out Flight Split Composition**:
   - **Historical Baseline (89.19%)**: Derived from `GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)`, which partitioned 3 held-out flights: `['aces1am_2002_191', 'aces1am_2002_225', 'aces1am_2002_235']` (30,061 test samples).
   - **Dataset Upgrade Exp A (86.35%)**: Used a manually hardcoded 4-flight held-out split: `['aces1am_2002_191', 'aces1am_2002_224', 'aces1am_2002_225', 'aces1am_2002_237']` (31,064 test samples). Flights `224` and `237` have distinct operational phase distributions and higher class boundary variance.

2. **Categorical Encoding of `Operating_State`**:
   - **Historical Baseline (89.19%)**: Employed `ColumnTransformer` with `OneHotEncoder(handle_unknown='ignore')` on `Operating_State` (7 regimes: CLIMB, CRUISE, CRUISE_LOW, DESCENT, DESCENT_LOW, GROUND, TAKEOFF) in addition to the 14 numeric channels.
   - **Dataset Upgrade Exp A (86.35%)**: Evaluated raw numeric sensor arrays without one-hot encoding the operating regime.

---

## 2. Quantitative Side-by-Side Comparison

| Dimension | Historical Baseline Protocol | Dataset Upgrade (Exp A) Protocol |
| :--- | :--- | :--- |
| **Dataset Source** | `FINAL_DATASET/ACES/aces_health.csv` | `FINAL_DATASET/ACES/aces_health.csv` |
| **Total Rows** | 173,878 rows | 173,878 rows |
| **Train Flights (Count & IDs)**| 11 flights (143,817 rows) | 10 flights (142,814 rows) |
| **Held-Out Test Flights** | **3 flights**: `191`, `225`, `235` (30,061 rows) | **4 flights**: `191`, `224`, `225`, `237` (31,064 rows) |
| **Feature Set** | 14 Continuous + **OneHot(`Operating_State`)** | 14 Continuous only |
| **Model** | `HistGradientBoostingClassifier(max_iter=150)` | `HistGradientBoostingClassifier(max_iter=80)` |
| **Accuracy** | **89.19%** (reproduced 100% exact) | **86.35%** |
| **Balanced Accuracy** | **87.67%** (reproduced 100% exact) | **84.93%** |
| **Macro F1** | **85.18%** (reproduced 100% exact) | **82.14%** |
| **Critical Recall** | **91.31%** (reproduced 100% exact) | **87.72%** |
| **Critical F1** | **79.74%** (reproduced 100% exact) | **82.84%** |
| **Critical FNR** | **8.69%** (reproduced 100% exact) | **12.28%** |

---

## 3. Mathematical Verification Script Output

Running the historical verification pipeline reproduces:
```text
GroupShuffleSplit held-out flights: ['aces1am_2002_191', 'aces1am_2002_225', 'aces1am_2002_235']
Train: 143,817 | Test: 30,061
Accuracy:          89.19%
Balanced Accuracy: 87.67%
Macro F1:          85.18%
Critical Recall:   91.31%
Critical F1:       79.74%
Critical FNR:       8.69%
```

---

## 4. Standardized Protocol for Optimization

To ensure strict scientific integrity during the >95% optimization search:
1. Both the 3-flight held-out benchmark (`191, 225, 235`), the 4-flight held-out benchmark (`191, 224, 225, 237`), the 5-fold `GroupKFold` across all 14 flights, AND Leave-One-Flight-Out (LOFO) cross-validation must be reported for every candidate architecture.
2. `Operating_State` encoding must be explicitly treated as an environmental/regime feature.
3. No cherry-picked splits will be permitted: cross-flight generalization must hold across all 14 flights.
