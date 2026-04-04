# audit/orchestrator/net_value_gate.py
"""Net-value economic verification gate (L-017).

Prevents submission of findings where single-token profit analysis masks
net-neutral or net-negative economics. Every finding claiming extractable_value
must provide two-token net_value_analysis.

Lesson learned: CRITICAL-001 claimed $4,750 USDC theft but attacker also lost
~$4,750 WETH. Net P&L was ~$0. This gate would have caught it.
"""

from dataclasses import dataclass


@dataclass
class NetValueVerdict:
    finding_id: str
    passed: bool
    reason: str
    net_profit_usd: float = 0.0


def check_net_value(finding: dict) -> NetValueVerdict:
    """Check a single finding for economic soundness.

    Rules:
    1. Findings without extractable_value skip the gate.
    2. Findings with extractable_value MUST have net_value_analysis.
    3. net_value_analysis.tokens_checked must have >= 2 entries.
    4. net_value_analysis.net_profit_usd must be > 0.
    """
    fid = finding.get("id", "unknown")
    ev = finding.get("extractable_value", "")

    # Rule 1: no profit claim → skip
    if not ev or finding.get("status") != "confirmed":
        return NetValueVerdict(finding_id=fid, passed=True, reason="no_profit_claim")

    # Rule 2: profit claimed but no analysis → fail
    nva = finding.get("net_value_analysis")
    if not nva or not isinstance(nva, dict):
        return NetValueVerdict(
            finding_id=fid, passed=False,
            reason="missing_analysis: finding claims extractable_value but has no net_value_analysis",
        )

    tokens = nva.get("tokens_checked", [])
    net_usd = nva.get("net_profit_usd", 0)

    # Rule 3: must check both tokens in a two-token pool
    if len(tokens) < 2:
        return NetValueVerdict(
            finding_id=fid, passed=False,
            reason=f"single_token: only checked {tokens}, must check both tokens (L-017)",
        )

    # Rule 4: net profit must be positive
    if net_usd < 0:
        return NetValueVerdict(
            finding_id=fid, passed=False, net_profit_usd=net_usd,
            reason=f"net_negative: attacker loses ${abs(net_usd):.2f} net",
        )
    if net_usd == 0:
        return NetValueVerdict(
            finding_id=fid, passed=False, net_profit_usd=0,
            reason="net_neutral: gains on one token offset by losses on another",
        )

    return NetValueVerdict(finding_id=fid, passed=True, net_profit_usd=net_usd, reason="verified")


def run_net_value_gate(sidecar: dict) -> list[NetValueVerdict]:
    """Run net-value gate on all findings in a sidecar."""
    return [check_net_value(f) for f in sidecar.get("findings", [])]
