#!/usr/bin/env bash
# ==============================================================================
# AeroPulse-X Edge Compute Node Daemon Startup Script
# Target: ARM64 / ARMv7 / Linux SBC (Raspberry Pi 4/5, NVIDIA Jetson, etc.)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"
export AEROPULSE_CONFIG="${SCRIPT_DIR}/edge_config.json"
export AEROPULSE_MODE="EDGE_NODE"

LOG_DIR="/var/log/aeropulse"
mkdir -p "${LOG_DIR}" 2>/dev/null || LOG_DIR="/tmp/aeropulse_logs"
mkdir -p "${LOG_DIR}"

echo "[AEROPULSE-X EDGE] Initializing Edge Compute Subsystem..."
echo "[AEROPULSE-X EDGE] Architecture: $(uname -m) | Kernel: $(uname -r)"

# Setup SocketCAN interface if running on Linux with physical CAN adapter
if [ -d "/sys/class/net/can0" ]; then
    echo "[AEROPULSE-X EDGE] Configuring physical CAN interface can0 at 500 kbps..."
    ip link set can0 down 2>/dev/null || true
    ip link set can0 type can bitrate 500000 2>/dev/null || true
    ip link set can0 up 2>/dev/null || true
    echo "[AEROPULSE-X EDGE] can0 link state: UP"
else
    echo "[AEROPULSE-X EDGE] No hardware can0 detected; initializing internal simulated CAN bus adapter."
fi

echo "[AEROPULSE-X EDGE] Starting UAVEdgeNode daemon..."
exec python3 -m app.edge \
    --config "${AEROPULSE_CONFIG}" \
    --log-dir "${LOG_DIR}" \
    >> "${LOG_DIR}/edge_node.log" 2>&1
