## Codebase Overview

Limit Break AMM security audit framework. This parent directory orchestrates audits across multiple target repos in the Guardian Defender contest (Feb-Apr 2026).

**Stack**: Solidity 0.8.24, Foundry, cancun EVM, PermitC (EIP-712), Creator Token Standards
**Framework**: `docs/` contains shared methodology, agent spawn prompts, memory system, and per-target artifacts.

**Target repos** (each has its own git repo, not tracked here):
- `lbamm-core/` — Core AMM module, pool management, math libraries
- `amm-pool-type-dynamic/` — Dynamic pool type implementation
- `lbamm-pool-type-fixed/` — Fixed pool type implementation
- `lbamm-pool-type-single-provider/` — Single-provider pool type implementation
- `lbamm-hooks-and-handlers/` — Transfer handlers (CLOB, permit) + AMM hooks (audited v1+v2, 0 accepted)
- `secure-proxy/` — Proxy infrastructure (dependency, read-only)

**Build tools run inside each target repo** — `cd lbamm-hooks-and-handlers/ && forge build`. This parent is for framework/orchestration only.

**Structure**:
- `docs/framework/` — Shared rubrics, runbook, tool guide, patterns
- `docs/orchestrator/templates/` — Agent prompt templates (archetypes, checklists, preamble)
- `docs/audit_memory/` — Hierarchical memory system (digest, FPs, patterns, lessons, episodes)
- `docs/targets/{name}/` — Per-target artifacts, results, spawn-prompt overrides
- `docs/plans/` — Implementation plans
- `docs/references/` — Research materials

**Wave models**: `WAVES_BLACK_HAT` (default, offense-first) or `WAVES_DEFENSIVE` (original 8-wave). Switch in `config.py:WAVES`.

**Active templates** (black hat model):
- `black-hat-preamble.md` — shared exploit-first reasoning (included via `{{PREAMBLE}}`)
- 9 archetype templates: `precision-sniper`, `state-desync`, `auth-forger`, `math-deep-diver`, `cross-boundary`, `composability-exploiter`, `price-distorter`, `insolvency-engineer`, `extension-hijacker`
- `exploit-developer` — wave 2 PoC construction from wave 1 leads
- Old defensive templates archived in `docs/orchestrator/templates/archive/`

**Experiment loop** (compliance scoring model):
- `docs/orchestrator/experiment.py` — `compute_compliance_score()`, TSV logger, `best_score()`
- `docs/orchestrator/compliance.py` — 6-dimension scoring (checklist, tool_breadth, evidence, depth, thesis, hypothesis)
- `docs/targets/full-system/experiments.tsv` — persistent experiment log (untracked)
- Run with: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --experiment --description "what changed"`
- Best score: 112.5 (read `experiments.tsv` for current trajectory)

For architecture details, see [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md).
<!-- context-sync: 2026-03-28T15:30:50Z -->
<!-- Recent changes: Templates changed: 1 files modified; Config changed: config.py; Scoring changed: compliance.py, 2026-03-28-output-compliance-and-dimensional-patterns.md -->
