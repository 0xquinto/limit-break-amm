# Full-System Audit Design — Wave Architecture with SDK Orchestration

**Date**: 2026-03-09
**Target**: All 6 repos in `limit-break-amm/` (lbamm-core, amm-pool-type-dynamic, lbamm-pool-type-fixed, lbamm-pool-type-single-provider, lbamm-hooks-and-handlers, secure-proxy)
**Scope**: ~163K tokens, ~290 files, 6 repos
**Budget**: ~$60-86 across ~17 agent instances
**Architecture**: 5-wave audit, SDK-orchestrated, disk-first communication, max 4 agents per wave

---

## 1. Architecture Overview

### Wave Model

Each wave is a fresh team session with its own orchestrator context. Synthesis documents bridge waves — no context bleeds between sessions.

```
Phase 0 (scripted) → Wave 0 (analytical artifacts, optional)
→ Wave 1 (recon, 4 agents) → synthesis
→ Wave 2 (deep top hot spots, 4 agents) → synthesis
→ Wave 3 (deep remaining + economic, 3-4 agents) → synthesis
→ Wave 4 (fuzz/test generation, 2-3 agents) → synthesis
→ Wave 5 (PoC + red-team + second-pass, 3 agents) → final report
→ Memory update
```

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration | SDK (Python) | Reproducible, reusable for future targets (roadmap item 7) |
| Communication | Disk-first, SendMessage for High/Crit only | Prevents context blowup in orchestrator |
| Plan mode | Dropped | L-001: caused 5x resubmission loops in v2 |
| Agents per wave | Max 4 | Keeps each session well under v2's proven 8-agent ceiling |
| Wave boundaries | By audit depth, not by repo | User requirement: advance in lockstep across all repos |
| Framework reuse | 100% methodology, adapted plumbing | Boilerplate, FP gate, rubric, memory, checklist all preserved |

### Runbook Phase Mapping

```
Old Runbook                    New Wave Structure
─────────────                  ──────────────────
Phase 0: Pre-compute           → artifact_generator.py (automated)
  21 artifacts                   Tier 1: scripted (Slither/Aderyn)
                                 Tier 2: Wave 0 agents or manual

Phase 0.5: Cross-pollination   → synthesizer.py reads memory system
  prior-findings.md               Injected into all wave 1 spawn prompts

Phase 1: Team setup + recon    → Wave 1 (4 agents, 15 turns)
  Spawn, plan approval, triage    Recon template, no plan mode

Phase 2: Deep analysis         → Waves 2 + 3 (4 + 3-4 agents, 25-30 turns)
  Monitoring, routing, findings    Deep template, disk-first

Phase 3: PoC confirmation      → Wave 5 (poc-writer)

Phase 3.5: Red-team review     → Wave 5 (red-team-adversary)

Phase 4: Second pass           → Absorbed into wave 3 (remaining hot spots)

Phase 5: Report & teardown     → synthesizer.py final pass
  Metrics, findings report,        Generates final report + updates memory
  memory update
```

### What Stays Unchanged

All audit methodology carries forward:

- Agent boilerplate (P0-15): environment, tools, anti-patterns
- FP gate pipeline: 5 gates + confidence scoring
- Severity rubric + exploitability tiers (A/B/C)
- Attack vector triage: Skip/Borderline/Survive
- Proof sketch format for ruled-out vectors
- Memory system: digest, 45 FPs, 5 confirmed patterns, 8 lessons
- Known vuln patterns: 10 categories, 20+ patterns
- Deliverable format with structured metrics
- JSONL structured logging (SESSION_START, TURN_COMPLETE, FINDING, SAFETY_EVENT, SESSION_END)
- Operational checklist (38 items)
- Turn/budget calibration from v2 data

### What Changes

- TeamCreate/TaskCreate per wave (not one team for entire run)
- SendMessage reduced to High/Crit only (disk-first default)
- Plan mode dropped (L-001 lesson)
- Cross-module routing happens in synthesis step, not real-time
- Phase 4 (second pass) absorbed into wave 3

---

## 2. Wave Definitions

