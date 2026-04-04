# Operational Checklist (Post-Execution Verification)

> Use this checklist after execution to verify all mistake-prevention measures were followed.
> Each item references where the prevention is built into the design doc.

| # | Mistake | Prevention | Where in Design |
|---|---------|-----------|-----------------|
| 1 | Spawning without file ownership | Every spawn prompt has "Owned files" AND "Do NOT modify" | Spawn prompts, Architecture |
| 2 | Broadcasting routine messages | Default to `message`; `broadcast` only for cross-module critical findings | Communication Protocol |
| 3 | Panicking when teammate goes idle | Idle is normal. Send a message to wake them. | Communication Protocol |
| 4 | Omitting `summary` on SendMessage | Template requires it. Lead enforces 5-10 word summaries. | Communication Protocol |
| 5 | Setting deps at TaskCreate time | Use TaskUpdate with `addBlockedBy`/`addBlocks` AFTER creation | Task Management |
| 6 | Lead implementing tasks itself | Delegate mode (Shift+Tab) enforced from Phase 1 Step 6 | Phase 1 |
| 7 | Skipping TaskGet before starting work | Spawn prompt tells agents: "Call TaskGet to read full task details before starting" | Task Management |
| 8 | Two teammates editing same file | Worktree isolation on every agent. No shared files. | Architecture ("Why worktrees") |
| 9 | Using Explore agent for implementation | All agents are `general-purpose` (can read AND write) | Agent Spawn Details |
| 10 | Forgetting ToolSearch before slither/exa | Spawn prompt explicitly says "Use ToolSearch with +slither to load tools" | Slither MCP Usage |
| 11 | Agents re-reporting known findings | Anti-patterns section lists all Guardian finding IDs to skip | Spawn prompts ("Known Findings") |
| 12 | Not reading config.json for member names | Phase 1 Step 5 explicitly reads config to get names | Team Setup |
| 13 | TeamDelete with active members | Teardown sends shutdown_request first, waits for all responses | Teardown Protocol |
| 14 | Forge fails in worktree (path resolution) | Mandatory Worktree Setup section with absolute symlinks + sed fixes | agent-boilerplate.md (Phase 0) |
| 15 | Slither returns sibling repo contracts | Always use `exclude_paths: ["lib/", "test/", "../"]` | Slither MCP Usage |
| 16 | Slither function signature mismatch | Always `search_functions` first, then `get_function_callers`/`get_function_callees` | Slither MCP Usage |
| 17 | Chisel fails with echo pipe syntax | Use `printf '...\n'` not `echo '...'` | Chisel Usage |
| 18 | Medusa not finding `medusa.json` | Run `medusa init` in project root first. Ensure config points at correct test contract paths. | Medusa Usage |
| 19 | Python import fails (matplotlib/pandas) | Must `source .venv/bin/activate` first — packages are in the project venv, not system Python | Python/Jupyter Usage |
| 20 | Medusa hangs on large contracts | Set `testLimit` and `timeout` in `medusa.json`. Start with `testLimit: 10000` and increase. | Medusa Usage |
| 21 | Reading remediation-diff.md overflows context | Use `git diff 0483a11 0199bdf -- src/<module>/` per-module instead | Phase 0 |
| 22 | Forgetting to log agent metrics on completion | Log tokens/duration to turn-counts.md BEFORE reading findings. Teardown gate blocks until file is complete. | Metric Collection Protocol |
| 23 | Agent findings lost to context compaction | Agents write findings to disk incrementally (`agent-metrics-{name}.md`). | Spawn prompts + Cache-aware principles |
| 24 | Editing CLAUDE.md while lead session is active | CLAUDE.md is in the cached prefix. Editing mid-session breaks the lead's cache. Edit between sessions only. | Cache-aware design principles |
| 25 | MCP server crash/restart mid-session | If slither-mcp or exa restarts, deferred tool stubs may change, breaking prefix cache. Verify MCP stability before spawning. | Cache-aware design principles |
| 26 | Unexpected token usage spike on an agent | Compare tokens across similar agents in turn-counts.md. A spike may indicate cache misses. Investigate before spawning more. | Cache-aware design principles |
| 27 | Submitting a finding that overlaps acknowledged family | Lead runs dedup check against `acknowledged-findings-families.md` before forwarding to poc-writer. | Phase 3 |
| 28 | Severity overestimation | Lead classifies every finding into exploitability tier A/B/C. Tier B capped at Medium, Tier C at Low/Info. | Phase 3, Spawn prompts |
| 29 | One-line "ruled out" justifications | Agents must write proof sketches with premises, code evidence, assumptions, confidence, and weaknesses. | Spawn prompts ("Ruling Out Vectors") |
| 30 | Switching models when resuming an agent | NEVER resume with a different model — rebuilds entire cache. Spawn NEW agent with handoff summary. | Model assignment rules |
| 31 | Same model for second pass | Second-pass uses diverse models (2 sonnet + 1 opus + 1 haiku). All must be fresh spawns, not resumed. | Phase 4 |
| 32 | Red-team agrees with audit team | Red-team prompt enforces skepticism as default stance. Do NOT agree — challenge every conclusion. | red-team-adversary spec |
| 33 | Auditors spending >2 turns on standard vuln classes | Anti-pattern in all auditor prompts: standard reentrancy/overflow/access-control covered by Slither. | Spawn prompts ("Investigation priority") |
| 34 | Subagent in worktree can't use Bash | Platform limitation: worktree isolation blocks Bash for background subagents. Use team agents for Bash/forge. | Architecture ("Why all team agents") |
| 35 | Halmos unused despite being in plan | Only include when specific ALL-input proofs are needed. Marked optional in fuzz-writer spec. | fuzz-writer spec |
| 36 | Aderyn output overwrites `report.md` | Use `--output aderyn-report.md` or rename before running alongside other tools | tool-guide.md (Aderyn Gotchas) |
| 37 | Quimera needs LLM API or manual mode | Verify model availability before spawning poc-writer, or use manual mode (no API key needed) | tool-guide.md (Quimera Gotchas) |
| 38 | Skills invoked as CLI instead of Skill() | Skills are conversation-internal AI tools. Invoke via `Skill("name:name")`, not bash. Agents discover via boilerplate. | agent-boilerplate.md (Skills table) |
