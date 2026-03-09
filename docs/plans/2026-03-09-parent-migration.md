# Framework Migration to Parent Directory — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the audit framework from `lbamm-hooks-and-handlers/` to the parent `limit-break-amm/`, giving the orchestrator/lead context over all repos and enabling N=2 on lbamm-core without duplicating framework docs.

**Architecture:** Init a git repo at the parent to track framework docs only (target repos gitignored). Framework docs (spawn-prompts, memory, runbook, boilerplate, plans, references) move to `docs/`. Target-specific artifacts (slither, aderyn, coverage, findings) move to `docs/targets/{target-name}/`. Spawn prompts split into base templates (framework sections) + target overrides (domain, files, known findings). All 26 absolute paths converted to relative. Auto-memory migrated to new project path.

**Tech Stack:** Git, Markdown, shell. No new dependencies.

**Key insight:** `forge build`, `slither`, `halmos` still run inside each target repo. Only the framework/orchestration layer moves to the parent.

---

### Task 1: Init parent git repo and directory structure

**Files:**
- Create: `limit-break-amm/.gitignore`
- Create: `limit-break-amm/CLAUDE.md`

**Step 1: Init git repo at parent**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm
git init
```

**Step 2: Create .gitignore**

Gitignore all target repos (they have their own git). Only track `docs/` and `CLAUDE.md`.

```gitignore
# Target repos (own git repos — do NOT track)
lbamm-hooks-and-handlers/
lbamm-core/
lbamm-pool-type-dynamic/
lbamm-pool-type-fixed/
lbamm-pool-type-single-provider/
amm-pool-type-dynamic/
secure-proxy/

# Build artifacts
out/
cache/
node_modules/

# OS
.DS_Store
```

**Step 3: Create CLAUDE.md**

```markdown
## Codebase Overview

Limit Break AMM security audit framework. This parent directory orchestrates audits across multiple target repos in the Guardian Defender contest (Feb-Apr 2026).

**Stack**: Solidity 0.8.24, Foundry, cancun EVM, PermitC (EIP-712), Creator Token Standards
**Framework**: `docs/` contains shared methodology, agent spawn prompts, memory system, and per-target artifacts.

**Target repos** (each has its own git repo, not tracked here):
- `lbamm-hooks-and-handlers/` — Transfer handlers (CLOB, permit) + AMM hooks (target 1, audited v1+v2)
- `lbamm-core/` — Core AMM module, pool management, math libraries (target 2, pending N=2)
- `secure-proxy/` — Proxy infrastructure (dependency, read-only)

**Build tools run inside each target repo** — `cd lbamm-hooks-and-handlers/ && forge build`. This parent is for framework/orchestration only.

**Structure**:
- `docs/framework/` — Shared rubrics, runbook, tool guide, patterns
- `docs/spawn-prompts/` — Base agent templates (framework sections)
- `docs/memory/` — Hierarchical memory system (digest, FPs, patterns, lessons, episodes)
- `docs/targets/{name}/` — Per-target artifacts, results, spawn-prompt overrides
- `docs/plans/` — Implementation plans
- `docs/references/` — Research materials

For architecture details, see [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md).
```

**Step 4: Create directory structure**

```bash
mkdir -p docs/framework
mkdir -p docs/spawn-prompts
mkdir -p docs/memory/run-episodes
mkdir -p docs/targets/hooks-and-handlers/artifacts
mkdir -p docs/targets/hooks-and-handlers/results
mkdir -p docs/targets/hooks-and-handlers/spawn-prompts
mkdir -p docs/targets/lbamm-core/artifacts
mkdir -p docs/targets/lbamm-core/results
mkdir -p docs/targets/lbamm-core/spawn-prompts
mkdir -p docs/plans
mkdir -p docs/references
```

**Step 5: Verify**

```bash
ls -R docs/
```

**Step 6: Commit**

```bash
git add .gitignore CLAUDE.md docs/
git commit -m "feat: init parent framework repo with directory structure"
```

---

### Task 2: Move framework docs (non-spawn-prompts)

**Files:**
- Move: boilerplate, runbook, tool-guide, known-vuln-patterns, metrics, turn-counts, team-design, operational-checklist
- Move: memory system (all 6 files)
- Move: plans (all 11 files)
- Move: references (all 7+ files)
- Move: CODEBASE_MAP.md

**Step 1: Move framework files**

All commands from parent dir (`limit-break-amm/`):

```bash
# Framework core
cp lbamm-hooks-and-handlers/docs/artifacts/agent-boilerplate.md docs/framework/agent-boilerplate.md
cp lbamm-hooks-and-handlers/docs/execution-runbook.md docs/framework/execution-runbook.md
cp lbamm-hooks-and-handlers/docs/artifacts/tool-guide.md docs/framework/tool-guide.md
cp lbamm-hooks-and-handlers/docs/artifacts/known-vuln-patterns.md docs/framework/known-vuln-patterns.md
cp lbamm-hooks-and-handlers/docs/artifacts/metrics.json docs/framework/metrics.json
cp lbamm-hooks-and-handlers/docs/artifacts/turn-counts.md docs/framework/turn-counts.md
cp lbamm-hooks-and-handlers/docs/team-design.md docs/framework/team-design.md
cp lbamm-hooks-and-handlers/docs/operational-checklist.md docs/framework/operational-checklist.md