### Wave 1: System-Wide Recon (4 agents, 15 turns each)

| Agent | Scope | Model | Budget |
|-------|-------|-------|--------|
| recon-core | lbamm-core + secure-proxy (~61K tokens) | sonnet | $3 |
| recon-pools | amm-pool-type-dynamic + lbamm-pool-type-fixed + lbamm-pool-type-single-provider (~69K tokens) | sonnet | $3 |
| recon-hooks | lbamm-hooks-and-handlers (~40K tokens, fresh eyes) | sonnet | $3 |
| cross-contract-tracer | all repos, read-only | sonnet | $3 |

**Objective**: Triage all attack vectors, identify top hot spots, map cross-boundary calls, assess module complexity.

**Output per agent**: `docs/targets/full-system/artifacts/wave1-recon-{name}.md`
- Entry point inventory
- Vector triage (Skip/Borderline/Survive)
- Top-5 hot spots with rationale
- Cross-boundary flags
- Complexity assessment (which sub-modules need dedicated deep agents)

**Wave 1 estimated cost**: ~$8-12

### Wave 2: Deep Analysis — Top Hot Spots (4 agents, 30 turns each)

Agent roster determined by wave 1 synthesis. Expected assignments based on codebase complexity:

| Agent | Likely Scope | Model | Budget |
|-------|-------------|-------|--------|
| core-swap-auditor | AMMModule swap paths, hook dispatch, transient storage, reentrancy | opus | $8 |
| dynamic-pool-auditor | DynamicPoolType, DynamicHelper, SqrtPriceMath, SwapMath, TickMath | opus | $8 |
| fixed-pool-auditor | FixedPoolType, FixedHelper (19K), height system, linked lists | sonnet | $5 |
| hooks-auditor | AMMStandardHook, SqrtPriceCalculator (fresh deep dive) | sonnet | $5 |

**Note**: Exact roster depends on wave 1 results. Wave config is partially dynamic.

**Output per agent**: `docs/targets/full-system/artifacts/wave2-{name}.md`
- Uses full deep-analysis template (same structure as v2 spawn prompts)
- Confirmed findings (deliverable format)
- Ruled-out vectors with proof sketches
- Structured metrics block

**Wave 2 estimated cost**: ~$20-28

### Wave 3: Deep Analysis — Remaining + Economic (3-4 agents, 25 turns each)

| Agent | Likely Scope | Model | Budget |
|-------|-------------|-------|--------|
| core-liquidity-auditor | AMMModule liquidity paths, ModuleLiquidity, ModuleFeeCollection | opus | $8 |
| remaining-auditor | Gap areas from wave 2 (e.g., single-provider, proxy, core-admin) | sonnet | $5 |
| economic-analyst | Full-system MEV/fee modeling (needs wave 2 findings) | sonnet | $5 |
| cross-contract-tracer-deep | Re-run with wave 2 context, focused on finding-adjacent boundaries | sonnet | $4 |

**Wave 3 estimated cost**: ~$12-18

### Wave 4: Test Generation (2-3 agents, 30 turns each)

| Agent | Scope | Model | Budget |
|-------|-------|-------|--------|
| fuzz-writer | Invariant tests across all repos targeting wave 2-3 hot spots | sonnet | $10 |
| targeted-fuzz | Specific modules needing dedicated coverage (if wave 3 identifies) | sonnet | $5 |

**Wave 4 estimated cost**: ~$8-12

### Wave 5: Confirmation (3 agents, 20 turns each)

| Agent | Scope | Model | Budget |
|-------|-------|-------|--------|
| poc-writer | Exploit PoC creation for all confirmed findings | opus | $5 |
| red-team-adversary | Challenge all findings + proof sketches from waves 2-3 | opus | $5 |
| second-pass | Gap areas identified across all waves | sonnet | $4 |

**Wave 5 estimated cost**: ~$12-16

### Budget Summary

