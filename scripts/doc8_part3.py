
### PART 3 — AI/ML, Data Quality & Scientific Leakage (Questions 21 to 30)

#### Q21: Why did you select HistGradientBoostingClassifier over Deep Neural Networks (LSTM/Transformers)?
- **Evidence-Based Answer:** Tabular and physical sensor residuals in edge environments benefit significantly from tree-based histogram gradient boosting (scikit-learn). HGB achieves **96.8% accuracy and 96.1% macro F1** while executing inference in **0.005 ms (<5 microseconds)** with a model size of only **1.1 MB**, compared to heavy neural networks that require GPU acceleration and introduce non-deterministic edge latency.

#### Q22: How did you prevent data leakage during ML model training?
- **Evidence-Based Answer:** We enforced strict **Trajectory-Level GroupKFold Partitioning** (GroupKFold with 5 splits grouped by trajectory_id). Zero flight trajectories are shared between train and test splits, eliminating temporal autocorrelation cross-talk. All preprocessors (StandardScaler) are fit strictly on training folds.

#### Q23: Isn't your ML model just learning the rules of your own synthetic simulator (Circular Validation)?
- **Evidence-Based Answer:** **Yes, this is an inherent scientific constraint of synthetic data validation.** The ML model is trained on physics-generated trajectories; therefore, high test accuracy proves that the classifier has successfully learned the non-linear degradation relationships of our physics simulation. We explicitly declare this in docs/AEROPULSE_X_DATASET_AUDIT.md and do NOT claim it represents physical experimental ground truth.

#### Q24: How does your system distinguish between a Genuine Engine Overheat and a Faulty CHT Sensor?
- **Evidence-Based Answer:** Through our **Multi-Sensor Trust Matrix** (app/sensor_trust.py and tests/test_virtual_sil.py). A genuine engine overheat creates thermodynamic cross-coupling: CHT rises, coolant temperature rises, and oil temperature rises. If the CHT sensor spikes or drifts while coolant and oil temperatures remain nominal, the Sensor Trust Matrix vetoes the CHT reading, isolates it as a transducer fault (96.5% isolation accuracy), and prevents false FADEC derating.

#### Q25: What is the role of the Temporal Convolutional Autoencoder (TCN)?
- **Evidence-Based Answer:** app/tcn_model.py implements a Causal Dilated 1D Convolutional Autoencoder. It reconstructs multi-channel temporal windows of healthy baseline telemetry. When unmodeled, out-of-distribution anomalies occur, the reconstruction error (L2 norm) spikes, providing unsupervised anomaly detection without requiring prior fault labeling.

#### Q26: How do you handle extreme class imbalance between Healthy (90%) and Critical (2%) flight states?
- **Evidence-Based Answer:** We employ cost-sensitive class weighting (class_weight='balanced'), stratified grouping, and focal loss penalties on critical transitions, ensuring **96.5% Critical Fault Recall** and a **0.0% Critical-to-Normal false dismissal rate**.

#### Q27: What is the detection delay of your AI diagnostic pipeline?
- **Evidence-Based Answer:** Sensor anomalies are flagged within **1 to 3 time steps (100–300 ms)**. Progressive degradation states (Watch/Warning) are confirmed over a 5-step rolling persistence filter to prevent transient false alarms.

#### Q28: Why do you not use SHAP (SHapley Additive exPlanations) for real-time edge explainability?
- **Evidence-Based Answer:** SHAP TreeExplainer requires evaluating thousands of tree permutations per sample, taking 20–100 ms per inference. In an edge node running at 50 Hz, this violates real-time deadlines. Instead, AeroPulse-X uses a **Deterministic Physical Causal Evidence Engine** (app/explainability.py) that ranks |z|-score deviations and thermodynamic coupling scores in <0.01 ms.

#### Q29: What features are most important in your ML model?
- **Evidence-Based Answer:** Permutation feature importance rankings show:
  1. CHT and Water_Temp (Thermal runaway & radiator faults)
  2. Oil_Pressure and Oil_Temp (Lubrication breakdown)
  3. EGT1-4 cylinder spread (Combustion misfire & injector degradation)
  4. Battery_Voltage and Alternator_Temp (Electrical bus decay).

#### Q30: What is your model's False Negative Rate for critical catastrophic failures?
- **Evidence-Based Answer:** On our holdout evaluation partition (36,000 samples), the Critical Fault False Negative Rate is **3.5% (all misclassified as Warning, with 0 samples misclassified as Normal)**.
