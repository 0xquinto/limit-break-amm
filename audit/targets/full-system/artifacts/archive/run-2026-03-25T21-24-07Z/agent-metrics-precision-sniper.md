# Agent Metrics: precision-sniper (Wave 1)

## Session Info
- Agent: precision-sniper
- Model: claude-opus-4-6
- Wave: 1
- Checklist: C-MATH (29 items)
- Hypotheses: 10 (H-R4-CP-01 through H-R4-CP-10)

## Phase Completion

### Phase A: Static Analysis (4/4)
- A1: Slither detectors — ran on 5 repos. 144+ H/M findings. No novel exploitable issues.
- A2: Slither function list — analyzed target contracts
- A3: Aderyn — ran on lbamm-core (88 detectors). Fixed/Dynamic repos crashed (known cross-repo bug v0.6.8)
- A4: Custom Slither detectors — attempted via MCP

### Phase B: Architectural Analysis (3/5)
- B1: audit-context-building — analyzed FixedHelper, DynamicHelper, SingleProviderHelper math functions
- B2: entry-point-analyzer — mapped state-changing entry points
- B3: call graph export — FixedHelper via MCP (0 nodes for library)
- B4: property-based-testing — guidance applied to C23-C25 invariant tests
- B5: variant-analysis — not applicable (no confirmed findings)

### Phase C: C-MATH Checklist (27/29)
- C1-C2: FullMath.mulDiv/mulDivRoundingUp — DONE
- C3-C6: FixedHelper swap/liquidity math — DONE
- C7-C10: DynamicHelper computeSwap/crossTick/updatePosition — DONE
- C11-C16: SqrtPriceMath/TickMath/BitMath/LiquidityMath — DONE
- C17: FeeHelper calculateInputFee/calculateOutputFee — DONE
- C18: CLOBHelper.calculateFixedInput — DONE
- C19: SqrtPriceCalculator.computeRatioX96 — DONE
- C20: SingleProviderHelper round-trip — DONE
- C21: Medusa on FixedPoolType — ERROR (constructor args needed)
- C22: Medusa on DynamicPoolType — ERROR (no zero-arg properties)
- C23: INV-SW02 No Profitable Round-Trip — DONE
- C24: INV-SW03 Rounding Favors Protocol — DONE
- C25: INV-E01 Fee Monotonicity — DONE
- C26-C29: Exploit-grounded probes (Cetus, Balancer, ERC-4626, Hook) — DONE

### Phase D: Hypothesis Testing (10/10)
All 10 hypotheses tested. 0 confirmed, 10 dismissed (all strategic failures — guards exist, paths blocked).

## Test Files
1. `amm-pool-type-dynamic/test/AuditPrecisionSniperW1V4.t.sol` — 24 tests
2. `amm-pool-type-dynamic/test/AuditPrecisionSniper.t.sol` — 46 tests
3. `lbamm-pool-type-fixed/test/audit/PrecisionSniperFixed.t.sol` — 14 tests
4. `lbamm-pool-type-fixed/test/audit/AuditPrecisionSniperCMath.t.sol` — 18 tests
5. `lbamm-pool-type-fixed/test/audit/PrecisionSniperHypotheses.t.sol` — ~20 integration tests
6. `lbamm-pool-type-single-provider/test/audit/AuditPrecisionSniperSP.t.sol` — 6 tests
7. `lbamm-hooks-and-handlers/test/audit/AuditPrecisionSniperCLOB.t.sol` — 4 tests

## Tools Run
| Tool | Status | Notes |
|------|--------|-------|
| Slither MCP | ran | 5 repos, 144+ H/M findings |
| Aderyn | ran | lbamm-core only (cross-repo bug) |
| Forge | ran | 116 tests, 7 files, 5 repos |
| Halmos | ran | 5 check_ functions, all TIMEOUT (no counterexample) |
| Medusa | ran (errors) | Constructor args / no property tests |
| Call graph | ran | FixedHelper via MCP |

## Findings
- 0 confirmed findings
- 8 ruled-out vectors with Forge test evidence
- 10 dismissed hypotheses (all strategic)
- 5 theft theses (all ruled out)

## Key Observations
1. Math libraries are well-hardened. FullMath.mulDiv/mulDivRoundingUp handle phantom overflow correctly.
2. Rounding is consistently protocol-favorable: mulDiv for outputs, mulDivRoundingUp for inputs.
3. CLOBHelper uses mulDivRoundingUp for output (favors taker over maker) — documented, not exploitable.
4. Fixed pool height precision truncation is safe: redeposited amounts always <= original values.
5. Fee growth Q128 is monotonically non-decreasing; truncation losses permanently stranded.
6. All invariants hold: INV-SW02, INV-SW03, INV-E01.