# Memory system
cp lbamm-hooks-and-handlers/docs/memory/digest.md docs/memory/digest.md
cp lbamm-hooks-and-handlers/docs/memory/false-positives.md docs/memory/false-positives.md
cp lbamm-hooks-and-handlers/docs/memory/confirmed-patterns.md docs/memory/confirmed-patterns.md
cp lbamm-hooks-and-handlers/docs/memory/lessons-learned.md docs/memory/lessons-learned.md
cp lbamm-hooks-and-handlers/docs/memory/run-episodes/v1-2026-02-27.md docs/memory/run-episodes/v1-2026-02-27.md
cp lbamm-hooks-and-handlers/docs/memory/run-episodes/v2-2026-03-02.md docs/memory/run-episodes/v2-2026-03-02.md

# Plans
cp lbamm-hooks-and-handlers/docs/plans/*.md docs/plans/

# References
cp -r lbamm-hooks-and-handlers/docs/references/* docs/references/

# Codebase map (will be rewritten in Task 8, but copy for now)
cp lbamm-hooks-and-handlers/docs/CODEBASE_MAP.md docs/CODEBASE_MAP.md
```

**Step 2: Verify file count**

```bash
find docs/ -name "*.md" -o -name "*.json" | wc -l
```
Expected: ~40+ files

**Step 3: Commit**

```bash
git add docs/
git commit -m "feat: migrate framework docs, memory, plans, references to parent"
```

---

### Task 3: Move target-specific artifacts for hooks-and-handlers

**Files:**
- Move: all target-specific artifacts to `docs/targets/hooks-and-handlers/`

**Step 1: Move target-specific files**

```bash
# Target-specific artifacts
cp lbamm-hooks-and-handlers/docs/artifacts/slither-findings.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/aderyn-findings.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/dead-code.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/call-graphs.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/storage-layouts.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/cross-boundary-call-graph.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/coverage-gaps.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/external-interfaces.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/access-control-matrix.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/order-lifecycle.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/token-flow.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/spec-vs-code.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/economic-model-clob.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/mev-surface.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/novel-attack-surface.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/acknowledged-findings-families.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/remediation-diff.md docs/targets/hooks-and-handlers/artifacts/
cp lbamm-hooks-and-handlers/docs/artifacts/README.md docs/targets/hooks-and-handlers/artifacts/

# Per-agent metrics
for f in lbamm-hooks-and-handlers/docs/artifacts/agent-metrics-*.md; do
  cp "$f" docs/targets/hooks-and-handlers/artifacts/
done

# Results
cp lbamm-hooks-and-handlers/docs/results/*.md docs/targets/hooks-and-handlers/results/
```

**Step 2: Verify**

```bash
ls docs/targets/hooks-and-handlers/artifacts/ | wc -l
ls docs/targets/hooks-and-handlers/results/ | wc -l
```
Expected: ~27 artifacts, 3 results

**Step 3: Commit**

```bash
git add docs/targets/
git commit -m "feat: move hooks-and-handlers target-specific artifacts and results"
```

---

### Task 4: Split spawn prompts into base + target overrides

**Files:**
- Create: `docs/spawn-prompts/{role}.md` (9 base templates — framework sections only)
- Move: current spawn prompts to `docs/targets/hooks-and-handlers/spawn-prompts/{role}.md` (full target-specific versions)

**Step 1: Copy current spawn prompts as target overrides**

These are the full, target-specific versions used for hooks-and-handlers runs:

```bash
for f in lbamm-hooks-and-handlers/docs/spawn-prompts/*.md; do
  cp "$f" docs/targets/hooks-and-handlers/spawn-prompts/
done
```

**Step 2: Create base spawn-prompt template**

Create `docs/spawn-prompts/README.md` explaining the template system:

```markdown
# Spawn Prompt Templates

Base templates define the framework sections shared across all targets.
Target-specific overrides at `docs/targets/{target}/spawn-prompts/` add:
- Domain description and owned files
- Known findings (do NOT re-report)
- Attack vectors to investigate
- Cross-boundary trace points

## How to Create Target-Specific Spawn Prompts

1. Copy the base template for the relevant role
2. Fill in the `## Your Domain` section with target-specific paths
3. Fill in `## Known Findings` from the target's prior audit
4. Fill in `## Attack Vectors` from Phase 0 artifacts
5. Save to `docs/targets/{target-name}/spawn-prompts/{role}.md`

## Roles

| Role | Description | All targets? |
|------|-------------|------|
| clob-auditor | CLOB orderbook lifecycle | Only if target has CLOB |
| hook-auditor | AMM hook enforcement | Only if target has hooks |
| permit-auditor | Permit/signature handling | Only if target has permits |
| registry-auditor | Settings/registry | Only if target has registry |
| cross-contract-tracer | Cross-boundary call chains | Yes (always) |
| economic-analyst | Economic/game-theoretic models | Yes (always) |
| fuzz-writer | Foundry fuzz + invariant tests | Yes (always) |
| poc-writer | Exploit PoC creation | Yes (always) |
| red-team-adversary | Challenge conclusions | Yes (always) |
```

**Step 3: Commit**

```bash
git add docs/spawn-prompts/ docs/targets/hooks-and-handlers/spawn-prompts/
git commit -m "feat: split spawn prompts — base templates + hooks-and-handlers overrides"
```

---

### Task 5: Fix all internal path references in framework docs

**Files:**
- Modify: all files under `docs/framework/`, `docs/spawn-prompts/`, `docs/memory/`

**Step 1: Update artifact references**

In framework docs, artifact refs change from `docs/artifacts/X` to either:
- `docs/framework/X` (for framework files like boilerplate, tool-guide)
- `docs/targets/{target}/artifacts/X` (for target-specific files)

Run these replacements in all framework files:

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm

# Framework-level artifact refs (files that moved to docs/framework/)
# In all docs under docs/framework/, docs/memory/, docs/plans/:
find docs/framework docs/memory docs/plans -name "*.md" -exec sed -i '' \
  's|docs/artifacts/agent-boilerplate\.md|docs/framework/agent-boilerplate.md|g' {} +
find docs/framework docs/memory docs/plans -name "*.md" -exec sed -i '' \
  's|docs/artifacts/tool-guide\.md|docs/framework/tool-guide.md|g' {} +
find docs/framework docs/memory docs/plans -name "*.md" -exec sed -i '' \
  's|docs/artifacts/known-vuln-patterns\.md|docs/framework/known-vuln-patterns.md|g' {} +
find docs/framework docs/memory docs/plans -name "*.md" -exec sed -i '' \
  's|docs/artifacts/metrics\.json|docs/framework/metrics.json|g' {} +
find docs/framework docs/memory docs/plans -name "*.md" -exec sed -i '' \
  's|docs/artifacts/turn-counts\.md|docs/framework/turn-counts.md|g' {} +

# Runbook / execution refs
find docs/framework docs/memory docs/plans -name "*.md" -exec sed -i '' \
  's|docs/execution-runbook\.md|docs/framework/execution-runbook.md|g' {} +
find docs/framework docs/memory docs/plans -name "*.md" -exec sed -i '' \
  's|docs/team-design\.md|docs/framework/team-design.md|g' {} +

# Spawn-prompt refs
find docs/framework docs/plans -name "*.md" -exec sed -i '' \
  's|docs/spawn-prompts/|docs/spawn-prompts/|g' {} +
# (spawn-prompts path stays the same at parent level — no change needed)

# Memory refs stay the same (docs/memory/ → docs/memory/)
# Plans refs stay the same (docs/plans/ → docs/plans/)
# References refs stay the same (docs/references/ → docs/references/)
```

**Step 2: Update target-specific artifact refs in target spawn prompts**

In `docs/targets/hooks-and-handlers/spawn-prompts/*.md`, all `docs/artifacts/X` refs become `docs/targets/hooks-and-handlers/artifacts/X`:

```bash
find docs/targets/hooks-and-handlers/spawn-prompts -name "*.md" -exec sed -i '' \
  's|docs/artifacts/|docs/targets/hooks-and-handlers/artifacts/|g' {} +
```

Also update `src/` and `test/` refs to be target-prefixed:

```bash
find docs/targets/hooks-and-handlers/spawn-prompts -name "*.md" -exec sed -i '' \
  's|`src/|`lbamm-hooks-and-handlers/src/|g' {} +
find docs/targets/hooks-and-handlers/spawn-prompts -name "*.md" -exec sed -i '' \
  's|`test/|`lbamm-hooks-and-handlers/test/|g' {} +
```

**Step 3: Update results refs**

```bash
find docs/framework docs/plans docs/memory -name "*.md" -exec sed -i '' \
  's|docs/results/|docs/targets/hooks-and-handlers/results/|g' {} +
```

**Step 4: Verify no stale `docs/artifacts/` refs remain in framework**

```bash
grep -rn "docs/artifacts/" docs/framework/ docs/memory/ docs/spawn-prompts/ docs/plans/ 2>/dev/null | grep -v "docs/targets/" | head -20
```
Expected: 0 matches (all should be either `docs/framework/` or `docs/targets/`)

Note: Some refs in `docs/plans/` are historical (describing what was done). These can keep old paths as-is since plans are historical records. Focus on fixing refs in framework/, memory/, and target spawn-prompts/.

**Step 5: Commit**

```bash
git add docs/
git commit -m "refactor: update all internal path references for parent layout"
```

---

### Task 6: Fix hardcoded absolute paths

**Files:**
- Modify: `docs/framework/agent-boilerplate.md`
- Modify: `docs/framework/tool-guide.md`
- Modify: `docs/framework/team-design.md`
- Modify: `docs/framework/execution-runbook.md`
- Modify: `docs/targets/hooks-and-handlers/spawn-prompts/fuzz-writer.md`

**Step 1: Replace project path with relative**

The old absolute path `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers` becomes `.` (parent root) or `lbamm-hooks-and-handlers/` (target-relative).

In `agent-boilerplate.md`:
- Line ~9: `**Project path**: .` (parent is now the project root)
- Symlink lines: Remove — symlinks no longer needed since repos are siblings at the same level

In `tool-guide.md`:
- Symlink section: Remove or replace with note that repos are already siblings
- Worktree section: Update to reference parent directory structure

In `execution-runbook.md`:
- Symlink lines: Remove — repos are siblings at parent level

In `team-design.md`:
- Project path references: Update to parent

**Step 2: Fix Halmos PATH references**

The `/Users/diego/.foundry/bin` and `~/.local/bin/halmos` paths are machine-specific but OK (`~` resolves correctly). These are tool installation paths, not project paths. Leave them as-is.

**Step 3: Remove symlink instructions**

Since repos are now siblings at the same level, symlinks are no longer needed. In boilerplate, tool-guide, and runbook, replace symlink blocks with:

```markdown
> **Note:** All target repos are siblings in the parent directory. No symlinks needed.
> Solidity imports resolve via `remappings.txt` in each target repo.
```

**Step 4: Verify no absolute project paths remain**

```bash
grep -rn "/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers" docs/ | grep -v "docs/plans/" | head -20
```
Expected: 0 matches outside of historical plans

**Step 5: Commit**

```bash
git add docs/
git commit -m "refactor: convert absolute paths to relative, remove symlink instructions"
```

---

### Task 7: Migrate auto-memory

**Files:**
- Create: `~/.claude/projects/-Users-diego-Dev-non-toxic-bug_bounty-limit-break-amm/memory/MEMORY.md`

**Step 1: Determine new auto-memory path**

When working from `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/`, Claude creates auto-memory at:
`/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug_bounty-limit-break-amm/memory/`

Note: The exact directory name encoding may vary (dashes vs underscores for path separators). To find the exact path, start a session from the parent and check. For now, create the expected path.

**Step 2: Copy existing auto-memory**

```bash
# Create target directory
mkdir -p "/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug_bounty-limit-break-amm/memory"

# Copy existing memory files
cp "/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug-bounty-limit-break-amm-lbamm-hooks-and-handlers/memory/MEMORY.md" \
   "/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug_bounty-limit-break-amm/memory/MEMORY.md"

cp "/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug-bounty-limit-break-amm-lbamm-hooks-and-handlers/memory/anthropic-strategy.md" \
   "/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug_bounty-limit-break-amm/memory/anthropic-strategy.md" 2>/dev/null || true
```

**Step 3: Update MEMORY.md for parent scope**

Update the copied MEMORY.md:
- Change "Project path" to parent
- Update "What's In Scope" to list all targets
- Update "Key Documents" paths to reflect new `docs/` layout
- Add migration note

Key changes to MEMORY.md:
- All `docs/artifacts/X` → `docs/framework/X` or `docs/targets/hooks-and-handlers/artifacts/X`
- All `docs/spawn-prompts/` → `docs/targets/hooks-and-handlers/spawn-prompts/` (for target-specific) or `docs/spawn-prompts/` (for base templates)
- All `docs/results/` → `docs/targets/hooks-and-handlers/results/`
- Add note: "Working directory is now `limit-break-amm/` (parent). Build tools run inside target repos."

**Step 4: Verify**

```bash
ls -la "/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug_bounty-limit-break-amm/memory/"
```

Note: The exact auto-memory directory name is determined by Claude at runtime. If the path encoding doesn't match, the memory will be created fresh on first session from parent. In that case, manually copy MEMORY.md to whatever path Claude creates.

**Step 5: No git commit** (auto-memory is outside the repo)

---

### Task 8: Create unified CODEBASE_MAP.md

**Files:**
- Rewrite: `docs/CODEBASE_MAP.md`

**Step 1: Generate new codebase map**

Use the `cartographer` skill or manually create a map covering all 3 repos:
- `lbamm-hooks-and-handlers/` — handlers + hooks (2,000+ LOC)
- `lbamm-core/` — AMM module, pool management (6,300 LOC)
- `secure-proxy/` — Proxy infrastructure

The new map should cover:
1. Parent directory structure (framework + targets)
2. Each target repo's architecture
3. Cross-repo dependencies and call chains
4. Where to find framework docs vs target-specific artifacts

**Step 2: Commit**

```bash
git add docs/CODEBASE_MAP.md
git commit -m "docs: create unified codebase map covering all repos"
```

---

### Task 9: Copy CLAUDE.md settings from hooks-and-handlers

**Files:**
- Create: `.claude/settings.local.json` at parent (if needed)

**Step 1: Check if Claude settings need copying**

```bash
cat lbamm-hooks-and-handlers/.claude/settings.local.json
```

Copy relevant tool permissions to parent `.claude/settings.local.json`. The key settings:
- Allowed tools (forge, slither, etc.)
- Permission overrides

**Step 2: Verify Forge still works from target dirs**

```bash
cd lbamm-hooks-and-handlers && forge build && cd ..
cd lbamm-core && forge build && cd ..
```

Build tools must still work inside each target repo.

**Step 3: Commit settings if created**

```bash
git add .claude/ 2>/dev/null
git commit -m "feat: copy Claude settings for parent workspace" 2>/dev/null || true
```

---

### Task 10: Final verification and cleanup

**Step 1: Verify framework doc completeness**

```bash
# All framework files exist at parent
test -f docs/framework/agent-boilerplate.md && echo "OK" || echo "MISSING: boilerplate"
test -f docs/framework/execution-runbook.md && echo "OK" || echo "MISSING: runbook"
test -f docs/framework/tool-guide.md && echo "OK" || echo "MISSING: tool-guide"
test -f docs/framework/known-vuln-patterns.md && echo "OK" || echo "MISSING: patterns"
test -f docs/framework/metrics.json && echo "OK" || echo "MISSING: metrics"
test -f docs/framework/turn-counts.md && echo "OK" || echo "MISSING: turn-counts"
test -f docs/memory/digest.md && echo "OK" || echo "MISSING: digest"
test -f docs/memory/false-positives.md && echo "OK" || echo "MISSING: fps"
test -f docs/memory/confirmed-patterns.md && echo "OK" || echo "MISSING: patterns"
test -f docs/memory/lessons-learned.md && echo "OK" || echo "MISSING: lessons"
```

**Step 2: Verify target artifacts exist**

```bash
ls docs/targets/hooks-and-handlers/artifacts/ | wc -l
ls docs/targets/hooks-and-handlers/results/ | wc -l
ls docs/targets/hooks-and-handlers/spawn-prompts/ | wc -l
```
Expected: ~27 artifacts, 3 results, 9 spawn prompts

**Step 3: Verify no broken cross-references in key files**

```bash
# Framework files should NOT reference docs/artifacts/ (old path)
grep -rn "docs/artifacts/" docs/framework/ docs/memory/ | grep -v "docs/targets/" | wc -l
```
Expected: 0

**Step 4: Verify CLAUDE.md exists and is correct**

```bash
head -20 CLAUDE.md
```

**Step 5: Tag and commit**

```bash
git tag parent-migration-2026-03-09
```

**Step 6: Do NOT delete files from hooks-and-handlers yet**

The original files in `lbamm-hooks-and-handlers/docs/` should be kept until we verify the parent layout works for at least one full session. They can be cleaned up later.

---

### Task 11: Update remote tracking

**Step 1: Add audit remote to parent repo**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm
# Create the remote repo first (or use existing)
git remote add audit git@github.com:0xquinto/lbamm-audit-framework.git
```

Note: The user may want to use a different remote name/URL. Confirm before pushing.

**Step 2: Push**

```bash
git push -u audit main
```
