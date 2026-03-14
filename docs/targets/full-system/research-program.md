# Audit Research Program

> Adapted from [karpathy/autoresearch](https://github.com/karpathy/autoresearch).
> Each wave 1 run is an experiment. The goal: maximize audit_score.
> Unlike autoresearch (which only modifies train.py), you modify the ENTIRE
> system — prompts, orchestrator code, SDK wiring, config. Fix the engine,
> not just the fuel.

## The Metric: audit_score (higher = better)

```
audit_score = (
    25 * regression_bugs_found     # 0-4 known bugs → 0-100 pts
  + 40 * confirmed_findings        # each finding = 40 pts (cap 200)
  + 0.15 * tool_compliance_pct     # mandatory tools run → 0-15 pts
  + 0.10 * vectors_ruled_out       # thoroughness → 0-10 pts (cap)
  + 0.10 * forge_test_count        # PoC evidence → 0-10 pts (cap)
)
```

## Files You CAN Modify (the "train.py" — everything is fair game)

### Prompt Layer (what agents see)
| File | What it controls |
|------|-----------------|
| `docs/orchestrator/templates/black-hat-preamble.md` | Exploit-first methodology, mandatory probes, sidecar schema, tool checkpoints |
| `docs/orchestrator/templates/price-distorter.md` | Price manipulation archetype: hypotheses, target map, scope |
| `docs/orchestrator/templates/insolvency-engineer.md` | Bad debt / reserve extraction archetype |
| `docs/orchestrator/templates/state-desync.md` | Reentrancy / transient storage desync archetype |
| `docs/orchestrator/templates/precision-sniper.md` | Math boundary / rounding archetype |
| `docs/orchestrator/templates/auth-forger.md` | Permit / signature forging archetype |
| `docs/orchestrator/templates/extension-hijacker.md` | Hook / handler / pool-type abuse archetype |
| `docs/framework/agent-boilerplate.md` | Environment, tool table, checkpoints, anti-patterns, deliverables |

### Orchestrator Layer (how agents are spawned, managed, evaluated)
| File | What it controls |
|------|-----------------|
| `docs/orchestrator/wave_runner.py` | SDK options, team lead prompt, MCP propagation, artifact collection, safety limits |
| `docs/orchestrator/config.py` | Agent count, archetype selection, scope, profiles, max_turns |
| `docs/orchestrator/model_profiles.py` | Model selection, thinking budget, effort level, system prompt |
| `docs/orchestrator/prompt_renderer.py` | Template rendering, variable substitution, memory injection |
| `docs/orchestrator/synthesizer.py` | Hotspot scoring weights, dedup logic, tool coverage checks, synthesis output format |
| `docs/orchestrator/schema.py` | Sidecar validation rules, required fields |
| `docs/orchestrator/run_audit.py` | Pipeline flow, regression checks, pre-filtering |
| `docs/orchestrator/safety.py` | FP pre-filtering, NOOP matching |
| `docs/orchestrator/memory_lifecycle.py` | Post-run memory updates, episode generation |

### Infrastructure Layer (what tools/resources agents have access to)
| File | What it controls |
|------|-----------------|
| `.claude/settings.local.json` | Tool permissions for spawned agents |
| `docs/orchestrator/harnesses/*.sol` | Reusable exploit test contracts |
| `docs/audit_memory/digest.md` | Memory injected into all agents |
| `docs/audit_memory/false-positives.md` | Known FPs agents should skip |
| `docs/audit_memory/confirmed-patterns.md` | Patterns agents should look for variants of |

## Files You CANNOT Modify (the "prepare.py" — ground truth)

| File | Why |
|------|-----|
| `docs/orchestrator/experiment.py` | Scoring function — changing it invalidates comparisons |
| `docs/orchestrator/regression_cases.json` | Ground truth — the 4 known bugs we must rediscover |
| Target repos (lbamm-core, etc.) | The code being audited — immutable |

## Experiment Loop

```
LOOP:
  1. DIAGNOSE: Read experiments.tsv + latest wave artifacts
     - What is the audit_score bottleneck? (regression? tools? findings?)
     - Read wave1-synthesis.md for tool coverage warnings
     - Read wave1-safety.jsonl for agent failures
     - Read agent findings.json metadata for what agents actually did
     - Check run stdout/stderr for crashes, SDK errors, MCP failures

  2. CLASSIFY the fix needed:
     - SYSTEM FIX: SDK wiring, MCP propagation, artifact collection,
       synthesis parsing, schema validation (agents can't succeed
       because infrastructure is broken)
     - PROMPT FIX: Agent instructions, checkpoint language, hypothesis
       specificity, tool enforcement (agents can succeed but don't
       because instructions are unclear)
     - CONFIG FIX: Agent count, scope, turn budget, thinking budget,
       model selection (agents do the right things but suboptimally)

  3. IMPLEMENT: Modify relevant files. System fixes first — there's no
     point optimizing prompts if MCP servers aren't propagated.

  4. git commit -m "experiment: {category}: {hypothesis}"

  5. RUN: python3 -m docs.orchestrator.run_audit --wave 1 --fresh \
         --experiment --description "{category}: {hypothesis}"

  6. EVALUATE: Check experiments.tsv
     - If audit_score improved → keep (advance)
     - If audit_score same/worse → discard (git reset --hard HEAD~1)

  7. GOTO 1
```

## Diagnostic Checklist (run BEFORE proposing changes)

When audit_score is stuck, systematically check each layer:

### Infrastructure (check first — broken pipes mean 0 signal)
- [ ] Do agents have MCP servers? Check `setting_sources` in wave_runner.py
- [ ] Do agents get tool permissions? Check `.claude/settings.local.json`
- [ ] Does synthesis parse sidecar data correctly? Check synthesis.md ruled-out section
- [ ] Is stop_reason accurate? Check metrics.json for false "missing"
- [ ] Do agents write artifacts to the right paths? Check artifact dirs after run

### Prompts (check second — unclear instructions mean wasted turns)
- [ ] Are mandatory checkpoints INLINE or referenced? Inline = followed, reference = skipped
- [ ] Do agents know HOW to invoke tools? Check tool commands in preamble
- [ ] Are hypotheses specific enough? (function names > abstract patterns)
- [ ] Is the sidecar schema clear? Do agents produce valid JSON?

### Config (check third — suboptimal settings mean diminishing returns)
- [ ] Is max_turns sufficient? Do agents hit the cap before finishing?
- [ ] Is thinking budget useful? Compare 128K vs 32K
- [ ] Are 6 archetypes better than 3? Check for duplicate coverage

## What to Try (ordered by expected impact)

### System fixes (highest expected impact when score = 0)
1. **MCP wiring**: Ensure slither/aderyn MCP servers propagate to agents
2. **Artifact collection**: Fix paths, parsing, validation
3. **Synthesis bugs**: Fix rendering, dedup, scoring
4. **SDK options**: setting_sources, permission_mode, thinking config

### Prompt fixes (medium impact)
5. **Regression seeding**: Add 4 known bug descriptions directly in templates
6. **Tool enforcement**: Inline checkpoint commands (not just references)
7. **Hypothesis specificity**: Exact function:line targets vs abstract patterns
8. **Pre-completion gate**: Checklist agents must verify before finishing

### Config tuning (lower impact, fine-tuning)
9. **Agent count**: 6 vs 3 broader agents
10. **Scope narrowing**: 2 repos vs all 6 per agent
11. **Turn budget**: 30 vs 200
12. **Thinking budget**: 128K vs 64K vs 32K

## Simplicity Criterion (from autoresearch)

All else being equal, simpler is better. A small audit_score improvement that
adds ugly complexity is not worth it. Removing code/prompt sections and getting
equal or better results is a simplification win.

## Real Examples from This Codebase

Experiments already run (manually, before this framework existed):

| Run | Change Category | What Changed | Impact |
|-----|----------------|--------------|--------|
| 1 | baseline | First run, no fixes | 0 findings, 70 vectors, 0% tools |
| 1→2 | system fix | Fix synthesis ruled-out rendering (wrong JSON keys) | Ruled-out vectors now visible |
| 1→2 | system fix | Fix stop_reason (check sidecar, not just report.md) | Agents correctly marked "completed" |
| 1→2 | prompt fix | Strengthen checkpoint 1 language | No effect — agents still skipped |
| 2→3 | system fix | Add setting_sources for MCP propagation | Pending — agents should now have slither |
| 2→3 | prompt fix | Inline tool checkpoints in preamble | Pending — should improve tool compliance |
