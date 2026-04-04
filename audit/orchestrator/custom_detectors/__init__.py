"""Custom Slither detectors for Limit Break AMM patterns.

Installed as a Slither plugin via entry_points(group="slither_analyzer.plugin").
Each entry point must be a callable returning (detectors, printers).
"""

from .diamond_slot_collision import DiamondSlotCollision
from .hook_reentrancy import HookReentrancy
from .transient_storage_leak import TransientStorageLeak
from .unchecked_delegatecall_return import UncheckedDelegatecallReturn


def make_plugin():
    return [DiamondSlotCollision, HookReentrancy, TransientStorageLeak, UncheckedDelegatecallReturn], []