| Wave | Agents | Est. Cost |
|------|--------|-----------|
| Phase 0 | 0 (scripted) | ~$0 |
| Wave 1 | 4 | ~$8-12 |
| Wave 2 | 4 | ~$20-28 |
| Wave 3 | 3-4 | ~$12-18 |
| Wave 4 | 2-3 | ~$8-12 |
| Wave 5 | 3 | ~$12-16 |
| Orchestrator (synthesis) | — | ~$5-10 |
| **Total** | **~17** | **~$65-96** |

---

## 3. Wave Synthesis Format

Each wave ends with the orchestrator writing a synthesis document. This is the sole handoff between wave sessions.

**File**: `docs/targets/full-system/artifacts/wave-{N}-synthesis.md`

```markdown
# Wave {N} Synthesis
Generated: {timestamp}
Agents: {list with model, turns used, status}

## Hot Spots (ranked by confidence)
1. **[location]** — [1-line description] — confidence: [H/M/L]
2. ...

## Confirmed Findings
(full finding template from boilerplate, copied from agent disk artifacts)

## Ruled-Out Vectors (summary)
- [vector] → [1-line reason] — agent: {name}

## Cross-Boundary Concerns
(from cross-contract-tracer)

## Recommended Wave {N+1} Focus
- Agent 1: [scope] — because [hot spot reference]
- Agent 2: ...

## Open Questions
(anything unresolved that needs investigation)
```

Wave N+1 agents receive: their spawn prompt + `wave-{N}-synthesis.md`. They don't re-read prior wave agent metrics — the synthesis is the curated handoff.

---

## 4. Spawn Prompt Templates

### 4.1 Recon Template (Wave 1)

```markdown
---
name: recon-{scope}
model: sonnet
isolation: worktree
max_turns: 15
max_cost_usd: 3.00
---

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` then `docs/CODEBASE_MAP.md`.

## Memory (read before investigating)
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`
- **Patterns to find**: `docs/audit_memory/confirmed-patterns.md`

## Your Scope
- **Repos**: {list of repos this agent covers}
- **Read ALL source files** in these repos
- **Do NOT write code** — this is analysis only
- **Read also**: Phase 0 artifacts for your repos (slither, aderyn, storage layouts)

## Objective
Produce `docs/targets/full-system/artifacts/wave1-recon-{name}.md` with:

1. **Entry point inventory**: Every external/public state-changing function
2. **Vector triage**: For each attack vector below, classify
   Skip / Borderline / Survive (same methodology as boilerplate)
3. **Top-5 hot spots**: Ranked by suspicion, with 2-3 sentence rationale each
4. **Cross-boundary flags**: Functions that call into other repos
5. **Complexity assessment**: Which sub-modules need dedicated deep agents in wave 2

## Attack Vectors to Triage
{target-specific list — drawn from known-vuln-patterns.md + module-specific vectors}

## Recommended Skills (invoke via Skill tool)
- `audit-context-building:audit-context-building` — run FIRST
- `entry-point-analyzer:entry-point-analyzer` — map entry points

## Shared Standards
Deliverable format, severity rubric, and incremental writing requirements
are defined in `docs/framework/agent-boilerplate.md`.
```

### 4.2 Deep Analysis Template (Waves 2-3)

Same structure as v2 hooks-and-handlers spawn prompts:

- YAML frontmatter (name, model, isolation, max_turns, max_cost_usd)
- First Action: read boilerplate + codebase map
- Memory section: digest, FPs, confirmed patterns
- Your Domain: owned files, do-NOT-modify, read-only access
- **NEW**: Read also includes `wave-{N-1}-synthesis.md`
- Known Findings: from prior waves (do NOT re-report)
- Attack Vectors: triage pass, composability check, hunt-for list
- Recommended Skills
- Shared Standards
- Required: Write Progress to Disk Incrementally

The only change from v2 is the addition of wave synthesis in "Read also" and updated file paths pointing to `docs/targets/full-system/artifacts/`.

### 4.3 Cross-Cutting Template (Waves 4-5)

Ports from v2 with scope expanded:
- fuzz-writer: targets ALL repos, invariants from wave 2-3 findings
- poc-writer: receives ALL confirmed findings from waves 2-3
- red-team: challenges ALL findings + proof sketches
- economic-analyst: models fee flows across full system

---

## 5. Phase 0: Artifact Generation

