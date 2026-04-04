# Right-Size Expectations & Fix Infrastructure

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the gap between agent output and compliance scoring by (a) right-sizing Phase A/B expected counts to match actual conditionality, (b) making Phase B skills mandatory via the sidecar gate, and (c) fixing stale agent detection.

**Architecture:** The scorer inflates expected counts — A5 (storage layout) is counted for all 9 agents but only applies to 2, B4/B5 are counted universally but are conditional. Fixing this drops expected totals by 6-8 items per agent, immediately boosting checklist %. On the infrastructure side, Phase B skills exist but agents skip them because the gate doesn't enforce them. Adding `audit-context-building` and `entry-point-analyzer` to REQUIRED_TOOLS (or a separate gate check) forces agents to invoke them. Finally, stale agents (precision-sniper: 0 turns) need detection and re-scoring exclusion.

**Tech Stack:** Python 3.13, compliance.py, sidecar_gate.py, black-hat-preamble.md

**Expected impact:**

| Change | Target dimension | Expected pts |
|--------|-----------------|-------------|
| Right-size Phase A (A5 conditional) | checklist | +2-4 |
| Right-size Phase B (B4/B5 conditional) | checklist | +2-3 |
| Enforce Phase B skills in gate | tool_breadth (bonus) | +3-5 |
| Exclude stale agents from aggregate | all | +3-4 |
| **Total** | | **+10-16** |

---

## Task 1: Right-size Phase A expected counts

**Files:**
- Modify: `docs/orchestrator/compliance.py` (lines 28-31, line 77)

A5 (storage layout) only applies to cross-boundary and state-desync (preamble line 226 says so explicitly). The scorer currently counts 5 items per repo for ALL agents. Fix: 4 per repo baseline, +1 for A5 agents.

- [ ] **Step 1: Add A5 agent set and update Phase A constant**

In `docs/orchestrator/compliance.py`, after the `CHECKLIST_EXPECTED` dict (line 26), replace the Phase A/B constants:

Find:
```python
# Phase A has 5 items per repo. Phase B has 3-5 items. Phase D has 4 items.
PHASE_A_ITEMS_PER_REPO = 5
PHASE_B_ITEMS = 5
PHASE_D_ITEMS = 4
```

Replace with:
```python
# Phase A: 4 base items per repo (A1-A4). A5 (storage layout) only for specific agents.
PHASE_A_BASE_PER_REPO = 4
PHASE_A5_AGENTS = {"cross-boundary", "state-desync"}

# Phase B: 3 base items (B1-B3). B4 only for C-MATH agents. B5 is conditional (never counted).
PHASE_B_BASE = 3
PHASE_B4_AGENTS = {"precision-sniper", "math-deep-diver", "price-distorter"}

PHASE_D_ITEMS = 4
```

- [ ] **Step 2: Update the expected_total formula**

In `_score_checklist()`, replace the expected_total calculation (line 77):

Find:
```python
    expected_total = (PHASE_A_ITEMS_PER_REPO * num_repos) + PHASE_B_ITEMS + expected_c + PHASE_D_ITEMS
```

Replace with:
```python
    phase_a = PHASE_A_BASE_PER_REPO * num_repos
    if agent_name in PHASE_A5_AGENTS:
        phase_a += num_repos  # A5 adds 1 item per repo
    phase_b = PHASE_B_BASE + (1 if agent_name in PHASE_B4_AGENTS else 0)
    expected_total = phase_a + phase_b + expected_c + PHASE_D_ITEMS
```

- [ ] **Step 3: Verify the impact**

```bash
.venv/bin/python3 -c "
from docs.orchestrator.compliance import score_wave
rc = score_wave(1)
print(f'Aggregate: {rc.aggregate_score}/100 ({rc.grade})')
for a in rc.agents:
    d = a.details
    if d.get('gate_bypassed'): continue
    ck = d.get('checklist', {})
    print(f'{a.name:30s}  {a.total:5.1f} ({a.grade})  ck={a.checklist_score:.0f}/30 ({ck[\"completed\"]}/{ck[\"expected\"]} = {ck[\"pct\"]:.0f}%)')
"
```

