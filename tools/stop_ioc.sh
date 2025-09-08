#!/usr/bin/env bash
set -euo pipefail

# Try to gracefully stop IOC processes by name
PIDS=$(pgrep -f "/bin/linux-x86_64/DCM_CCV2" || true)

if [[ -z "${PIDS}" ]]; then
  echo "[stop_ioc] no IOC process found"
  exit 0
fi

echo "[stop_ioc] stopping PIDs: ${PIDS}"
kill ${PIDS} || true
sleep 1

PIDS2=$(pgrep -f "/bin/linux-x86_64/DCM_CCV2" || true)
if [[ -n "${PIDS2}" ]]; then
  echo "[stop_ioc] force killing PIDs: ${PIDS2}"
  kill -9 ${PIDS2} || true
fi

echo "[stop_ioc] done"