### Tier 1 — Automated (scripted, `artifact_generator.py`)

Run Slither + Aderyn on each of the 5 new repos. ~40 min total.

| Artifact | Tool | Per-repo |
|----------|------|----------|
| Static analysis findings | Slither `run_detectors` | `phase0/{repo}-slither.md` |
| Call graphs | Slither `export_call_graph` | `phase0/{repo}-callgraph.md` |
| Storage layouts | Slither `get_storage_layout` | `phase0/{repo}-storage.md` |
| Entry points | Slither `list_functions` | `phase0/{repo}-entries.md` |
| Dead code | Slither `find_dead_code` | `phase0/{repo}-deadcode.md` |
| Aderyn findings | `aderyn .` | `phase0/{repo}-aderyn.md` |

### Tier 2 — Analytical (Wave 0 or manual)

| Artifact | Description | Generator |
|----------|-------------|-----------|
| Access control matrix | Who can call what across all repos | Wave 0 agent or manual |
| Cross-boundary call graph | All cross-repo delegatecalls and callbacks | Wave 1 cross-contract-tracer |
| Token flow | Where tokens move across the system | Wave 0 agent or manual |
| External interfaces | Trust boundaries between repos | Wave 1 cross-contract-tracer |
| Coverage gaps | What's untested per repo | Wave 0 agent or manual |
| Novel attack surface | Transient storage, assembly, unchecked math | Wave 1 recon agents |

### Tier 3 — Carried Forward

| Artifact | Source |
|----------|--------|
| All hooks-and-handlers artifacts | `docs/targets/hooks-and-handlers/artifacts/` |
| Memory system | `docs/audit_memory/` (digest, FPs, confirmed patterns, lessons) |
| Known vuln patterns | `docs/framework/known-vuln-patterns.md` |
| Codebase map | `docs/CODEBASE_MAP.md` |

---

## 6. SDK Orchestrator Structure

```
docs/orchestrator/
├── __init__.py
├── run_audit.py              # Main entry point (CLI: --wave N, --dry-run)
├── config.py                 # Wave definitions, agent configs, budgets (Python dataclasses)
├── wave_runner.py            # Spawns agents for a wave, waits, collects
├── prompt_renderer.py        # Combines templates with scope/synthesis context
├── synthesizer.py            # Reads agent artifacts → writes synthesis doc
├── artifact_generator.py     # Phase 0: runs Slither/Aderyn per repo (automated)
└── templates/
    ├── recon-agent.md        # Wave 1 recon template
    ├── cross-contract-tracer.md # Wave 1 cross-boundary tracer
    ├── deep-agent.md         # Waves 2-3 deep analysis template
    ├── economic-analyst.md   # Wave 3 economic modeling
    ├── fuzz-writer.md        # Wave 4 fuzz/invariant test generation
    ├── poc-writer.md         # Wave 5 exploit PoC creation
    └── red-team-adversary.md # Wave 5 adversarial review
```

> **Note:** Wave configs are Python dataclasses in `config.py` (not YAML files).
> Wave 1 is fully defined; waves 2-5 are dynamic templates populated after prior synthesis.

### Core Loop (`run_audit.py`)

```python
async def run_audit():
    # Phase 0: Generate artifacts
    await artifact_generator.run_all_repos()

    for wave_num in range(1, 6):
        # 1. Load wave config
        wave_config = load_wave_config(wave_num)

        # 2. Load previous synthesis (if wave > 1)
        prior_synthesis = read_synthesis(wave_num - 1) if wave_num > 1 else None

        # 3. Render spawn prompts
        prompts = render_prompts(wave_config, prior_synthesis)

        # 4. Spawn all agents (parallel, worktree isolation)
        results = await wave_runner.spawn_wave(prompts)

        # 5. Collect metrics
        metrics = wave_runner.collect_metrics(results)

        # 6. Read agent disk artifacts
        artifacts = wave_runner.read_artifacts(wave_config)

        # 7. Generate synthesis
        synthesis = await synthesizer.generate(wave_num, artifacts, metrics)

        # 8. Adjust next wave config if needed
        if wave_num < 5:
            adjust_wave_config(wave_num + 1, synthesis)

    # Final: generate report + update memory
    await synthesizer.generate_final_report()
    await update_memory_system()
```