Expected: checklist percentages increase by ~10-15% for most agents (lower expected denominators).

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/compliance.py
git commit -m "fix: right-size Phase A/B expected counts — A5 and B4 are conditional, not universal"
```

---

## Task 2: Enforce Phase B skills in sidecar gate

**Files:**
- Modify: `docs/orchestrator/sidecar_gate.py` (add Phase B check)
- Modify: `docs/orchestrator/compliance.py` (Step 4: move Phase B to REQUIRED_TOOLS + fix hyphen normalization)

Phase B skills (audit-context-building, entry-point-analyzer) exist and are invocable. Agents skip them because the gate doesn't check. Currently `REQUIRED_TOOLS` is slither/aderyn/forge/halmos/medusa. Add the two mandatory Phase B skills.

- [ ] **Step 1: Add Phase B tools to gate validation**

In `docs/orchestrator/sidecar_gate.py`, after the existing `REQUIRED_TOOLS` set (line 16), add:

```python
# Phase B skills — mandatory for all agents (B1, B2)
REQUIRED_PHASE_B = {"audit-context-building", "entry-point-analyzer"}
```

Then in the `validate()` function, after the existing tool breadth check (after the `if missing:` block, around line 41), add a second check:

```python
    # Phase B skill check (fuzzy match)
    phase_b_found = set()
    for skill in REQUIRED_PHASE_B:
        for k, v in tools_run.items():
            if skill.replace("-", "_") in k.lower().replace("-", "_"):
                ran = (v is True) or (isinstance(v, dict) and v.get("ran"))
                if ran:
                    phase_b_found.add(skill)
                    break
    missing_b = REQUIRED_PHASE_B - phase_b_found
    if missing_b:
        errors.append(
            f"MISSING PHASE B SKILLS ({len(missing_b)}): {', '.join(sorted(missing_b))}. "
            f"Invoke each via Skill() and log in metadata.tools_run."
        )
```

- [ ] **Step 2: Test rejection with missing Phase B**

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path
# Has all 5 tools but no Phase B skills
bad = {
    'agent_name': 'test',
    'ruled_out_vectors': [{'vector': f'v{i}', 'test_file': f'test/A{i}.t.sol', 'why_ruled_out': 'g'} for i in range(10)],
    'findings': [],
    'metadata': {
        'tools_run': {
            'forge': {'ran': True}, 'halmos': {'ran': True},
            'medusa': {'ran': True}, 'slither': {'ran': True},
            'aderyn': {'ran': True}
        }
    }
}
Path('/tmp/test-draft.json').write_text(json.dumps(bad))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
```

Expected: REJECTED with "MISSING PHASE B SKILLS (2): audit-context-building, entry-point-analyzer", exit code 1.

- [ ] **Step 3: Test acceptance with Phase B**

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path
good = {
    'agent_name': 'test',
    'ruled_out_vectors': [{'vector': f'v{i}', 'test_file': f'test/A{i}.t.sol', 'why_ruled_out': 'g'} for i in range(10)],
    'findings': [],
    'metadata': {
        'tools_run': {
            'forge': {'ran': True}, 'halmos': {'ran': True},
            'medusa': {'ran': True}, 'slither': {'ran': True},
            'aderyn': {'ran': True},
            'audit-context-building': {'ran': True},
            'entry-point-analyzer': {'ran': True}
        }
    }
}
Path('/tmp/test-draft.json').write_text(json.dumps(good))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
```

Expected: ACCEPTED, exit code 0.

- [ ] **Step 4: Move Phase B from BONUS_TOOLS to scored differently in compliance.py**

In `docs/orchestrator/compliance.py`, the Phase B skills are currently in `BONUS_TOOLS` (lines 37-40). Move `audit-context-building` and `entry-point-analyzer` to `REQUIRED_TOOLS` so they contribute to the required score (3 pts each) instead of bonus (1 pt each):

Find:
```python
REQUIRED_TOOLS = {"slither", "aderyn", "forge", "halmos", "medusa"}

