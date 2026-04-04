"""Config protection verification gate.

Detects when agents modify build configuration files (foundry.toml,
remappings.txt, etc.) instead of fixing their code. These modifications
can mask compilation errors and produce false-positive test results.

Inspired by ECC config-protection hook pattern, adapted for post-wave
verification instead of pre-tool blocking.
"""

import subprocess
from pathlib import Path

from .config import PROJECT_ROOT

# Files that agents should never modify — they should fix their code instead
_PROTECTED_PATTERNS = [
    "foundry.toml",
    "remappings.txt",
    "hardhat.config",
    ".solhint",
    ".prettierrc",
    ".eslintrc",
]


def _git_diff_names() -> list[str]:
    """Get list of modified files from git diff (unstaged + staged)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
            timeout=10,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def check_config_modifications() -> list[dict]:
    """Check for agent modifications to protected config files.

    Returns list of violations: [{"file": str, "severity": "warning", "message": str}]
    """
    changed = _git_diff_names()
    violations = []
    for filepath in changed:
        name = Path(filepath).name
        for pattern in _PROTECTED_PATTERNS:
            if pattern in name:
                violations.append({
                    "file": filepath,
                    "severity": "warning",
                    "message": (
                        f"Agent modified {name} — likely to bypass compilation errors. "
                        f"Review the change and revert if the agent weakened config."
                    ),
                })
                break
    return violations
