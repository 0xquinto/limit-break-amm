#!/bin/bash
# Static analysis with cross-repo build-info fix
# Usage: bash audit/orchestrator/templates/_shared/scripts/run-slither.sh <repo-path>
set -e
if [ $# -lt 1 ]; then echo "Usage: $0 <repo-path>"; exit 1; fi
# Resolve PROJECT_ROOT before cd — .venv is relative to project root, not the repo
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# 5 levels up: scripts/ → _shared/ → templates/ → orchestrator/ → audit/ → PROJECT_ROOT
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
[ -f "$PROJECT_ROOT/.venv/bin/python3" ] || { echo "ERROR: PROJECT_ROOT resolve failed (got $PROJECT_ROOT)"; exit 1; }
cd "$1"
~/.foundry/bin/forge build
# fix_build_info is in artifact_generator.py — call via python
PYTHONPATH="$PROJECT_ROOT" "$PROJECT_ROOT/.venv/bin/python3" -c "
from docs.orchestrator.artifact_generator import fix_build_info
from pathlib import Path
fix_build_info(Path('.'))
"
slither . --ignore-compile