# Bonus tools (archetype-specific, give extra credit)
BONUS_TOOLS = {
    "entry-point-analyzer", "audit-context-building",
    "property-based-testing", "variant-analysis",
```

Replace with:
```python
REQUIRED_TOOLS = {"slither", "aderyn", "forge", "halmos", "medusa",
                  "audit-context-building", "entry-point-analyzer"}

# Bonus tools (archetype-specific, give extra credit)
BONUS_TOOLS = {
    "property-based-testing", "variant-analysis",
```

**Note:** This changes tool_breadth scoring: 7 required tools × 3 pts = 21 (capped at 20), so agents with all 7 get full 20/20 from required alone. The 5-pt bonus pool is now just property-based-testing and variant-analysis.

- [ ] **Step 5: Fix hyphen normalization in REQUIRED_TOOLS matching**

The BONUS_TOOLS check normalizes hyphens (`tool.replace("-", "_") in k.lower().replace("-", "_")`) but REQUIRED_TOOLS doesn't. With `audit-context-building` now in REQUIRED_TOOLS, agents logging it as `audit_context_building` would be missed. Fix the required check to normalize too.

In `docs/orchestrator/compliance.py`, in `_score_tool_breadth()` (line 129):

Find:
```python
            if tool in k.lower():
```

Replace (first occurrence only — this is the required tools loop, not the bonus loop):
```python
            if tool.replace("-", "_") in k.lower().replace("-", "_"):
```

- [ ] **Step 6: Commit**

```bash
git add docs/orchestrator/sidecar_gate.py docs/orchestrator/compliance.py
git commit -m "feat: enforce Phase B skills — audit-context-building + entry-point-analyzer now required"
```

---

## Task 3: Handle stale agents in scoring

**Files:**
- Modify: `docs/orchestrator/compliance.py` (`score_wave` or `score_agent`)

precision-sniper had 0 turns (stale artifact from prior run). It scores 41.8 and drags the aggregate from 78.7 to 74.6. Stale agents should be excluded from the aggregate (they didn't run this wave).

- [ ] **Step 1: Add stale detection to score_agent**

`num_turns` is passed as a parameter to `score_agent()` (loaded from the metrics JSON by `score_wave()`), NOT stored in sidecar metadata. In `score_agent()`, after the gate_passed check, add:

```python
    # Stale agent detection: 0 turns means the agent didn't run this wave
    if num_turns == 0:
        c.total = 0.0
        c.grade = "F"
        c.details = {"stale": True, "reason": "0 turns — agent did not run"}
        return c
```

**Note:** This excludes agents where the primary run had 0 turns, even if continuation work was merged. The primary agent failing to spawn is an infrastructure issue — continuation work on a stale base produces incomplete results (precision-sniper: 41.8/100) that drag the aggregate.

- [ ] **Step 2: Exclude stale/zero-score agents from aggregate**

In `score_wave()`, find the aggregate calculation (line 374):

Find:
```python
    aggregate = round(sum(a.total for a in agents) / len(agents), 1)
```

Replace with:
```python
    active_agents = [a for a in agents if a.total > 0]
    aggregate = round(sum(a.total for a in active_agents) / len(active_agents), 1) if active_agents else 0.0
```

- [ ] **Step 3: Verify**

```bash
.venv/bin/python3 -c "
from docs.orchestrator.compliance import score_wave
rc = score_wave(1)
print(f'Aggregate: {rc.aggregate_score}/100 ({rc.grade})')
print(f'Active agents: {sum(1 for a in rc.agents if a.total > 0)}/{len(rc.agents)}')
for a in rc.agents:
    d = a.details
    stale = d.get('stale', False)
    bypassed = d.get('gate_bypassed', False)
    if stale:
        print(f'{a.name:30s}  STALE (excluded)')
    elif bypassed:
        print(f'{a.name:30s}  GATE BYPASSED (excluded)')
    else:
        print(f'{a.name:30s}  {a.total:5.1f} ({a.grade})')
"
```

Expected: precision-sniper marked STALE, excluded. Aggregate recalculated from 8 active agents.

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/compliance.py
git commit -m "fix: exclude stale agents (0 turns) from compliance aggregate"
```

---

## Task 4: Re-score and verify combined impact

**Files:**
- No new changes — verification only

- [ ] **Step 1: Full re-score with all fixes**

```bash
.venv/bin/python3 -c "
from docs.orchestrator.compliance import score_wave
rc = score_wave(1)
print(f'Aggregate: {rc.aggregate_score}/100 ({rc.grade})')
print(f'Weakest: {rc.weakest_dimension}')
print()
for a in rc.agents:
    d = a.details
    if d.get('stale') or d.get('gate_bypassed'):
        print(f'{a.name:30s}  {a.total:5.1f} — EXCLUDED ({\"stale\" if d.get(\"stale\") else \"gate_bypassed\"})')
        continue
    ck = d.get('checklist', {})
    tb = a.tool_breadth_score
    ev = a.evidence_score
    print(f'{a.name:30s}  {a.total:5.1f} ({a.grade})  ck={a.checklist_score:.0f}/30({ck[\"pct\"]:.0f}%)  tb={tb:.0f}/20  ev={ev:.0f}/20  dp={a.depth_score:.0f}/20  th={a.thesis_score:.0f}/10')
"
```

Expected: aggregate in 80-85 range (B grade) from right-sized expectations + stale exclusion. tool_breadth stays at 15/20 (Phase B skills not yet run — need a live run for that).

- [ ] **Step 2: Note for next live run**

The full impact of Task 2 (Phase B enforcement) won't show until a live experiment run, since agents need to actually invoke the skills and pass the gate. The re-score only reflects Tasks 1 and 3 (right-sizing + stale exclusion). Run:

```bash
.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --experiment --description "right-sized expectations + Phase B enforcement + stale exclusion"
```

to see the full combined effect.
