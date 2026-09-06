# HARDWARE-IN-THE-LOOP (HIL) INTERFACE DESIGN

---

## 1. Supported Hardware Architectures

1. **Linux Virtual CAN (`vcan0`)**:
   ```bash
   sudo modprobe vcan
   sudo ip link add dev vcan0 type vcan
   sudo ip link set up vcan0
   ```
2. **Physical USB-CAN Adapters**:
   - Supported Interfaces: SocketCAN, PEAK-System PCAN-USB, CANable (Candlelight firmware), Lawicel CANUSB.
3. **Serial / UART / ARINC-429 Bridges**:
   - 115200/921600 baud binary telemetry framing.

---

## 2. End-to-End Pipeline
$$\text{CAN Bus (0x100 - 0x103)} \xrightarrow{\text{CRC8 Check}} \text{CAN Decoder} \xrightarrow{\text{Canonical Telemetry}} \text{Physics Engine V2} \xrightarrow{\text{Residuals}} \text{HGB-PRO Diagnostics}$$
