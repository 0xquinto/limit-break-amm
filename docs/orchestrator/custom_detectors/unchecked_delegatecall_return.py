"""Detect delegatecall where the return value is not checked.

The pool type interface uses delegatecall extensively. Flags any delegatecall
where the success boolean is not checked.
"""

import re
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification
from slither.core.cfg.node import NodeType


class UncheckedDelegatecallReturn(AbstractDetector):
    ARGUMENT = "unchecked-delegatecall-return"
    HELP = "Delegatecall return value not checked"
    IMPACT = DetectorClassification.HIGH
    CONFIDENCE = DetectorClassification.HIGH

    WIKI = "https://github.com/limitbreakinc/lbamm"
    WIKI_TITLE = "Unchecked Delegatecall Return"
    WIKI_DESCRIPTION = (
        "Detects delegatecall operations where the return value (success boolean) "
        "is not checked, which can silently fail."
    )
    WIKI_RECOMMENDATION = "Always check the return value of delegatecall and revert on failure."
    WIKI_EXPLOIT_SCENARIO = (
        "A delegatecall to a pool type fails silently, leaving the AMM in an "
        "inconsistent state while the caller assumes success."
    )

    def _detect(self):
        results = []
        for contract in self.compilation_unit.contracts_derived:
            for function in contract.functions:
                for node in function.nodes:
                    # Check assembly blocks for delegatecall
                    if node.inline_asm:
                        asm = str(node.inline_asm)
                        # Find delegatecall in assembly
                        if "delegatecall" in asm:
                            # Check if the return value is used in a conditional
                            has_check = False
                            for succ_node in node.sons:
                                succ_asm = str(succ_node.inline_asm) if succ_node.inline_asm else ""
                                node_str = str(succ_node)
                                if any(kw in (succ_asm + node_str).lower()
                                       for kw in ["iszero", "if", "require", "revert"]):
                                    has_check = True
                                    break
                            # Also check within the same assembly block
                            if re.search(r'if\s+iszero\(', asm) or "revert" in asm:
                                has_check = True

                            if not has_check:
                                info = [
                                    f"Unchecked delegatecall return in ",
                                    function,
                                    f" at ",
                                    node,
                                    f"\n",
                                ]
                                res = self.generate_result(info)
                                results.append(res)

        return results
