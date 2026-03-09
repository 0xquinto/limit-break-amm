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
