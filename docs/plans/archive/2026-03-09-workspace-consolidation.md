# Workspace Consolidation Plan

**Date:** 2026-03-09
**Goal:** Consolidate all project context into lbamm-hooks-and-handlers as the single working directory.

## Background

Context was scattered between `bug_bounty/` (SDK orchestrator, Pashov/autoresearch references, Anthropic strategy) and `lbamm-hooks-and-handlers/` (battle-tested system, v1/v2 runs, spawn-prompts, 21 artifacts). The `bug_bounty/run_audit.py` and `agents/*.md` were built without awareness of the existing v1/v2 system — they're a parallel reimplementation. The value is in the **ideas**, not the files.

## 12 Ideas to Integrate

| # | Idea | Source | Integration Target |
|---|---|---|---|
| 1 | FP gate (3-check + confidence scoring) | Pashov `judging.md` | `agent-boilerplate.md` — add FP Gate section |
| 2 | 170 attack vectors | Pashov `attack-vectors/*.md` | `known-vuln-patterns.md` — link as supplementary corpus |
| 3 | Structured TSV run logging | karpathy/autoresearch | `execution-runbook.md` — add to Phase 3.5 |
| 4 | Cross-pollination (agents read prior findings) | karpathy/autoresearch | `execution-runbook.md` + spawn prompt template |
| 5 | Session reports as artifacts | karpathy/autoresearch | `execution-runbook.md` — add to Phase 5 |
| 6 | Bundle-and-fan-out | Pashov SKILL.md | `execution-runbook.md` Phase 1 + `agent-boilerplate.md` |
| 7 | "NEVER STOP" autonomy | karpathy/autoresearch | `agent-boilerplate.md` — autonomy rules section |
| 8 | Report formatting template | Pashov `report-formatting.md` | `agent-boilerplate.md` — standardized output format |
| 9 | Triage taxonomy (Skip/Borderline/Survive) | Pashov `vector-scan-agent.md` | All auditor spawn-prompts |
| 10 | Composability check | Pashov `vector-scan-agent.md` | All auditor spawn-prompts |
| 11 | Cross-contract tracer | bug_bounty draft | New: `spawn-prompts/cross-contract-tracer.md` |
| 12 | PoC deepen phase | bug_bounty draft | `execution-runbook.md` — formalize Phase 2.5 |

## Execution Steps

### Step 1: Create `docs/references/` [AUTOMATED]

Copy Pashov materials and autoresearch notes into lbamm-hooks-and-handlers.

```
docs/references/
├── pashov-skills/
│   ├── attack-vectors/{1-4}.md   (170 vectors)
│   ├── agents/                    (vector-scan-agent.md, adversarial-reasoning-agent.md)
│   ├── judging.md                 (FP gate + confidence scoring)
│   ├── report-formatting.md
│   ├── SKILL.md                   (orchestrator pattern)
│   └── README.md                  (our assessment)
└── autoresearch-patterns.md       (7 patterns borrowed from karpathy)
```

### Step 2: Consolidate memory [AUTOMATED]

- Copy `anthropic-strategy.md` into lbamm-hooks-and-handlers memory
- Rewrite MEMORY.md: unified context, under 180 lines
- Replace bug_bounty memory with pointer

### Step 3: Integrate ideas into existing docs [MANUAL]

Update these files with the 12 ideas:
- `docs/artifacts/agent-boilerplate.md` — ideas 1, 6, 7, 8
- `docs/execution-runbook.md` — ideas 3, 4, 5, 6, 12
- `docs/artifacts/known-vuln-patterns.md` — idea 2
- All auditor spawn-prompts — ideas 9, 10

### Step 4: Create cross-contract-tracer spawn prompt [MANUAL]

New file: `docs/spawn-prompts/cross-contract-tracer.md` (idea 11)

### Step 5: Verify [MANUAL]

Read execution path end-to-end: `execution-runbook.md` + all spawn-prompts. Confirm no orphaned references or contradictions.

## Not In This Migration

- SDK orchestration (later — per framework evolution roadmap)
- N=2 run on lbamm-core (needs integrated system first)
- Deleting bug_bounty/ (leave as dead weight)
