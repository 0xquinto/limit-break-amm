# Pashov Skills — Reference Material

Source: https://github.com/pashov/skills (MIT License)
Downloaded: 2026-03-09

## What This Is

Pashov Audit Group's Claude Code skill for parallelized Solidity security scanning.
We imported it as reference material for our 9-agent audit system.

## What We Use From Here

### 1. Attack Vectors (170 total across 4 files)
- `attack-vectors/attack-vectors-{1,2,3,4}.md`
- Categories: signatures, tokens, proxies, cross-chain, access control, arithmetic, assembly, oracles, governance, ERC standards, bridges, AA/ERC-4337
- Use as baseline vector corpus for our scanning agents

### 2. FP Gate + Confidence Scoring (`judging.md`)
- 3-check false-positive filter: attack path traceable? entry point reachable? no existing guard?
- Confidence scoring: 100 base, deductions for admin-only (-25), partial path (-20), self-harm (-15)
- Threshold at 75 — findings below still reported but without fix sections
- **Adopt for our Guardian agent's judging criteria**

### 3. Report Formatting (`report-formatting.md`)
- Structured markdown with confidence scores, diffs, threshold separator
- Reference for our report generation

### 4. Agent Prompts (`agents/`)
- `vector-scan-agent.md` — 4-step workflow: read → triage → deep analysis → compose
- `adversarial-reasoning-agent.md` — Opus-based deeper reasoning (their "DEEP" mode)
- `SKILL.md` — 4-turn orchestrator: Discover → Prepare → Spawn → Report

## Key Limitations (why our system goes further)
- ~2,500 LOC ceiling (drops accuracy past 5K)
- Homogeneous agents (same prompt, different file chunks)
- No memory/learning across runs
- No cross-contract relational reasoning
- No static analysis (Slither/Semgrep) integration
- No spec/whitepaper compliance checking
