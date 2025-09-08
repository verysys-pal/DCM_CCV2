#!/usr/bin/env bash
set -euo pipefail

# Run the EPICS IOC using the existing st.cmd
IOC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../iocBoot/iocDCM_CCV2 && pwd)"

echo "[run_ioc] cd $IOC_DIR"
cd "$IOC_DIR"

LOG_FILE="$(cd .. && pwd)/Log_stCmd.log"
echo "[run_ioc] starting IOC, logging to $LOG_FILE"

if [[ -x ./st.cmd ]]; then
  ./st.cmd |& tee "$LOG_FILE"
else
  echo "[run_ioc] st.cmd not executable; running binary with st.cmd"
  ../../bin/linux-x86_64/DCM_CCV2 st.cmd |& tee "$LOG_FILE"
fi

