## Gotchas — price-distorter

_Auto-generated from wave 1 compliance data._

### Checklist completion: 0% (target: 100%)
Your prior run completed fewer than 70% of checklist items. Prioritize completing ALL Phase C items before moving to free-form exploration.

### Missing tools from prior run
- **aderyn**: `bash docs/orchestrator/templates/_shared/scripts/run-aderyn.sh <repo>`
- **audit-context-building**: `Skill("audit-context-building:audit-context-building")`
- **entry-point-analyzer**: `Skill("entry-point-analyzer:entry-point-analyzer")`
- **forge**: `cd <repo> && forge test --match-contract <YourTest> -vvv`
- **halmos**: `bash docs/orchestrator/templates/_shared/scripts/run-halmos.sh <repo> <contract>`
- **medusa**: `bash docs/orchestrator/templates/_shared/scripts/run-medusa.sh <repo> <contract>`
- **slither**: `Use Slither MCP tools (mcp__slither__run_detectors)`

### Early completion detected (0 turns)
Your prior run used only 0 of 200 available turns. Do NOT declare completion early. Work through every checklist item.

### Low test count (0 Forge tests)
Use the fuzz test scaffold: `cat docs/orchestrator/templates/_shared/scripts/forge-fuzz-template.t.sol`

### Score: 0.0/100 (F) — weakest: checklist
Target: C grade. Focus on **checklist** dimension.
