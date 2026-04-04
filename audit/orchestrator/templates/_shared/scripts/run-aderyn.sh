#!/bin/bash
# Static analysis (cross-repo patched)
# Usage: bash docs/orchestrator/templates/_shared/scripts/run-aderyn.sh <repo-path>
set -e
if [ $# -lt 1 ]; then echo "Usage: $0 <repo-path>"; exit 1; fi
cd "$1"
~/.foundry/bin/forge build
/opt/homebrew/bin/aderyn .
