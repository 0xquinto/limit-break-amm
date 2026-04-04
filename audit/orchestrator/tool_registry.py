"""Tool path registry — discovers external tools at startup.

Replaces hardcoded paths like ~/.foundry/bin/forge, /opt/homebrew/bin/aderyn, etc.
with shutil.which() discovery + fallback paths. Call discover_tools() once at startup.
"""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    name: str
    path: str | None  # None = not found
    fallback_paths: list[str] = field(default_factory=list)


# Known tools and their fallback locations (searched after shutil.which)
_TOOL_SPECS: dict[str, list[str]] = {
    "forge": ["~/.foundry/bin/forge"],
    "chisel": ["~/.foundry/bin/chisel"],
    "cast": ["~/.foundry/bin/cast"],
    "anvil": ["~/.foundry/bin/anvil"],
    "slither": [],  # usually in PATH via pip/uv
    "aderyn": ["~/.local/bin/aderyn", "/opt/homebrew/bin/aderyn"],
    "halmos": ["~/.local/bin/halmos"],
    "medusa": ["/opt/homebrew/bin/medusa"],
}

_registry: dict[str, ToolInfo] = {}


def _resolve(name: str, fallbacks: list[str]) -> ToolInfo:
    """Resolve a tool using shutil.which, then fallbacks."""
    found = shutil.which(name)
    if found:
        return ToolInfo(name=name, path=found, fallback_paths=fallbacks)

    for fb in fallbacks:
        expanded = str(Path(fb).expanduser())
        if Path(expanded).is_file() and Path(expanded).stat().st_mode & 0o111:
            return ToolInfo(name=name, path=expanded, fallback_paths=fallbacks)

    return ToolInfo(name=name, path=None, fallback_paths=fallbacks)


def discover_tools(extra_specs: dict[str, list[str]] | None = None) -> dict[str, ToolInfo]:
    """Discover all tools. Call once at startup.

    Args:
        extra_specs: Additional {tool_name: [fallback_paths]} to check beyond defaults.
    """
    global _registry
    specs = {**_TOOL_SPECS, **(extra_specs or {})}

    for name, fallbacks in specs.items():
        info = _resolve(name, fallbacks)
        _registry[name] = info
        if info.path:
            logger.info("Tool %s: %s", name, info.path)
        else:
            logger.warning("Tool %s: NOT FOUND (checked: PATH + %s)", name, fallbacks)

    return _registry


def get_tool_path(name: str) -> str | None:
    """Get resolved path for a tool. Returns None if not found."""
    if not _registry:
        discover_tools()
    info = _registry.get(name)
    return info.path if info else None


def require_tool(name: str) -> str:
    """Get resolved path, raise if not found."""
    path = get_tool_path(name)
    if path is None:
        raise FileNotFoundError(
            f"Required tool '{name}' not found. "
            f"Searched: PATH + {_TOOL_SPECS.get(name, [])}"
        )
    return path


def format_tool_table() -> str:
    """Format discovered tools as a markdown table for agent prompts.

    Used by prompt_renderer.py via {{TOOL_PATHS}} template variable.
    """
    if not _registry:
        discover_tools()

    lines = ["| Tool | Path | Status |", "|------|------|--------|"]
    for name, info in sorted(_registry.items()):
        if info.path:
            lines.append(f"| {name} | `{info.path}` | available |")
        else:
            lines.append(f"| {name} | — | not installed |")
    return "\n".join(lines)
