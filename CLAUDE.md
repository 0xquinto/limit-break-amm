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

**Three modes** (`--mode` flag):
- `compliance` — 9 agents (7 Opus + 2 Sonnet), full checklists, compliance scoring. Builds the knowledge base.
- `exploit` — 3 Sonnet agents, attack-focused system prompts, exploit scoring. Consumes the knowledge base.
- Both modes have per-archetype persistent system prompts with knowledge injection.
- Pass 1 boundary agents (6 Sonnet) also have per-boundary system prompts.

**Active templates**:
- 9 compliance archetype templates + 3 exploit templates + exploit-developer (wave 2)
- `black-hat-preamble.md` — shared tool phases (included via `{{PREAMBLE}}`)
- Per-archetype system prompts in `templates/compliance_system_prompts.py`, `exploit_system_prompts.py`, `boundary_system_prompts.py`
- Old defensive templates archived in `docs/orchestrator/templates/archive/`

**Run commands**:
- Compliance: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --mode compliance --experiment --description "..."`
- Exploit: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --mode exploit --hints docs/targets/full-system/hints.md --experiment --description "..."`
- Best compliance score: 112.5. First novel finding: CP-006 (exploit mode, $29 run).

For architecture details, see [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md).
<!-- context-sync: 2026-03-31T12:48:54Z -->
<!-- Recent changes: docs: 80 files (SKILL.md, CLAUDE.md, CODEBASE_MAP.md, hint_generator.py, metadata.json...) -->
