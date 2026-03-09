# Tool Integration Wiring — Aderyn, Quimera, Trail of Bits Skills

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire three new tools (Aderyn, Quimera, Trail of Bits Claude Code Skills) into every touchpoint of the audit system so agents discover and use them reliably.

**Architecture:** The tools are already documented in the two canonical tool files (`agent-boilerplate.md`, `tool-guide.md`). This plan wires them into the execution flow: spawn prompts, execution runbook, artifact registry, team design reference, and operational checklist.

**Tech Stack:** Markdown edits only — no code changes.

**Prerequisites:** Aderyn v0.6.8, Quimera v0.1, and 9 Trail of Bits skills plugins already installed and documented in `agent-boilerplate.md` + `tool-guide.md`.

---

### Task 1: Add Aderyn findings as Phase 0 artifact

**Files:**
- Modify: `docs/artifacts/README.md`
- Modify: `docs/execution-runbook.md`

**Step 1: Add P0-22 to artifact registry**

In `docs/artifacts/README.md`, add row after P0-21 (line 29):

```markdown
| P0-22 | `aderyn-findings.md` | Aderyn static analysis results | aderyn | all auditors |
```

Update line 31 total count from "20 artifact files" to "21 artifact files (P0-01 through P0-22, P0-13 intentionally skipped)".

Update verification script (line 48) — add `22` to the ID loop:
```bash
for id in 01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 18 19 20 21 22; do
```

Update line 57 echo from "All 20" to "All 21".

Add P0-22 to the consumer quick-reference (line 66): auditors read list gets P0-22.

**Step 2: Update execution runbook Phase 0**

In `docs/execution-runbook.md`, update line 11 from "20 artifacts" to "21 artifacts".

Update line 19 verification script — add `22` to the ID loop:
```bash
for id in 01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 18 19 20 21 22; do
```

Update line 28 echo from "All 20" to "All 21".

Update line 37 gate from "all 20" to "all 21".

**Step 3: Generate the actual Aderyn artifact**

Run: `aderyn . 2>&1 | head -5` to verify it works on this project.
Then save output: move `report.md` to `docs/artifacts/aderyn-findings.md`.
Add the P0-ID header to the file:
```markdown
> **ID:** P0-22 | **Generated:** 2026-03-02 | **Method:** aderyn
> **Readers:** all auditors
```

**Step 4: Verify**

Run the updated verification script. Expected: "All 21 P0-ID artifacts present".

---

### Task 2: Update all 4 auditor spawn prompts — add Aderyn artifact + skill recommendations

**Files:**
- Modify: `docs/spawn-prompts/clob-auditor.md`
- Modify: `docs/spawn-prompts/permit-auditor.md`
- Modify: `docs/spawn-prompts/hook-auditor.md`
- Modify: `docs/spawn-prompts/registry-auditor.md`

**Step 1: Add `aderyn-findings.md` to Read also lists**

In each auditor's `Read also` list (line 19 in all 4 files), add `docs/artifacts/aderyn-findings.md` after `docs/artifacts/slither-findings.md`.

**Step 2: Add skill recommendations section**

In each auditor file, add a new section before `## Shared Standards`:

For `clob-auditor.md` (before line 56):
```markdown
## Recommended Skills (invoke via Skill tool)
- `audit-context-building:audit-context-building` — run FIRST to build deep architectural context
- `entry-point-analyzer:entry-point-analyzer` — map all state-changing entry points in your module
- `spec-to-code-compliance:spec-to-code-compliance` — verify code matches spec (use with `docs/artifacts/spec-vs-code.md`)
- `variant-analysis:variant-analysis` — after finding a vulnerability, search for similar patterns
```

For `permit-auditor.md` (before line 45):
```markdown
## Recommended Skills (invoke via Skill tool)
- `audit-context-building:audit-context-building` — run FIRST to build deep architectural context
- `entry-point-analyzer:entry-point-analyzer` — map all state-changing entry points in your module
- `building-secure-contracts:token-integration-analyzer` — analyze ERC20/permit token integration patterns
- `variant-analysis:variant-analysis` — after finding a vulnerability, search for similar patterns
```

