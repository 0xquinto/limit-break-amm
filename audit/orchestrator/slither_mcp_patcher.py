"""Reproducible patcher for slither-mcp's slither_wrapper.py.

Injects fix_build_info() into the installed slither-mcp package so that
MCP-path Slither handles cross-repo Forge build-info the same way the CLI does.

Run after every `uv tool install slither-mcp` or `uv tool upgrade slither-mcp`:

    .venv/bin/python3 -m audit.orchestrator.slither_mcp_patcher

Or call programmatically:

    from audit.orchestrator.slither_mcp_patcher import patch_slither_mcp
    patch_slither_mcp()
"""

import glob
import shutil
import textwrap
from pathlib import Path

PATCH_MARKER = "# PATCHED by lbamm audit framework — fix_build_info for cross-repo compat"


def _find_slither_wrapper() -> Path:
    """Locate the installed slither_mcp/slither_wrapper.py."""
    # Method 1: uv tool location (most common)
    candidates = glob.glob(
        str(Path.home() / ".local/share/uv/tools/slither-mcp/lib/python*/site-packages/slither_mcp/slither_wrapper.py")
    )
    if candidates:
        return Path(candidates[0])

    # Method 2: importlib (works if slither_mcp is importable)
    try:
        import importlib.util
        spec = importlib.util.find_spec("slither_mcp.slither_wrapper")
        if spec and spec.origin:
            return Path(spec.origin)
    except (ImportError, ModuleNotFoundError):
        pass

    # Method 3: pip site-packages
    candidates = glob.glob(
        str(Path.home() / ".local/lib/python*/site-packages/slither_mcp/slither_wrapper.py")
    )
    if candidates:
        return Path(candidates[0])

    raise FileNotFoundError(
        "Cannot find slither_mcp/slither_wrapper.py. "
        "Is slither-mcp installed? Try: uv tool install slither-mcp"
    )


def is_patched(wrapper_path: Path | None = None) -> bool:
    """Check if slither_wrapper.py already has our patch."""
    wrapper_path = wrapper_path or _find_slither_wrapper()
    return PATCH_MARKER in wrapper_path.read_text()


# The fix_build_info function to inject (standalone, no framework imports)
_FIX_BUILD_INFO = textwrap.dedent('''\
    def fix_build_info(repo_path: str) -> dict[str, int]:
        """Fix forge build-info for cross-repo compatibility.

        When repos import via ../ relative paths, Forge emits duplicate entries:
        absolute-path entries (with AST) and relative-path entries (without AST).
        This function:
          1. Copies ASTs from absolute entries to their relative-path duplicates
          2. Adds missing entries to input.sources with content read from disk
          3. Remaps cross-compilation AST node IDs in exportedSymbols/referencedDeclaration
        """
        totals = {"output_ast_fixed": 0, "input_content_added": 0, "ids_remapped": 0}

        for bi_file in glob.glob(os.path.join(repo_path, "out", "build-info", "*.json")):
            with open(bi_file) as f:
                data = json.load(f)

            modified = False
            output_sources = data.get("output", {}).get("sources", {})

            # Phase 1: Build real-path -> AST lookup from entries that have ASTs
            ast_lookup: dict[str, dict] = {}
            for name, val in output_sources.items():
                if val.get("ast"):
                    if os.path.isabs(name):
                        real = os.path.realpath(name)
                    else:
                        real = os.path.realpath(os.path.join(repo_path, name))
                    ast_lookup[real] = val["ast"]

            # Fix entries with missing ASTs
            for name, val in output_sources.items():
                if not val.get("ast"):
                    real = os.path.realpath(os.path.join(repo_path, name))
                    if real in ast_lookup:
                        val["ast"] = ast_lookup[real]
                        totals["output_ast_fixed"] += 1
                        modified = True

            # Phase 2: Fix input.sources missing entries
            input_sources = data.get("input", {}).get("sources", {})
            missing = set(output_sources.keys()) - set(input_sources.keys())
            for name in missing:
                file_path = name if os.path.isabs(name) else os.path.join(repo_path, name)
                real_path = os.path.realpath(file_path)
                if os.path.isfile(real_path):
                    with open(real_path) as f:
                        content = f.read()
                    input_sources[name] = {"content": content}
                    totals["input_content_added"] += 1
                    modified = True

            # Phase 3: Remap cross-compilation AST node IDs
            all_ids: set[int] = set()

            def _collect_ids(node):
                if isinstance(node, dict):
                    nid = node.get("id")
                    if isinstance(nid, int):
                        all_ids.add(nid)
                    for v in node.values():
                        _collect_ids(v)
                elif isinstance(node, list):
                    for item in node:
                        _collect_ids(item)

            for val in output_sources.values():
                ast = val.get("ast")
                if ast:
                    _collect_ids(ast)

            symbol_ids: dict[str, set[int]] = {}
            for val in output_sources.values():
                ast = val.get("ast", {})
                for sym_name, ids in ast.get("exportedSymbols", {}).items():
                    symbol_ids.setdefault(sym_name, set()).update(ids)

            remap: dict[int, int] = {}
            for sym_name, ids in symbol_ids.items():
                local = [i for i in ids if i in all_ids]
                foreign = [i for i in ids if i not in all_ids]
                if local and foreign:
                    for fid in foreign:
                        remap[fid] = local[0]

            if remap:
                def _remap_ast(node):
                    count = 0
                    if isinstance(node, dict):
                        if "exportedSymbols" in node:
                            for sym_name, ids in node["exportedSymbols"].items():
                                node["exportedSymbols"][sym_name] = [
                                    remap.get(i, i) for i in ids
                                ]
                                count += sum(1 for i in ids if i in remap)
                        ref = node.get("referencedDeclaration")
                        if isinstance(ref, int) and ref in remap:
                            node["referencedDeclaration"] = remap[ref]
                            count += 1
                        for v in node.values():
                            count += _remap_ast(v)
                    elif isinstance(node, list):
                        for item in node:
                            count += _remap_ast(item)
                    return count

                for val in output_sources.values():
                    ast = val.get("ast")
                    if ast:
                        totals["ids_remapped"] += _remap_ast(ast)
                if totals["ids_remapped"]:
                    modified = True

            if modified:
                with open(bi_file, "w") as f:
                    json.dump(data, f)

        return totals
''')

