# AEROPULSE-X CAN BUS / SOCKETCAN INTEGRATION ARCHITECTURE
## Message Framing, Canonical Schema Mapping, Scaling, and Fault Tolerance

**Document Version**: 2.0.0-SIH  
**Release Date**: August 26, 2026  
**Module**: `app/can_bus.py` & `app/telemetry.py`

---

## 1. Overview
AeroPulse-X features a hardware-ready Controller Area Network (CAN 2.0B) ingestion layer. The architecture decodes standard 8-byte raw CAN frames (compatible with Linux SocketCAN, CANoe, or USB-CAN adapters) and serializes them into the canonical `UAVTelemetry` data model.

```
+--------------------+        +--------------------+        +---------------------+
| Hardware CAN Bus / |  Raw   |   CAN Frame Decoder| Canonical|  Digital Twin Engine |
| Simulated CAN Node +------->+  (Scaling, CRC16)  +--------->+     & Diagnostics    |
+--------------------+ Frames +--------------------+ Telemetry+---------------------+
```

---

## 2. CAN Standard Message ID Catalog

| Message ID | Frame Name | Rate (Hz) | DLC | Payload Signal Content |
| :--- | :--- | :--- | :--- | :--- |
| **`0x100`** | `CAN_ENGINE_DYNAMICS` | 20 Hz | 8 | `Engine_RPM` (uint16, 0.25 RPM/bit), `MAP_Injector` (uint16, 0.01 kPa/bit), `Fuel_Flow` (uint16, 0.01 L/hr/bit), `Throttle` (uint8, 0.5%/bit), `State` (uint8) |
| **`0x101`** | `CAN_TEMPERATURES` | 10 Hz | 8 | `EGT1` (uint16, 0.1°C/bit), `EGT2` (uint16, 0.1°C/bit), `EGT3` (uint16, 0.1°C/bit), `CHT` (uint16, 0.1°C/bit) |
| **`0x102`** | `CAN_LUBRICATION_COOLANT` | 10 Hz | 8 | `Oil_Temp` (int16, 0.1°C/bit), `Oil_Pressure` (uint16, 0.1 PSI/bit), `EFI_Water_Temp` (int16, 0.1°C/bit), `EFI_Fuel_Temp` (int16, 0.1°C/bit) |
| **`0x103`** | `CAN_ELECTRICAL_VIB` | 10 Hz | 8 | `Battery_Voltage` (uint16, 0.01 V/bit), `Battery_Current` (int16, 0.1 A/bit), `Alternator_Temp` (int16, 0.1°C/bit), `Vibration` (uint16, 0.001 g/bit) |

---

## 3. Byte Packing & Encoding Specification

### Example: Message `0x100` (`CAN_ENGINE_DYNAMICS`)
```
Byte 0..1: Engine_RPM    (uint16_t, Little Endian, Scale: 0.25, Range: 0 - 16383.75 RPM)
Byte 2..3: MAP_Injector  (uint16_t, Little Endian, Scale: 0.01, Range: 0 - 655.35 kPa)
Byte 4..5: Fuel_Flow     (uint16_t, Little Endian, Scale: 0.01, Range: 0 - 655.35 L/hr)
Byte 6:    Throttle      (uint8_t,  Scale: 0.5%, Range: 0 - 100%)
Byte 7:    CRC8 / Counter(uint8_t,  Rolling sequence 0-15 & parity)
```

---

## 4. Error Handling & Malformed Frame Rejection
- **Stale Frame Detection**: Signals older than 500 ms trigger a `CAN_TIMEOUT_WARNING`.
- **Out-of-Range Bounds**: Values outside physical transducer limits trigger `SENSOR_COMMUNICATION_FAULT`.
- **CRC Parity Validation**: Corrupted packets are dropped without affecting state estimation.
