#!/usr/bin/env bash
set -euo pipefail

# Run simulator bridge with default YAML configs if present
DIR="$(cd "$(dirname "$0")" && pwd)"

exec python "$DIR/pv_bridge.py" \
  --init-config "$DIR/pv_init.yaml" \
  --verbose "$@"