_PATCHED_ENSURE_BUILT = textwrap.dedent('''\
        def _ensure_built(self):
            """Ensure the Slither object is built and ready (PATCHED for cross-repo)."""
            if not self._built:
                print(f"Lazy-loading Slither for project at {self.path}...", file=sys.stderr)

                forge_path = _find_forge_executable()
                forge_dir = os.path.dirname(forge_path)
                if forge_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = f"{forge_dir}:{os.environ.get('PATH', '')}"

                npx_path = _find_npx_executable()
                npx_dir = os.path.dirname(npx_path)
                if npx_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = f"{npx_dir}:{os.environ.get('PATH', '')}"

                # Step 1: Build with forge (generates build-info)
                build_project_foundry(self.path)

                # Step 2: Fix build-info for cross-repo compatibility
                totals = fix_build_info(self.path)
                if totals["output_ast_fixed"]:
                    print(f"Fixed {totals['output_ast_fixed']} AST entries in build-info", file=sys.stderr)
                if totals["input_content_added"]:
                    print(f"Added {totals['input_content_added']} missing input sources", file=sys.stderr)
                if totals["ids_remapped"]:
                    print(f"Remapped {totals['ids_remapped']} cross-compilation AST node IDs", file=sys.stderr)

                # Step 3: Load Slither WITHOUT recompiling (uses patched build-info)
                prev_cwd = os.getcwd()
                try:
                    os.chdir(self.path)
                    self._slither = Slither(self.path, ignore_compile=True)
                finally:
                    os.chdir(prev_cwd)
                print("Slither object created successfully", file=sys.stderr)
                self._built = True
''')


def patch_slither_mcp(wrapper_path: Path | None = None, backup: bool = True) -> Path:
    """Patch the installed slither_wrapper.py for cross-repo compatibility.

    Returns the path to the patched file.
    """
    wrapper_path = wrapper_path or _find_slither_wrapper()
    content = wrapper_path.read_text()

    if PATCH_MARKER in content:
        print(f"Already patched: {wrapper_path}")
        return wrapper_path

    if backup:
        backup_path = wrapper_path.with_suffix(".py.orig")
        # Always overwrite — previous .orig may be from an older version
        shutil.copy2(wrapper_path, backup_path)
        print(f"Backup saved: {backup_path}")

    # Inject fix_build_info after the imports block
    import_anchor = "from slither import Slither"
    if import_anchor not in content:
        raise ValueError(f"Cannot find '{import_anchor}' in {wrapper_path} — unexpected file format")

    insert_idx = content.index(import_anchor) + len(import_anchor)
    # Skip to end of that line
    insert_idx = content.index("\n", insert_idx) + 1
    content = (
        content[:insert_idx]
        + f"\n{PATCH_MARKER}\n\n"
        + _FIX_BUILD_INFO
        + "\n"
        + content[insert_idx:]
    )

    # Replace _ensure_built method
    old_method_start = "    def _ensure_built(self):"
    old_method_marker = '        """Ensure the Slither object is built and ready"""'
    if old_method_start in content and old_method_marker in content:
        # Find the full method (from def to next def or @property at same indent)
        method_start = content.index(old_method_start)
        # Find end: next method/property at class level (4-space indent)
        rest = content[method_start + len(old_method_start):]
        lines = rest.split("\n")
        method_end = method_start + len(old_method_start)
        for i, line in enumerate(lines):
            if i == 0:
                continue
            # End of method: a line at 4-space indent that's a def or @
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if stripped and indent == 4 and (stripped.startswith("def ") or stripped.startswith("@")):
                method_end = method_start + len(old_method_start) + sum(len(l) + 1 for l in lines[:i])
                break
        else:
            method_end = len(content)

        content = content[:method_start] + _PATCHED_ENSURE_BUILT + "\n" + content[method_end:]
    elif PATCH_MARKER in content:
        # fix_build_info was injected but _ensure_built was already patched
        pass
    else:
        print(f"WARNING: Could not find _ensure_built method to replace in {wrapper_path}")
        print("The fix_build_info function was injected but _ensure_built was not updated.")

    wrapper_path.write_text(content)
    print(f"Patched: {wrapper_path}")
    return wrapper_path


def unpatch_slither_mcp(wrapper_path: Path | None = None) -> Path | None:
    """Restore the original slither_wrapper.py from backup, then remove backup."""
    wrapper_path = wrapper_path or _find_slither_wrapper()
    backup_path = wrapper_path.with_suffix(".py.orig")
    if backup_path.exists():
        shutil.copy2(backup_path, wrapper_path)
        backup_path.unlink()
        print(f"Restored: {wrapper_path} (backup removed)")
        return wrapper_path
    print(f"No backup found at {backup_path}")
    return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--unpatch":
        unpatch_slither_mcp()
    elif len(sys.argv) > 1 and sys.argv[1] == "--check":
        try:
            path = _find_slither_wrapper()
            patched = is_patched(path)
            print(f"{path}: {'patched' if patched else 'NOT patched'}")
            sys.exit(0 if patched else 1)
        except FileNotFoundError as e:
            print(str(e))
            sys.exit(2)
    else:
        patch_slither_mcp()
