# Framework Generalization

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract the audit framework into reusable templates for future targets.

**Architecture:** Doc refactoring — extracting target-specific content from current docs into `{{PLACEHOLDER}}` templates, creating a "new target" onboarding flow, and validating templates can reproduce the current setup.

**Tech Stack:** Markdown templates

**Prerequisites:** Part A (full v2 validation run) completed. N=2 validation run on lbamm-core completed. Infrastructure validation table filled in. Any doc fixes from Part A already committed. Calibrated max_turns available from turn-counts.md.

---

### Task 1: Create target-agnostic spawn prompt templates

**Files:**
- Create: `docs/templates/spawn-prompts/auditor-template.md`
- Create: `docs/templates/spawn-prompts/fuzz-writer-template.md`
- Create: `docs/templates/spawn-prompts/economic-analyst-template.md`
- Create: `docs/templates/spawn-prompts/poc-writer-template.md`
- Create: `docs/templates/spawn-prompts/red-team-adversary-template.md`

**Step 1: Extract target-specific content from current spawn prompts**

For each of the 8 spawn prompts, identify and replace with `{{PLACEHOLDER}}`:

| Current hardcoded content | Placeholder |
|---------------------------|-------------|
| `src/handlers/clob/`, `src/hooks/` etc. | `{{MODULE_PATHS}}` |
| `CLOBTransferHandler.sol`, `AMMStandardHook.sol` etc. | `{{PRIMARY_FILES}}` |
| H-01, M-04, M-05 etc. finding IDs | `{{KNOWN_FINDINGS}}` |
| "CLOB linked-list FIFO under concurrent fills" etc. | `{{ATTACK_VECTORS}}` |
| Module-specific anti-patterns | `{{MODULE_ANTI_PATTERNS}}` |
| `docs/artifacts/order-lifecycle.md` etc. | `{{PHASE0_ARTIFACTS}}` |
| `test/audit/fuzz/MathFuzzTest.t.sol` etc. | `{{EXISTING_TESTS}}` |
| `/Users/diego/Dev/non-toxic/...` | `{{PROJECT_ROOT}}` |

**Step 2: Collapse 4 auditor prompts into 1 parameterized template**

The 4 auditor prompts (clob, permit, hook, registry) share 80% structure. Create one `auditor-template.md` with:
- `{{MODULE_NAME}}` — e.g., "CLOB handler"
- `{{OWNED_FILES}}` — files the auditor writes to
- `{{READ_FILES}}` — files to read (including module-specific artifacts)
- `{{KNOWN_FINDINGS}}` — findings to skip
- `{{ATTACK_VECTORS}}` — ordered hunt list
- `{{INVESTIGATION_PRIORITY}}` — tier 1/2/3 allocation

**Step 3: Keep support agents as separate templates**

