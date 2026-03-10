"""Detect external calls in hook callbacks that could re-enter the AMM.

Specific to the three-tier hook system: Token -> Pool -> Liquidity hooks.
Flags external calls in beforeSwap/afterSwap/beforeLiquidity/afterLiquidity
that could re-enter the AMM.
"""

from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification
from slither.slithir.operations import HighLevelCall, LowLevelCall


HOOK_FUNCTIONS = {
    "beforeSwap", "afterSwap",
    "beforeLiquidity", "afterLiquidity",
    "beforeAddLiquidity", "afterAddLiquidity",
    "beforeRemoveLiquidity", "afterRemoveLiquidity",
    "_beforeSwap", "_afterSwap",
}


class HookReentrancy(AbstractDetector):
    ARGUMENT = "hook-reentrancy"
    HELP = "External calls in hook callbacks that could re-enter the AMM"
    IMPACT = DetectorClassification.HIGH
    CONFIDENCE = DetectorClassification.MEDIUM

    WIKI = "https://github.com/limitbreakinc/lbamm"
    WIKI_TITLE = "Hook Reentrancy"
    WIKI_DESCRIPTION = (
        "Detects external calls (high-level or low-level) within hook callback "
        "functions that could potentially re-enter the AMM core."
    )
    WIKI_RECOMMENDATION = (
        "Ensure hook callbacks cannot re-enter the AMM. Use reentrancy guards "
        "or verify that external calls target trusted, non-reentrant contracts."
    )
    WIKI_EXPLOIT_SCENARIO = (
        "A beforeSwap hook makes an external call to a malicious contract that "
        "calls back into the AMM, bypassing swap invariants."
    )

    def _detect(self):
        results = []
        for contract in self.compilation_unit.contracts_derived:
            for function in contract.functions:
                if function.name not in HOOK_FUNCTIONS:
                    continue
                external_calls = []
                for node in function.nodes:
                    for ir in node.irs:
                        if isinstance(ir, (HighLevelCall, LowLevelCall)):
                            external_calls.append((node, ir))

                if external_calls:
                    for node, ir in external_calls:
                        info = [
                            f"Hook reentrancy risk in ",
                            function,
                            f": external call at ",
                            node,
                            f"\n",
                        ]
                        res = self.generate_result(info)
                        results.append(res)

        return results
