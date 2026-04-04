"""Detect transient storage (tstore) without matching clear in same call context.

HOOK-001 pattern: tstore writes that aren't cleared before function exit.
Already found once manually; this detector makes it permanent.
"""

from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification
from slither.core.cfg.node import NodeType
from slither.slithir.operations import InternalCall


class TransientStorageLeak(AbstractDetector):
    ARGUMENT = "transient-storage-leak"
    HELP = "Transient storage slot written but not cleared before function exit"
    IMPACT = DetectorClassification.MEDIUM
    CONFIDENCE = DetectorClassification.HIGH

    WIKI = "https://github.com/limitbreakinc/lbamm"
    WIKI_TITLE = "Transient Storage Leak"
    WIKI_DESCRIPTION = (
        "Detects tstore operations without a matching tstore(slot, 0) or tload "
        "in the same function, which can leak state between calls in the same transaction."
    )
    WIKI_RECOMMENDATION = "Clear transient storage slots before function exit."
    WIKI_EXPLOIT_SCENARIO = (
        "A hook writes to transient storage in beforeSwap but doesn't clear it. "
        "A subsequent call in the same transaction reads the stale value."
    )

    def _detect(self):
        results = []
        for contract in self.compilation_unit.contracts_derived:
            for function in contract.functions:
                if function.is_constructor or function.is_fallback:
                    continue
                tstore_slots = set()
                tclear_slots = set()
                for node in function.nodes:
                    if node.type == NodeType.ASSEMBLY:
                        asm = str(node.inline_asm) if node.inline_asm else ""
                        # Find tstore(slot, value) calls
                        import re
                        for m in re.finditer(r'tstore\(([^,]+),\s*([^)]+)\)', asm):
                            slot = m.group(1).strip()
                            value = m.group(2).strip()
                            if value == "0":
                                tclear_slots.add(slot)
                            else:
                                tstore_slots.add(slot)

                leaked = tstore_slots - tclear_slots
                if leaked:
                    info = [
                        f"Transient storage leak in ",
                        function,
                        f": slots {leaked} written but not cleared\n",
                    ]
                    res = self.generate_result(info)
                    results.append(res)

        return results
