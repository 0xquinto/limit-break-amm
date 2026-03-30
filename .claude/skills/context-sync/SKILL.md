---
name: context-sync
description: "Detects git changes and updates stale context files (CLAUDE.md, MEMORY.md, CODEBASE_MAP.md, System Guide). Triggers on: 'sync context', 'check for stale files', 'what changed since last sync', 'refresh context', 'update memory', 'are my files up to date', or when resuming after compaction."
---

# Context Sync

You are a context maintenance agent. Your job is to detect what changed in git, then **actually fix** stale content in the project's context files.

## Step 1: Detect Changes

Run the detection script to get a classified change report:

```bash
python3 ${SKILL_DIR}/scripts/context_sync.py --dry-run
```

If it reports "No changes since last sync", stop — everything is current.

If changes are detected, proceed to Step 2.

## Step 2: Validate Each Context File

For each file below, read the current content, compare claims against the actual codebase, and fix any stale content you find.

### CLAUDE.md

Read `CLAUDE.md` and verify these claims are accurate:

1. **Template list and count** — Run: `ls docs/orchestrator/templates/*.md | grep -v checklist | grep -v preamble | grep -v continuation | grep -v reflection` and count. Update the list if wrong.
2. **Experiment baseline** — Check if the scoring system reference is current. The project uses `compliance_score` (not `audit_score`). Remove outdated baselines.
3. **Dead links** — Check every file path referenced in CLAUDE.md actually exists. Remove or fix dead links.
4. **Wave model description** — Verify against `docs/orchestrator/config.py` (grep for `WAVE_BH1`, `WAVES`).
5. **Run command** — Verify the documented run command actually works (check `run_audit.py` args).

### MEMORY.md

Read the auto-memory file at `~/.claude/projects/*/memory/MEMORY.md`.

For each section, verify key claims:
1. **Agent count and roster** — Verify against `config.py:WAVE_BH1`
2. **max_turns** — Verify against `config.py:AgentConfig.max_turns` default
3. **Checklist counts** (C-MATH, C-STATE, etc.) — Verify against `compliance.py:CHECKLIST_EXPECTED`
4. **Score trajectory** — Don't duplicate volatile data. If MEMORY.md has specific scores, replace with "Read `experiments.tsv` for current scores"
5. **Turn count claims** — Verify against recent run data in `docs/targets/full-system/results/`
6. **Tool/infra claims** — Verify paths, versions, and patterns still exist

When fixing MEMORY.md: use the Write tool to update the file directly. You are authorized to fix factual inaccuracies. Do NOT delete entries — update them. Add a comment like `(updated YYYY-MM-DD)` after corrected claims.

### CODEBASE_MAP.md

If `docs/CODEBASE_MAP.md` does not exist OR if `target_repos` or `orchestrator` categories have changes, invoke cartographer to regenerate it:
```
Skill("cartographer:cartographer")
```

If it exists and no relevant files changed, leave it alone.

### System Guide

If `docs/SYSTEM_GUIDE.md` exists, check if it references the current tool stack, agent profiles, and workflow. Flag major gaps but don't rewrite the whole guide — just fix specific outdated facts.

### README.md

If `README.md` does not exist, create it. If it exists, verify it's current.

The README is the project's front door. Generate it from current code state:

1. **Read** `CLAUDE.md` for the project overview, stack, and target repos
2. **Read** `docs/orchestrator/config.py` for agent count, wave config, max_turns
3. **Read** `docs/orchestrator/model_profiles.py` for model profiles
4. **Read** `docs/orchestrator/compliance.py` for CHECKLIST_EXPECTED and scoring dimensions
5. **Count** tests: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ --co -q 2>&1 | tail -1`

Write `README.md` with this structure:

```markdown
# Limit Break AMM — Security Audit Framework

> AI-powered security audit orchestrator for the Guardian Defender contest.

## What This Is
[1-2 sentences from CLAUDE.md overview]

## Quick Start
[Run command, venv setup, prerequisites]

## Architecture
[Mermaid diagram from CODEBASE_MAP.md if it exists, else a simple text description]

## Agent Roster
[Table: agent name, model, scope, checklist — from config.py]

## Compliance Scoring
[6 dimensions, max 120, grade thresholds — from compliance.py]

## Tools
[7 required tools + 3 bonus tools — from preamble]

## Project Structure
[Condensed directory tree — from CODEBASE_MAP.md or ls]

## Links
- [Codebase Map](docs/CODEBASE_MAP.md)
- [System Guide](docs/SYSTEM_GUIDE.md)
- [Experiment History](docs/targets/full-system/experiments.tsv)
```

Keep the README concise — under 200 lines. It should give a new contributor enough context to run an audit in 5 minutes.

## Step 3: Update Checkpoint

After all fixes, run the script without `--dry-run` to save the checkpoint:

```bash
python3 ${SKILL_DIR}/scripts/context_sync.py
```

This updates `.context-sync-state.json` and appends to the sync log.

## Step 4: Report

Summarize what you found and fixed:
- Number of stale items found per file
- What was corrected
- Any gaps that need manual attention (e.g., missing CODEBASE_MAP.md)

## Gotchas

- MEMORY.md is owned by the auto-memory system, but you CAN fix factual errors (wrong counts, outdated claims). Don't restructure it.
- Don't duplicate volatile data (experiment scores, run counts) in MEMORY.md — point to the source file instead.
- If the checkpoint is missing, the first run detects everything as changed. Use `--reset` to initialize: `python3 ${SKILL_DIR}/scripts/context_sync.py --reset`
- The SessionStart hook runs the script in `--auto` mode (detection only, no fixes). Full fixes require this skill to be invoked explicitly.
- CLAUDE.md patches from the script are HTML comments (`<!-- context-sync: ... -->`). Your manual fixes go in the actual content.

## File Structure

```
scripts/
  context_sync.py       # Change detection script
  test_context_sync.py  # Tests (7 cases)
references/
  hook-setup.md         # SessionStart hook configuration
```
