# Lessons Learned (Procedural Memory)

> Compressed beliefs extracted from run outcomes. Each has a confidence score.
> **Lifecycle**: ADD after each run. UPDATE confidence when re-observed. DELETE if disproven.
> **Format**: Reflexion-style — outcome → belief → action rule.
> **Note**: Infrastructure/wiring lessons are in MEMORY.md. This file is for audit methodology lessons only.

---

## Contest Submission

### L-009: Only submit Medium+ with demonstrable economic impact
- **Observed**: Guardian Defender contest — 8 submissions, 0 accepted
- **Confidence**: 99
- **Belief**: Judges reject findings without attacker profit or material user loss. Below threshold: dust-level precision, code quality, gas waste, known design properties, intentional decisions, "misconfigured integrator" victims.
- **Action**: Apply Submission Threshold Test before ANY submission:
  1. Can attacker **profit**? (steal funds, extract value, MEV)
  2. Can attacker **cause material loss** to innocent victim?
  3. Can attacker **brick or DoS** the protocol?
  4. Is this **novel**, not a known design property?
  If ALL answers are NO, do NOT submit.

### L-010: Quality over quantity
- **Observed**: Guardian Defender — Low/Info submitted as standalone reports
- **Confidence**: 95
- **Belief**: Many low-quality submissions damage credibility. 1 valid Medium > 8 invalid Lows.
- **Action**: Only submit Medium+ that passes L-009 threshold test.

## Codebase Properties

### L-011: Well-hardened — exploit composition, not individual functions
- **Observed**: 10+ experiment runs, 9 agents, 0 confirmed findings
- **Confidence**: 90
- **Belief**: Individual functions are correct. All 20 invariants hold. Single-function bugs unlikely. Exploitable issues require cross-module composition, multi-tx sequences, or assumption mismatches between repos.
- **Action**: Focus on cross-boundary flows (core↔pool type↔handler↔hook), multi-step attack sequences, flash loan amplification.

### L-012: Rounding consistently favors protocol
- **Observed**: precision-sniper across 10 runs, all pool types
- **Confidence**: 95
- **Belief**: All math uses FullMath.mulDiv/mulDivRoundingUp with correct rounding direction. amountIn rounds UP, amountOut rounds DOWN, fees round UP. Standard Uniswap V3 convention. Dust-loop extraction is not profitable.
- **Action**: Don't spend turns on single-swap rounding exploits. Focus on multi-step accumulation or cross-pool composition instead.

## Agent Behavior

### L-013: Agents quit early without enforcement
- **Observed**: compliance scoring runs — state-desync (15-20 turns), composability-exploiter (15 turns), price-distorter (20 turns) out of 200 budget
- **Confidence**: 90
- **Belief**: Agents declare "well-hardened" and stop after superficial review unless the prompt has concrete completion criteria tied to consequences.
- **Action**: Mandatory completion checklist with item counts. Depth floor with discard threat. Structured metadata template agents must fill in.

### L-014: Agent self-reported metrics are the only reliable source
- **Observed**: all runs — platform token/turn counts unreliable, SDK metrics show 0
- **Confidence**: 90
- **Belief**: Agent sidecar `metadata` (num_turns, files_read, tools_run) is the source of truth. Platform-level metrics are often 0 or missing.
- **Action**: Require structured metadata in sidecar. Compliance scoring reads from sidecar, not platform metrics.

### L-015: Schema strictness causes silent data loss
- **Observed**: price-distorter wrote confidence='85', entire sidecar rejected
- **Confidence**: 85
- **Belief**: Agents deviate from enum values (numeric confidence, wrong case severity). Strict validation discards the entire sidecar, losing all findings and ruled-out vectors.
- **Action**: Coerce where possible (numeric→enum, case normalization). Only reject truly unparseable data.

## Tool Usage

### L-016: Halmos/Medusa consistently deprioritized
- **Observed**: 6-7 of 9 agents skip halmos/medusa across runs despite prompt instructions
- **Confidence**: 85
- **Belief**: Agents treat these as optional because they're expensive (slow, complex setup). Prompt says "run them" but agents self-rationalize skipping.
- **Action**: Tool gate per checklist item — "Halmos:" in an item means you MUST invoke halmos. Skipping = item not completed.

### L-008: Cross-repo patterns are usually by-design but still worth testing
- **Observed**: v1+v2 (transient storage), black-hat runs (diamond proxy)
- **Confidence**: 80
- **Belief**: Patterns crossing into lbamm-core/secure-proxy are usually architectural decisions. But cross-boundary agents should still write Forge tests to confirm — "by-design" is not "proven safe."
- **Action**: Test cross-repo patterns with Forge. Log as ruled-out with evidence if by-design. Don't skip investigation.
