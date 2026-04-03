# New Audit Target

## Quick Start

1. Copy this directory:
   ```bash
   cp -r docs/targets/_template docs/targets/my-protocol
   ```

2. Edit `target.json`:
   - Set `name` and `description`
   - Add your repos to the `repos` object (path relative to project root)
   - Configure agents: adjust `scope` arrays to match your repo names
   - Add trust boundaries if the architecture has clear module boundaries
   - Set budget limits

3. Place repo source code as sibling directories at the project root

4. Run:
   ```bash
   .venv/bin/python3 -m docs.orchestrator.run_audit \
     --target my-protocol --wave 1 --mode compliance \
     --fresh --description "initial audit"
   ```

## Configuration Reference

See `docs/targets/full-system/target.json` for a complete example (Limit Break AMM with 6 repos, 9 compliance agents, 6 trust boundaries).

### Required fields
- `name`: unique identifier
- `repos`: map of repo name → {path, tokens}
- `agents.compliance`: at least 1 agent with name/role/template/scope

### Optional fields
- `boundaries`: trust boundary definitions for Pass 1 hypothesis generation
- `budget`: cost and turn limits
- `custom_detectors`: Python module paths for custom Slither detectors

## Agent Archetypes

Available templates (in `docs/orchestrator/templates/`):
- `math-deep-diver` — precision loss, overflow, rounding
- `state-desync` — state inconsistencies, reentrancy
- `auth-forger` — access control, privilege escalation
- `cross-boundary` — cross-module interactions
- `composability-exploiter` — token composability
- `insolvency-engineer` — balance sheet attacks
- `precision-sniper` — fee/rounding precision
- `price-distorter` — oracle/pricing manipulation
- `extension-hijacker` — hook/plugin exploitation
- `exploit-user-prompt` — attack-focused (exploit mode)
