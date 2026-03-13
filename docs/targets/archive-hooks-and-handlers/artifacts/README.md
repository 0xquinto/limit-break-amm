# Phase 0 Artifact Registry

> Single source of truth for all pre-computed artifacts. Cross-reference with `team-design.md` Phase 0 steps.

## Artifact Index

| P0-ID | Filename | Description | Method | Primary Consumers |
|-------|----------|-------------|--------|-------------------|
| P0-01 | `access-control-matrix.md` | Public/external function access controls | manual | all auditors, fuzz-writer, poc-writer |
| P0-02 | `order-lifecycle.md` | CLOB state machine (states S0-S6, transitions) | manual | clob-auditor, fuzz-writer |
| P0-03 | `token-flow.md` | Token/value flow analysis across handlers | manual | all auditors, fuzz-writer, poc-writer |
| P0-04 | `external-interfaces.md` | Sibling repo interfaces (AMM hooks, PermitC) | manual | all auditors, poc-writer |
| P0-05 | `slither-findings.md` | Slither detector results (High+Med) | slither | all auditors |
| P0-06 | `dead-code.md` | Dead code analysis | slither | all auditors |
| P0-07 | `storage-layouts.md` | Per-contract storage layouts | slither | all auditors (esp. registry, hook) |
| P0-08 | `coverage-gaps.md` | Forge coverage report | forge | all auditors, fuzz-writer |
| P0-09 | `call-graphs.md` | Per-contract call graphs | slither | all auditors |
| P0-10 | `known-vuln-patterns.md` | External vulnerability research | exa | all auditors |
| P0-11 | `remediation-diff.md` | Git diff of remediation changes | git diff | all auditors |
| P0-12 | `tool-guide.md` | Chisel/Halmos/Medusa/Aderyn/Quimera/Skills/git-diff usage | manual | all agents |
| — | *(Step 13: Verify plan doc is current)* | Not an artifact — operational task | — | lead |
| P0-14 | `turn-counts.md` | Agent metrics tracking template | manual template | lead (runtime) |
| P0-15 | `agent-boilerplate.md` | Shared agent standards (rubric, setup, anti-patterns) | manual | all agents |
| P0-16 | `novel-attack-surface.md` | Protocol-specific attack primitives | manual | all agents |
| P0-17 | `economic-model-clob.md` | CLOB fee structure, incentive alignment | manual | clob-auditor, economic-analyst |
| P0-18 | `mev-surface.md` | MEV-susceptible functions | manual | clob-auditor, economic-analyst |
| P0-19 | `cross-boundary-call-graph.md` | Cross-repo function callers/callees | slither + manual | all agents |
| P0-20 | `acknowledged-findings-families.md` | Guardian's 53 findings grouped into dedup families | manual | all agents |
| P0-21 | `spec-vs-code.md` | NatSpec/README assertions vs implementation | manual | all agents |
| P0-22 | `aderyn-findings.md` | Aderyn static analysis results | aderyn | all auditors |

**Total: 21 artifact files (P0-01 through P0-22, P0-13 intentionally skipped — operational task, not artifact)**

## Non-P0 Files in This Directory

These are runtime outputs, not pre-computed Phase 0 artifacts:

| Filename | Purpose | Created By |
|----------|---------|------------|
| `agent-metrics-*.md` | Per-agent runtime metrics (written in worktrees) | individual agents |

## Verification

Run before Phase 1 to confirm all artifacts exist:

```bash
cd docs/artifacts
missing=0
for id in 01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 18 19 20 21 22; do
  file=$(grep -rl "ID:.*P0-$id" . --include='*.md' 2>/dev/null | grep -v README.md | head -1)
  if [ -z "$file" ]; then
    echo "MISSING: P0-$id"
    missing=$((missing + 1))
  else
    echo "OK: P0-$id → $(basename $file)"
  fi
done
[ $missing -eq 0 ] && echo "All 21 P0-ID artifacts present — Phase 0 gate PASSED"
```

## Consumer Quick-Reference

Which artifacts each agent **must** read (per spawn prompts):

| Agent | Reads |
|-------|-------|
| **All 4 domain auditors** | P0-01, 03–12, 15–16, 19–22 |
| **clob-auditor** | *(above)* + P0-02, 17, 18 |
| **cross-contract-tracer** | P0-01, 03–06, 08–10, 12, 15–16, 19–22 |
| **economic-analyst** | P0-12, 15–21 |
| **fuzz-writer** | P0-01–03, 08, 12, 15–16, 19–21 |
| **poc-writer** | P0-01, 03–04, 12, 15–16, 19–21 |
| **red-team-adversary** | P0-15–16, 19–21 |
