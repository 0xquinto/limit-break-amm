#!/bin/bash
# Parallel corpus-guided fuzzer
# Usage: bash docs/orchestrator/templates/_shared/scripts/run-medusa.sh <repo-path> <contract-name>
set -e
if [ $# -lt 2 ]; then echo "Usage: $0 <repo-path> <contract-name>"; exit 1; fi
cd "$1"
~/.foundry/bin/forge build
/opt/homebrew/bin/medusa fuzz --target-contracts "$2" --test-limit 100000