For `hook-auditor.md` (before line 50):
```markdown
## Recommended Skills (invoke via Skill tool)
- `audit-context-building:audit-context-building` — run FIRST to build deep architectural context
- `entry-point-analyzer:entry-point-analyzer` — map all state-changing entry points in your module
- `sharp-edges:sharp-edges` — identify footgun APIs in hook flag configuration
- `variant-analysis:variant-analysis` — after finding a vulnerability, search for similar patterns
```

For `registry-auditor.md` (before line 44):
```markdown
## Recommended Skills (invoke via Skill tool)
- `audit-context-building:audit-context-building` — run FIRST to build deep architectural context
- `entry-point-analyzer:entry-point-analyzer` — map all state-changing entry points in your module
- `sharp-edges:sharp-edges` — identify footgun APIs in settings/config interfaces
- `variant-analysis:variant-analysis` — after finding a vulnerability, search for similar patterns
```

---

### Task 3: Update poc-writer spawn prompt — add Quimera + variant-analysis

**Files:**
- Modify: `docs/spawn-prompts/poc-writer.md`

**Step 1: Add Tools section after Workflow (after line 25)**

```markdown
## Tools
- **Forge**: `forge test --match-test <test_name> -vvv` — compile and run PoC tests
- **Quimera**: `~/.local/bin/quimera` — LLM-driven exploit PoC generation. For confirmed vulnerabilities, use Quimera to auto-generate a Foundry PoC, then refine manually. Usage: `quimera <ContractName> . --contract <ContractName> --working-dir . --attachment <finding-description.txt> --iterations 5`. See `docs/artifacts/tool-guide.md` for full details.
```

**Step 2: Add skill recommendation (after the new Tools section)**

```markdown
## Recommended Skills (invoke via Skill tool)
- `variant-analysis:variant-analysis` — after confirming a PoC, check if the vuln pattern exists elsewhere in the codebase
```

---

### Task 4: Update fuzz-writer spawn prompt — add property-based-testing skill

**Files:**
- Modify: `docs/spawn-prompts/fuzz-writer.md`

**Step 1: Add Aderyn to Tools section (after line 21)**

Add after the Halmos line:
```markdown
- **Aderyn**: `aderyn . --src src/<module>/` — complementary static analysis (different detectors than Slither, useful for identifying functions with arithmetic issues worth fuzz-testing)
```

**Step 2: Add skill recommendation (after Tools section, before "## Target")**

```markdown
## Recommended Skills (invoke via Skill tool)
- `property-based-testing:property-based-testing` — run FIRST to guide invariant and property selection before writing tests
- `entry-point-analyzer:entry-point-analyzer` — identify which state-changing functions to target with fuzz tests
```

---

### Task 5: Update red-team-adversary spawn prompt — add tool-guide + skills

**Files:**
- Modify: `docs/spawn-prompts/red-team-adversary.md`

**Step 1: Add `tool-guide.md` to Read list (line 16)**

Currently missing. Add `docs/artifacts/tool-guide.md` to the Read list after `docs/artifacts/cross-boundary-call-graph.md`.

**Step 2: Add skill recommendation (before "## Anti-Patterns", line 45)**

```markdown
## Recommended Skills (invoke via Skill tool)
- `differential-review:differential-review` — security-focused review of remediation diffs
- `sharp-edges:sharp-edges` — challenge API designs and configuration safety assumptions
```

---

### Task 6: Update economic-analyst spawn prompt — add token-integration-analyzer skill

**Files:**
- Modify: `docs/spawn-prompts/economic-analyst.md`

**Step 1: Add skill recommendation (after Tools section, before "## Specific Analysis Tasks", line 24)**

```markdown
## Recommended Skills (invoke via Skill tool)
- `building-secure-contracts:token-integration-analyzer` — analyze token economics, weird token patterns, and owner privileges
```

---

### Task 7: Update team-design.md — add new tools to reference table

**Files:**
- Modify: `docs/team-design.md`

**Step 1: Add 3 rows to Tools table (after line 196)**

```markdown
| Aderyn | `/opt/homebrew/bin/aderyn` (v0.6.8) | Rust-based Solidity static analyzer (Cyfrin). Complements Slither with different detector set. | All auditors |
| Quimera | `~/.local/bin/quimera` (v0.1) | LLM-driven exploit PoC generation using Foundry (by Echidna creator). | poc-writer |
| Trail of Bits Skills | via `Skill()` tool | 9 Claude Code skills for security analysis (audit-context-building, entry-point-analyzer, variant-analysis, etc.) | All agents |
```

