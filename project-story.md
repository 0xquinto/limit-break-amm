---
name: "Limit Break AMM Security Audit Framework"
oneLiner: "AI-powered multi-agent security audit orchestrator built to crack the Guardian Defender contest (Feb–Apr 2026)"
domain: "Smart contract security / DeFi / AI agent orchestration"
---

## Timespan
- **First commit:** 2026-03-09
- **Last commit:** 2026-04-06
- **Total commits:** 369
- **Active days:** 25

## Arc

### Beginning
The project started on March 9, 2026 as a clean-room scaffold: a parent directory to orchestrate Claude agent spawns across six Limit Break AMM target repos (lbamm-core, dynamic/fixed/single-provider pool types, hooks-and-handlers, secure-proxy). Within a single day the entire skeleton — orchestrator entry point, wave runner, synthesizer, prompt renderer, memory lifecycle, and NOOP FP pre-filter — was committed. The early "defensive" model used generic recon-style agent archetypes that produced zero findings and scored badly on compliance.

### Middle
The pivot to a "black hat model" on March 13 was the defining inflection point. Six Opus archetype templates (offense-first, exploit-grounded attack probes, 128K thinking budget) replaced the defensive templates. The following two weeks were an intense feedback loop: running compliance waves, scoring agent thoroughness across six dimensions, hitting Grade F, debugging the gap between what agents claimed to do and what they actually did (schema coercions, checklist counting, evidence gates, continuation passes). The knowledge-loop architecture (Pass 1 boundary agents → hypothesis injection → Wave 1 investigation → kill gate → FP pre-filter → compliance scoring) crystallized through ~14 experiment runs between March 14–25, climbing from a compliance score of 39.8 (F) to a peak of 112.5 (A). The evidence-gated enforcement system — blocking coverage thresholds, artifact-existence verification, a 6th compliance dimension — was the mechanism that broke through the plateau.

### End
March 30 marked the handoff from compliance to exploit mode: a separate 3-agent pipeline that consumed the knowledge base, ran 50–500 turns of attack-focused investigation, and applied four verification gates (Forge test verification → FP dedup → net-value check → config protection). The first novel finding — CP-006 CLOBHelper double-rounding (Medium) — was discovered in a $29 exploit mode run. The final weeks (April 1–6) added infrastructure maturity: trace analyzer (16-dimension intelligence extraction), file inventory + coverage sweep (gap detection for uncovered files), predictive hypothesis ranking from 375 historical decisions, automated learning extraction, sidecar recovery from truncated agent traces, and a framework generalization pass (docs/ → audit/ migration, target.json requirement, Obsidian KB vault). The project ended with 60 false positives catalogued, 283 pytest tests, and a reusable multi-target audit framework.

## Key Milestones
| Date | Commit | Description |
|------|--------|-------------|
| 2026-03-09 | 3adb250 | Init parent framework repo — scaffold, wave runner, synthesizer, memory lifecycle all in one day |
| 2026-03-13 | 0271863 | Black hat model redesign plan — pivot from defensive to offense-first with 6 Opus archetypes |
| 2026-03-14 | c9839a8 | First compliance-scored run — 39.8/100 (F), establishes the 82-item exhaustive checklist baseline |
| 2026-03-16 | 63ad8c3 | Sidecar gate + continuation pass — score jumps to 72.7 (C), first passing grade |
| 2026-03-18 | c6f6aad | Phase 1 foundation — template restructure and gotchas push score to 91.9 (A) |
| 2026-03-25 | e7742a7 | Evidence-gated enforcement — blocking gates + 6th compliance dimension achieve peak score 112.5 (A) |
| 2026-03-30 | 3f0f10a | Exploit mode launch — 3 Sonnet agents, attack-focused pipeline, ~$30/run |
| 2026-03-30 | 6aa9354 | First novel finding — CP-006 CLOBHelper double-rounding (Medium) discovered for $29 |
| 2026-04-01 | cfae49e | Trace analyzer — 16-dimension agent intelligence extraction from JSONL traces |
| 2026-04-03 | d808b1d | Framework generalization — kill Quimera dependency, config-driven repos, any target via target.json |

## Tech Stack
- Python 3.11+ (orchestrator, 34 modules, 283 pytest tests)
- Claude Agent SDK (Opus 4.6 + Sonnet 4.6, adaptive thinking up to 128K budget)
- Solidity 0.8.24 / Foundry / Cancun EVM
- Slither (MCP server + custom detectors)
- Aderyn
- Halmos (symbolic execution)
- Medusa (parallel corpus-guided fuzzer)
- PermitC / EIP-712 / Creator Token Standards
- Obsidian (knowledge base vault + KB search CLI)

## Metrics
| Metric | Value |
|--------|-------|
| Compliance score improvement | 39.8 (F) → 112.5 (A) over 17 experiment runs |
| Total experiment runs tracked | 24 runs in experiments.tsv |
| Novel findings submitted | 1 confirmed (CP-006 Medium, $29 run cost) |
| False positives catalogued | 60 (with contract-scoped injection) |
| Agent archetypes | 9 compliance + 3 exploit + 6 Pass 1 boundary = 18 total |
| Test coverage | 283 pytest tests across 34 orchestrator modules |
| Hypotheses tracked | 375 historical decisions used for predictive ranking |
| Commits in 28-day window | 369 commits across 25 active days |

## Lessons Learned
- Offense-first agent framing (black hat model) dramatically outperforms defensive/recon framing for vulnerability discovery — the pivot on day 4 was the most impactful single change.
- Agent compliance theater is a real problem: without structured evidence gates, agents self-report thoroughness without doing the work; blocking thresholds tied to artifact existence are the only reliable enforcement mechanism.
- Exploit mode and compliance mode serve fundamentally different purposes and need separate agent rosters, system prompts, scoring functions, and verification gates — conflating them dilutes both.
