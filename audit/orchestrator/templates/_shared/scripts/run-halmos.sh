#!/bin/bash
# Symbolic execution for mathematical invariants
# Usage: bash docs/orchestrator/templates/_shared/scripts/run-halmos.sh <repo-path> <contract-name>
set -e
if [ $# -lt 2 ]; then echo "Usage: $0 <repo-path> <contract-name>"; exit 1; fi
cd "$1"
~/.foundry/bin/forge build
~/.local/bin/halmos --contract "$2" --function "check_" --loop 4 --solver-timeout-assertion 30000
