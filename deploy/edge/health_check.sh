#!/usr/bin/env bash
# ==============================================================================
# AeroPulse-X Edge Compute Node Local Health Check
# Target: ARM Linux SBC / systemd watchdog
# ==============================================================================

set -euo pipefail

HEALTH_PORT="${AEROPULSE_EDGE_PORT:-8001}"
ENDPOINT="http://127.0.0.1:${HEALTH_PORT}/health"

if command -v curl >/dev/null 2>&1; then
    RESPONSE=$(curl -s -m 2 "${ENDPOINT}" || echo '{"status":"UNREACHABLE"}')
elif command -v wget >/dev/null 2>&1; then
    RESPONSE=$(wget -qO- -T 2 "${ENDPOINT}" || echo '{"status":"UNREACHABLE"}')
else
    echo "ERROR: Neither curl nor wget available for edge healthcheck."
    exit 1
fi

echo "[EDGE HEALTH] ${RESPONSE}"

if echo "${RESPONSE}" | grep -q '"status":"OK"'; then
    echo "[EDGE HEALTH] Node status: HEALTHY"
    exit 0
else
    echo "[EDGE HEALTH] Node status: DEGRADED OR UNREACHABLE"
    exit 1
fi
