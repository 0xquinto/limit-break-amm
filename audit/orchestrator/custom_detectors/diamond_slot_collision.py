"""Detect potential storage slot collisions in diamond proxy pattern.

Checks that storage slot constants (0x9A1D pattern) don't collide across
modules. Walks all sstore/sload in assembly blocks and flags overlapping slots.
"""

import re
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification


class DiamondSlotCollision(AbstractDetector):
    ARGUMENT = "diamond-slot-collision"
    HELP = "Storage slot constants that may collide across diamond facets"
    IMPACT = DetectorClassification.HIGH
    CONFIDENCE = DetectorClassification.MEDIUM

    WIKI = "https://github.com/limitbreakinc/lbamm"
    WIKI_TITLE = "Diamond Slot Collision"
    WIKI_DESCRIPTION = (
        "Detects storage slot constants used in assembly sstore/sload that appear "
        "in multiple contracts, indicating potential collision in the diamond proxy."
    )
    WIKI_RECOMMENDATION = "Ensure each facet uses unique storage slots, preferably via EIP-7201."
    WIKI_EXPLOIT_SCENARIO = (
        "Two facets use the same storage slot for different purposes. A call to "
        "facet A overwrites data used by facet B."
    )

    def _detect(self):
        results = []
        # Map: slot_constant -> list of (contract, function) that use it
        slot_usage: dict[str, list[tuple]] = {}

        for contract in self.compilation_unit.contracts_derived:
            for function in contract.functions:
                for node in function.nodes:
                    if not node.inline_asm:
                        continue
                    asm = str(node.inline_asm)
                    # Find hex constants in sstore/sload: sstore(0x1234, ...) or sload(0x1234)
                    for m in re.finditer(r's(?:store|load)\((0x[0-9a-fA-F]+)', asm):
                        slot = m.group(1).lower()
                        slot_usage.setdefault(slot, []).append(
                            (contract.name, function.name)
                        )

        # Flag slots used by multiple contracts
        for slot, usages in slot_usage.items():
            contracts_using = set(c for c, _ in usages)
            if len(contracts_using) > 1:
                usage_str = ", ".join(f"{c}.{f}" for c, f in usages)
                info = [
                    f"Storage slot {slot} used by multiple contracts: {usage_str}\n",
                ]
                res = self.generate_result(info)
                results.append(res)

        return results
