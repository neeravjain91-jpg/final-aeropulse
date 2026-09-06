# DATA PROVENANCE & RECORD INVENTORY REPORT

| Stream Name | Provenance Tier | Sample Count | Underlying Source | Features & Labels |
| :--- | :--- | :--- | :--- | :--- |
| **ACES Telemetry** | REAL_TELEMETRY | 173,878 rows | NASA ACES Piston Engine Flight Data | 14 channels (RPM, EGT1-3, CHT, Oil P/T, Batt V/A) |
| **Physics Digital Twin**| MODEL_INFERENCE | Dynamic | ReducedOrderPistonEngine V2 | Expected thermodynamic reference and residuals |
| **Fault Injections** | SYNTHETIC_FAULT | Configurable | Physical Parameter Perturbation | Overheating, lubrication, misfire, injector degradation |
| **Navigation Coordinates**| SIMULATED_TELEMETRY| Dynamic | Haversine Kinematic Engine + OSM GIS | Waypoints, altitude profile, airspeed, wind vectors |
| **CAN Bus Messages** | SIMULATED_BUS | Dynamic | CAN 2.0B 8-Byte Frame Encoder | IDs 0x100 - 0x103 with CRC8 checksum |
