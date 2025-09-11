#!/usr/bin/env bash
set -euo pipefail

# Run the Python PV bridge that couples the simulator with EPICS PVs
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$THIS_DIR/.."

PY=${PY:-python3}
DT=${DT:-0.1}
Q_DCM=${QLOAD:-50}
INIT_SEC=${INIT_SEC:-2.0}
BAND=${BAND:-5.0}

echo "[run_bridge] dt=$DT q_dcm=$Q_DCM"
$PY tools/pv_bridge.py --dt "$DT" --q_dcm "$Q_DCM" "$@"
