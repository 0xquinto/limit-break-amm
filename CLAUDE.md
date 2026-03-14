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
- `docs/spawn-prompts/` — Base agent templates (framework sections)
- `docs/audit_memory/` — Hierarchical memory system (digest, FPs, patterns, lessons, episodes)
- `docs/targets/{name}/` — Per-target artifacts, results, spawn-prompt overrides
- `docs/plans/` — Implementation plans
- `docs/references/` — Research materials

**Wave models**: `WAVES_BLACK_HAT` (default, offense-first) or `WAVES_DEFENSIVE` (original 8-wave). Switch in `config.py:WAVES`.

**Active templates** (black hat model):
- `black-hat-preamble.md` — shared exploit-first reasoning (included via `{{PREAMBLE}}`)
- 6 archetype templates: `price-distorter`, `insolvency-engineer`, `state-desync`, `precision-sniper`, `auth-forger`, `extension-hijacker`
- `exploit-developer` — wave 2 PoC construction from wave 1 leads
- Old defensive templates archived in `docs/orchestrator/templates/archive/`

**Experiment loop** (autoresearch model):
- `docs/orchestrator/experiment.py` — `compute_audit_score()`, TSV logger, `best_score()`
- `docs/targets/full-system/experiments.tsv` — persistent experiment log (untracked)
- `docs/targets/full-system/research-program.md` — meta-researcher instructions (what to optimize, what's modifiable)
- Run with: `python3 -m docs.orchestrator.run_audit --wave 1 --fresh --experiment --description "what changed"`
- Baseline: `audit_score=13.9` (0 findings, 0/4 regression, 25% tools, 80 vectors)

For architecture details, see [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md).