fuzz-writer, economic-analyst, poc-writer, red-team-adversary each get their own template (they're structurally different from auditors).

### Task 2: Create target-agnostic execution runbook template

**Files:**
- Create: `docs/templates/execution-runbook-template.md`

**Step 1: Extract target-specific content from current runbook**

Replace with placeholders:

| Current | Placeholder |
|---------|-------------|
| `team_name: "bug-bounty-hooks-handlers"` | `{{TEAM_NAME}}` |
| 4 auditor tasks + 2 support + 2 deferred | `{{TASK_TABLE}}` |
| Cross-module routing table (11 rows) | `{{ROUTING_TABLE}}` |
| Phase 4 gap areas | `{{GAP_AREAS}}` (filled at runtime) |

**Step 2: Keep phase structure and gates unchanged**

Phases 0-5, gates, decision trees, and metric protocol are target-agnostic. Keep them verbatim.

### Task 3: Create target-agnostic agent-boilerplate template

**Files:**
- Create: `docs/templates/agent-boilerplate-template.md`

**Step 1: Replace target-specific content**

| Current | Placeholder |
|---------|-------------|
| `Solidity 0.8.24, Foundry, cancun EVM...` | `{{TECH_STACK}}` |
| `/Users/diego/Dev/non-toxic/...` | `{{PROJECT_ROOT}}` |
| `../lbamm-core/`, `../secure-proxy/` | `{{SIBLING_REPOS}}` (optional) |
| Worktree symlink commands | `{{WORKTREE_SETUP_COMMANDS}}` |
| `forge build --skip test script` | `{{BUILD_VERIFY_COMMAND}}` |

**Step 2: Keep universal content verbatim**

Anti-patterns, deliverable format, severity rubric, exploitability tiers, proof sketch format — all target-agnostic. Keep as-is.

### Task 4: Create "new target" onboarding guide

**Files:**
- Create: `docs/templates/new-target-setup.md`

**Step 1: Write the onboarding checklist**

```markdown
# New Target Setup

## Prerequisites
- [ ] Target repo cloned
- [ ] Build system works (forge/hardhat/etc.)
- [ ] Audit report PDF available (if contest)
- [ ] Sibling repos identified (if any)

## Step 1: Configure target (fill `target-config.md`)
- Project name, path, tech stack
- Module inventory (name → files → LOC)
- Known findings to skip
- Sibling repos and their paths

## Step 2: Generate Phase 0 artifacts
Refer to `phase0-checklist.md` for generation method per artifact:
- [ ] Access control matrix
- [ ] Token/value flow
- [ ] Slither findings + dead code + storage layouts + call graphs
- [ ] Coverage gaps
- [ ] Known vuln patterns (Exa research)
- [ ] Remediation diff (if audit contest)
- [ ] Novel attack surface catalog
- [ ] Economic model (if DeFi)
- [ ] MEV surface (if DeFi)
- [ ] Cross-boundary call graph (if sibling repos)
- [ ] Acknowledged findings families (if contest)
- [ ] Spec vs code checklist

## Step 3: Fill spawn prompt templates
Copy `docs/templates/spawn-prompts/` to `docs/spawn-prompts/`
Fill all {{PLACEHOLDER}} values from target-config.md

## Step 4: Fill runbook template
Copy `docs/templates/execution-runbook-template.md` to `docs/execution-runbook.md`
Fill {{TEAM_NAME}}, {{TASK_TABLE}}, {{ROUTING_TABLE}}

## Step 5: Determine agent count and model allocation
- 1 auditor per module (opus for complex, sonnet for bounded)
- fuzz-writer if Foundry project
- economic-analyst if DeFi (fees, MEV, incentives)
- poc-writer always
- red-team always

## Step 6: Run Phase 0 verification
All artifacts present → proceed to Phase 1
```

**Step 2: Write Phase 0 generation helper**

Create `docs/templates/phase0-checklist.md` listing which artifacts need Slither, Exa, forge, or manual creation — so the lead knows the generation method for each.

### Task 5: Create target-config specification

**Files:**
- Create: `docs/templates/target-config-template.md`

**Step 1: Define the config format**

```markdown
# Target Configuration

## Identity
- **Project**: {{PROJECT_NAME}}
- **Contest**: {{CONTEST_NAME}} (or "independent audit")
- **Deadline**: {{DEADLINE}}
- **Repo**: {{REPO_URL}}
- **Path**: {{PROJECT_ROOT}}

## Tech Stack
- **Language**: {{LANGUAGE}} (e.g., Solidity 0.8.24)
- **Framework**: {{FRAMEWORK}} (e.g., Foundry)
- **EVM target**: {{EVM_TARGET}} (e.g., cancun)
- **Key dependencies**: {{DEPENDENCIES}}

## Modules
| Module | Path | LOC | Complexity | Recommended Model |
|--------|------|-----|------------|-------------------|
| {{MODULE_1}} | {{PATH_1}} | {{LOC_1}} | High/Med/Low | opus/sonnet |

## Sibling Repos (optional)
| Repo | Local Path | Purpose |
|------|-----------|---------|
| {{SIBLING_1}} | {{SIBLING_PATH_1}} | {{PURPOSE_1}} |

## Known Findings to Skip
| ID | Title | Family |
|----|-------|--------|
| {{FINDING_1}} | {{TITLE_1}} | {{FAMILY_1}} |

## Remappings / Build Quirks
{{BUILD_NOTES}}
```

### Task 6: Validate templates against current target

**Step 1: Dry-run template fill**

Take `target-config-template.md`, fill it for lbamm-hooks-and-handlers. Verify the filled config + templates could reproduce the current `docs/spawn-prompts/` and `docs/execution-runbook.md`.

**Step 2: Identify any gaps**

If the templates can't express something from the current setup, add the missing placeholder.

**Step 3: Apply fixes from Part A run**

Incorporate anything that broke or needed adjustment during the full validation run — worktree setup changes, prompt wording fixes, phase gate adjustments, etc.

### Task 7: Document and ship

**Step 1: Create templates README**

Create `docs/templates/README.md` explaining:
- Template system overview
- Fill workflow (target-config → templates → Phase 0 → run)
- What's reusable vs. what must be recreated per-target
- Calibrated max_turns from Part A (reference turn-counts.md)

**Step 2: Commit templates**

```bash
git add docs/templates/
git commit -m "feat: extract reusable audit framework templates from v2 run"
```

**Step 3: Update MEMORY.md**

Add entry documenting:
- Template location (`docs/templates/`)
- Which parts are reusable vs. target-specific
- Link to this plan

**Step 4: Push and tag**

```bash
git push audit main
git tag v3-framework-2026-02-28
git push audit v3-framework-2026-02-28
```

---

## Success Criteria

- [ ] 5 template files in `docs/templates/spawn-prompts/`
- [ ] 1 runbook template
- [ ] 1 boilerplate template
- [ ] 1 target-config template
- [ ] 1 new-target-setup guide
- [ ] 1 phase0-checklist
- [ ] 1 templates README
- [ ] Dry-run validation passes (templates reproduce current setup)
- [ ] Part A fixes incorporated
- [ ] Tagged and pushed to audit remote