**Step 2: Update parenthetical at line 487**

Change:
```
Tools Available (Slither MCP, Exa MCP, Forge, Chisel, Halmos, Medusa, Python/Jupyter)
```
To:
```
Tools Available (Slither MCP, Exa MCP, Forge, Chisel, Halmos, Medusa, Aderyn, Quimera, Python/Jupyter, Trail of Bits Skills)
```

**Step 3: Add cross-reference after line 196**

```markdown
> **Detailed usage for Aderyn, Quimera, and Trail of Bits Skills:** See `docs/artifacts/tool-guide.md` (P0-12). The tool-guide is the canonical reference for usage commands, gotchas, and per-role skill recommendations.
```

---

### Task 8: Update operational checklist — add verification items for new tools

**Files:**
- Modify: `docs/operational-checklist.md`

**Step 1: Add 3 new rows after item 35**

```markdown
| 36 | Aderyn output overwrites `report.md` | Use `--output aderyn-report.md` or rename before running alongside other tools | tool-guide.md (Aderyn Gotchas) |
| 37 | Quimera needs LLM API or manual mode | Verify model availability before spawning poc-writer, or use manual mode (no API key needed) | tool-guide.md (Quimera Gotchas) |
| 38 | Skills invoked as CLI instead of Skill() | Skills are conversation-internal AI tools. Invoke via `Skill("name:name")`, not bash. Agents discover via boilerplate. | agent-boilerplate.md (Skills table) |
```

---

### Task 9: Update P0-12 tool-guide.md description in artifact registry

**Files:**
- Modify: `docs/artifacts/README.md`

**Step 1: Update P0-12 description (line 20)**

Change:
```
| P0-12 | `tool-guide.md` | Chisel/Halmos/Medusa/git-diff usage | manual | all agents |
```
To:
```
| P0-12 | `tool-guide.md` | Chisel/Halmos/Medusa/Aderyn/Quimera/Skills/git-diff usage | manual | all agents |
```

---

### Task 10: Run Aderyn scan and generate P0-22 artifact

**Step 1: Run Aderyn on the project**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers
aderyn .
```

**Step 2: Move and format output**

```bash
mv report.md docs/artifacts/aderyn-findings.md
```

Prepend the P0-ID header to the file.

**Step 3: Run full verification**

```bash
cd docs/artifacts
missing=0
for id in 01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 18 19 20 21 22; do
  file=$(grep -rl "ID:.*P0-$id" . --include='*.md' 2>/dev/null | grep -v README.md | head -1)
  if [ -z "$file" ]; then echo "MISSING: P0-$id"; missing=$((missing + 1))
  else echo "OK: P0-$id → $(basename $file)"; fi
done
[ $missing -eq 0 ] && echo "All 21 P0-ID artifacts present — Phase 0 gate PASSED"
```

Expected: All 21 present.

---

### Task 11: Commit

```bash
git add docs/artifacts/README.md docs/artifacts/aderyn-findings.md docs/artifacts/agent-boilerplate.md docs/artifacts/tool-guide.md docs/execution-runbook.md docs/operational-checklist.md docs/team-design.md docs/spawn-prompts/*.md docs/plans/2026-03-02-tool-integration-wiring.md
git commit -m "feat: wire Aderyn, Quimera, and Trail of Bits skills across audit system"
```

---

## Success Criteria

- [ ] P0-22 (`aderyn-findings.md`) exists and passes verification
- [ ] All 4 auditor spawn prompts reference Aderyn artifact + skill recommendations
- [ ] poc-writer references Quimera in Tools section
- [ ] fuzz-writer references `property-based-testing` skill
- [ ] red-team-adversary has `tool-guide.md` in Read list + skill recommendations
- [ ] economic-analyst references `token-integration-analyzer` skill
- [ ] team-design.md tools table has Aderyn, Quimera, ToB Skills rows
- [ ] operational-checklist has items 36-38 for new tools
- [ ] artifact registry P0-12 description updated
- [ ] Verification script passes with 21 artifacts
- [ ] All changes committed
