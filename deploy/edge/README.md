# AeroPulse-X — Embedded Edge Compute Node Deployment Guide

This directory contains the deployment profile, configuration templates, and operational scripts for running the **AeroPulse-X Edge Compute Node (`UAVEdgeNode`)** on embedded Linux targets (e.g., Raspberry Pi 4/5, NVIDIA Jetson Orin Nano/Xavier, BeagleBone AI-64, or custom ARM64 UAV flight computers).

---

## 1. System Requirements & Hardware Targets

- **Supported Architectures:** `aarch64` (ARM64), `armv7l` (ARM32), `x86_64` (x86 Linux).
- **Target OS:** Ubuntu Server 22.04/24.04 LTS (64-bit), Raspberry Pi OS Lite (64-bit), or NVIDIA JetPack 5.x/6.x.
- **Minimum RAM:** 512 MB (Peak RSS footprint is typically < 140 MB with PyTorch/TorchScript runtime).
- **Minimum Storage:** 250 MB free disk space.
- **CAN Bus Hardware (Optional for physical bus):** MCP2515 SPI-CAN Hat, Waveshare 2-CH CAN Hat, or PEAK PCAN-USB.

---

## 2. Multi-Modal AI Engine Deployment

The edge node incorporates the upgraded dual Deep Learning pipeline:
1. **Calibrated HGB + TCN Hybrid Diagnostic Fusion**: 0.70 HGB point model + 0.30 1D Dilated Causal TCN model with $\tau_{\text{Critical}} = 0.25$.
2. **Temporal TCN Autoencoder**: Unsupervised physics-residual reconstruction autoencoder (TorchScript `.ts` optimized) for zero-day anomaly detection.
3. **Deterministic Sensor Health Veto**: Hardware and mathematical checks that override ML predictions when sensor plausibility is violated.

---

## 3. Installation Steps

### Step 3.1: Clone & Setup Environment
```bash
# Update system packages
sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv can-utils iproute2 curl

# Navigate to project repository
cd /opt/aeropulse-x

# Create lightweight edge virtual environment
python3 -m venv venv-edge
source venv-edge/bin/activate

# Install edge dependencies
pip install --upgrade pip
pip install -r deploy/edge/requirements-edge.txt
```

### Step 3.2: Configure Hardware CAN (SocketCAN)
If using an MCP2515 CAN hat on Raspberry Pi `/boot/config.txt` (or `/boot/firmware/config.txt`):
```ini
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25
dtoverlay=spi-bcm2835
```
After reboot, bring up the `can0` interface:
```bash
sudo ip link set can0 up type can bitrate 500000
ip link show can0
```

---

## 4. Running the Edge Node

### Docker Deployment
```bash
# Build and run containerized edge stack
docker compose up -d --build
```

### Manual Launch
```bash
bash deploy/edge/start_edge_node.sh
```

### Systemd Service Deployment
Create `/etc/systemd/system/aeropulse-edge.service`:
```ini
[Unit]
Description=AeroPulse-X UAV Edge Health & Telemetry Daemon
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/aeropulse-x
ExecStart=/opt/aeropulse-x/venv-edge/bin/python3 -m app.edge --config /opt/aeropulse-x/deploy/edge/edge_config.json
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aeropulse-edge.service
sudo systemctl status aeropulse-edge.service
```

---

## 5. Embedded Benchmarking

To benchmark edge execution latency, throughput, and memory RSS on physical hardware:
```bash
python3 scripts/benchmark_edge_embedded.py --samples 10000 --warmup 500
```