---

## 7. Target Directory Structure

```
docs/targets/full-system/
├── spawn-prompts/
│   ├── recon-core.md
│   ├── recon-pools.md
│   ├── recon-hooks.md
│   ├── cross-contract-tracer.md
│   ├── core-swap-auditor.md          # wave 2-3 (post wave 1 synthesis)
│   ├── core-liquidity-auditor.md
│   ├── dynamic-pool-auditor.md
│   ├── fixed-pool-auditor.md
│   ├── hooks-auditor.md
│   ├── economic-analyst.md
│   ├── fuzz-writer.md
│   ├── poc-writer.md
│   └── red-team-adversary.md
├── artifacts/
│   ├── phase0/                        # Slither/Aderyn per repo
│   │   ├── lbamm-core-slither.md
│   │   ├── lbamm-core-aderyn.md
│   │   ├── lbamm-core-storage.md
│   │   ├── lbamm-core-entries.md
│   │   ├── lbamm-core-deadcode.md
│   │   ├── lbamm-core-callgraph.md
│   │   └── ... (per repo × 6 artifacts)
│   ├── wave1-recon-core.md
│   ├── wave1-recon-pools.md
│   ├── wave1-recon-hooks.md
│   ├── wave1-cross-contract.md
│   ├── wave1-synthesis.md
│   ├── wave2-*.md
│   ├── wave2-synthesis.md
│   ├── wave3-*.md
│   ├── wave3-synthesis.md
│   ├── wave4-*.md
│   ├── wave4-synthesis.md
│   ├── wave5-*.md
│   └── wave5-synthesis.md
└── results/
    ├── findings-report.md
    ├── session-report.md
    ├── metrics.json
    └── agent-metrics-*.md
```

---

## 8. Implementation Plan

### Step 1: Create directory structure
- `docs/targets/full-system/spawn-prompts/`
- `docs/targets/full-system/artifacts/phase0/`
- `docs/targets/full-system/results/`
- `docs/orchestrator/`

### Step 2: Write SDK orchestrator
- `config.py` with wave definitions
- `artifact_generator.py` for Phase 0 automation
- `wave_runner.py` for agent spawning
- `synthesizer.py` for between-wave synthesis
- `run_audit.py` main entry point

### Step 3: Write wave 1 spawn prompts
- `recon-core.md` (lbamm-core + secure-proxy)
- `recon-pools.md` (dynamic + fixed + single-provider)
- `recon-hooks.md` (hooks-and-handlers, fresh eyes)
- `cross-contract-tracer.md` (all repos, adapted from v2)

### Step 4: Adapt framework docs
- Update `agent-boilerplate.md` target repos list
- Update `execution-runbook.md` with wave mapping reference
- No changes to: known-vuln-patterns, operational-checklist, memory system

### Step 5: Run Phase 0
- Slither + Aderyn on all 5 new repos
- Store in `docs/targets/full-system/artifacts/phase0/`

### Step 6: Execute waves 1-5
- SDK orchestrator handles spawning, collection, synthesis
- Manual review between waves for synthesis quality

### Step 7: Post-run
- Final findings report
- Memory system update (digest, new FPs, new confirmed patterns, new lessons)
- Framework retrospective (what worked, what to change for N=3)

---

## 9. Open Questions

1. **Wave 0 (analytical artifacts)**: Generate manually or spawn 1-2 agents? Depends on time budget.
2. **Wave 2 roster**: Exact agents determined by wave 1 synthesis. Design doc provides likely assignments.
3. **SDK maturity**: `claude-agent-sdk==0.1.48` — may need workarounds for edge cases.
4. **hooks-and-handlers coverage**: Fresh-eyes recon may surface things v1/v2 missed, but also may waste turns on known FPs. Balance via memory system injection.
5. **Cross-repo fuzz tests**: Where do tests live? Each repo has its own `foundry.toml`. Fuzz-writer may need to work across repos.
