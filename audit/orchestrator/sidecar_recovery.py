"""Recover sidecar JSON from agent traces when agents died before writing output.

Extracts: truncated sidecar Write calls, text blocks with findings/analysis,
forge test file references, hypothesis results. Writes canonical sidecar JSON.

Usage:
  .venv/bin/python3 -m audit.orchestrator.sidecar_recovery --trace-dir audit/targets/full-system/artifacts
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone


# Sidecar schema fields
_EMPTY_SIDECAR = {
    "agent": "",
    "wave": 1,
    "target": "full-system",
    "recovery_source": "trace",
    "findings": [],
    "vectors_ruled_out": [],
    "test_files_created": [],
    "checklist_coverage": {},
    "summary": "",
}

# Known repos for resolving test file paths
_REPOS = [
    "lbamm-core", "amm-pool-type-dynamic", "lbamm-pool-type-fixed",
    "lbamm-pool-type-single-provider", "lbamm-hooks-and-handlers",
]


def extract_from_trace(trace_path: Path, project_root: Path) -> dict:
    """Extract recoverable sidecar data from a single trace file."""
    agent = trace_path.stem.removeprefix("trace-")

    sidecar_fragments = []    # Truncated JSON from Write calls
    text_findings = []        # Text blocks mentioning findings
    text_analysis = []        # All substantive text blocks (>50 chars)
    test_files_written = []   # .t.sol files created/edited
    files_read = set()        # All files the agent examined
    forge_test_results = []   # Bash commands with forge test
    hypothesis_mentions = []  # Text mentioning hypotheses
    checklist_mentions = []   # Text mentioning C-XX checklist items

    for line in trace_path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        turn = entry.get("turn", 0)

        for b in entry.get("blocks", []):
            btype = b.get("type")

            if btype == "tool_use":
                name = b.get("name", "")
                inp = b.get("input", {})

                if name == "Write":
                    fp = inp.get("file_path", "")
                    content = inp.get("content", "")
                    fname = Path(fp).name

                    if "findings" in fname.lower() or "sidecar" in fname.lower():
                        sidecar_fragments.append({
                            "turn": turn,
                            "file": fname,
                            "content": content,
                            "length": len(content),
                        })

                    if fname.endswith(".t.sol"):
                        test_files_written.append({
                            "turn": turn,
                            "file": fname,
                            "path": fp,
                            "content_length": len(content),
                        })

                elif name == "Edit":
                    fp = inp.get("file_path", "")
                    if Path(fp).name.endswith(".t.sol"):
                        test_files_written.append({
                            "turn": turn,
                            "file": Path(fp).name,
                            "path": fp,
                            "content_length": 0,  # edit, not full content
                        })

                elif name == "Read":
                    fp = inp.get("file_path", "")
                    files_read.add(fp)

                elif name == "Bash":
                    cmd = inp.get("command", "")
                    if "forge test" in cmd:
                        forge_test_results.append({
                            "turn": turn,
                            "command": cmd[:500],
                        })

            elif btype == "text":
                text = b.get("text", "")

                if len(text) > 50:
                    text_analysis.append({"turn": turn, "text": text})

                # Findings keywords
                if any(kw in text.lower() for kw in [
                    "confirmed", "ruled out", "vulnerability", "exploit",
                    "finding", "no profit", "guard holds", "not exploitable",
                    "drain", "overflow", "underflow", "reentrancy",
                ]):
                    text_findings.append({"turn": turn, "text": text})

                # Hypothesis mentions
                hyp_matches = re.findall(r'H[-_]?R?\d+[-_]?\w*[-_]?\d*', text)
                if hyp_matches:
                    hypothesis_mentions.append({
                        "turn": turn,
                        "ids": hyp_matches,
                        "text": text[:300],
                    })

                # Checklist item mentions
                checklist_matches = re.findall(r'\bC\d{1,2}\b', text)
                if checklist_matches:
                    checklist_mentions.append({
                        "turn": turn,
                        "items": checklist_matches,
                        "text": text[:300],
                    })

    # Deduplicate test files
    seen_tests = set()
    unique_tests = []
    for tf in test_files_written:
        if tf["file"] not in seen_tests:
            seen_tests.add(tf["file"])
            unique_tests.append(tf)

    # Check if test files still exist on disk (only at the exact path the agent wrote)
    test_files_on_disk = []
    for tf in unique_tests:
        disk_path = Path(tf["path"])
        if disk_path.exists():
            test_files_on_disk.append({
                "file": tf["file"],
                "path": tf["path"],
                "size": disk_path.stat().st_size,
                "exists": True,
            })
        else:
            test_files_on_disk.append({
                "file": tf["file"],
                "path": tf["path"],
                "exists": False,
            })

    # Extract partial sidecar JSON if available
    parsed_sidecar = None
    for frag in sidecar_fragments:
        content = frag["content"]
        # Try parsing as-is (might be complete)
        try:
            parsed_sidecar = json.loads(content)
            break
        except json.JSONDecodeError:
            # Truncated — try to repair by closing open structures
            parsed_sidecar = _attempt_json_repair(content)
            if parsed_sidecar:
                parsed_sidecar["_truncated"] = True
                break

    # Collect all checklist items mentioned
    all_checklist_items = set()
    for cm in checklist_mentions:
        all_checklist_items.update(cm["items"])

    return {
        "agent": agent,
        "trace_file": str(trace_path),
        "total_turns": max((json.loads(l).get("turn", 0) for l in trace_path.read_text().splitlines() if l.strip()), default=0),
        "parsed_sidecar": parsed_sidecar,
        "sidecar_fragments": sidecar_fragments,
        "text_findings": text_findings,
        "text_analysis": text_analysis,
        "test_files_written": unique_tests,
        "test_files_on_disk": test_files_on_disk,
        "forge_test_commands": forge_test_results,
        "hypothesis_mentions": hypothesis_mentions,
        "checklist_items_seen": sorted(all_checklist_items),
        "files_read_count": len(files_read),
        "recovery_quality": _assess_quality(
            parsed_sidecar, text_findings, unique_tests, test_files_on_disk
        ),
    }


def _attempt_json_repair(content: str) -> dict | None:
    """Try to repair truncated JSON by finding the last complete key-value pair."""
    # Strategy: walk backwards to last complete "key": value, then close all brackets
    # Find the last complete string value (ending with ")
    # or the last complete number/boolean/null

    # Try progressively shorter prefixes, trimming to last comma or closing bracket
    for trim_to in [
        content.rfind('",'),       # last complete string value
        content.rfind('"},'),      # last complete object in array
        content.rfind('],'),       # last complete array
        content.rfind('},'),       # last complete nested object
        content.rfind(': "'),      # last key start (incomplete value)
    ]:
        if trim_to <= 0:
            continue
        # Trim to just after the comma
        snippet = content[:trim_to + 1]
        # Remove trailing comma if present
        snippet = snippet.rstrip().rstrip(",")

        # Build closing brackets by tracking what's open
        stack = []
        in_string = False
        escape = False
        for ch in snippet:
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in '{[':
                stack.append('}' if ch == '{' else ']')
            elif ch in '}]':
                if stack:
                    stack.pop()

        suffix = "".join(reversed(stack))
        try:
            result = json.loads(snippet + suffix)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue

    return None


def _assess_quality(parsed_sidecar, text_findings, test_files, test_files_on_disk) -> str:
    """Rate recovery quality: full, partial, minimal, empty."""
    if parsed_sidecar and not parsed_sidecar.get("_truncated"):
        return "full"

    has_sidecar = parsed_sidecar is not None
    has_findings_text = len(text_findings) >= 3
    has_tests_on_disk = any(t.get("exists") for t in test_files_on_disk)

    if has_sidecar and has_tests_on_disk:
        return "partial"  # truncated sidecar + test files
    elif has_findings_text and has_tests_on_disk:
        return "partial"  # text analysis + test files
    elif has_findings_text or has_tests_on_disk:
        return "minimal"
    else:
        return "empty"


def build_recovery_sidecar(extraction: dict) -> dict:
    """Build a sidecar from extracted trace data. Best-effort."""
    agent = extraction["agent"]
    sidecar = dict(_EMPTY_SIDECAR)
    sidecar["agent"] = agent
    sidecar["recovery_source"] = "trace"
    sidecar["recovery_quality"] = extraction["recovery_quality"]
    sidecar["recovery_timestamp"] = datetime.now(timezone.utc).isoformat()

    # Start from parsed sidecar if available
    if extraction["parsed_sidecar"]:
        ps = extraction["parsed_sidecar"]
        sidecar["findings"] = ps.get("findings", [])
        sidecar["vectors_ruled_out"] = ps.get("vectors_ruled_out",
                                               ps.get("ruled_out_vectors", []))
        sidecar["checklist_coverage"] = ps.get("checklist_coverage", {})
        sidecar["summary"] = ps.get("summary", "")
        sidecar["test_file"] = ps.get("test_file", "")
        # Preserve any extra fields from the original
        for k in ("profit_question", "answer", "profit_question_answer",
                   "scope", "hypothesis_results", "invariants_verified"):
            if k in ps:
                sidecar[k] = ps[k]
        if ps.get("_truncated"):
            sidecar["_note"] = "Recovered from truncated Write call in trace"

    # Add test files
    for tf in extraction["test_files_on_disk"]:
        if tf.get("exists"):
            sidecar["test_files_created"].append({
                "path": tf["path"],
                "exists_on_disk": True,
            })

    # Add checklist items seen in text
    if not sidecar["checklist_coverage"] and extraction["checklist_items_seen"]:
        sidecar["checklist_coverage"] = {
            item: "mentioned_in_trace" for item in extraction["checklist_items_seen"]
        }

    # Build summary from text findings if none exists
    if not sidecar["summary"] and extraction["text_findings"]:
        # Take the longest/most substantive text findings
        sorted_texts = sorted(extraction["text_findings"],
                              key=lambda x: len(x["text"]), reverse=True)
        summary_parts = []
        for tf in sorted_texts[:5]:
            summary_parts.append(f"[Turn {tf['turn']}] {tf['text'][:300]}")
        sidecar["summary"] = "RECOVERED FROM TRACE TEXT:\n" + "\n".join(summary_parts)

    # Build vectors_ruled_out from text analysis if empty
    # Only extract conclusive statements, not operational debugging text
    _CONCLUSION_PATTERNS = [
        "ruled out", "guard holds", "not exploitable", "no profit",
        "no victim", "non-exploitable", "structurally inapplicable",
        "does not exist", "cannot be exploited", "no attack path",
        "invariant holds", "confirmed safe",
    ]
    if not sidecar["vectors_ruled_out"] and extraction["text_findings"]:
        idx = 0
        for tf in extraction["text_findings"]:
            text = tf["text"]
            text_lower = text.lower()
            # Must contain a conclusion keyword AND be >100 chars (not a fragment)
            if len(text) > 100 and any(kw in text_lower for kw in _CONCLUSION_PATTERNS):
                idx += 1
                sidecar["vectors_ruled_out"].append({
                    "id": f"VR-TRACE-{idx:02d}",
                    "title": text[:100],
                    "description": text[:500],
                    "severity": "info",
                    "status": "ruled_out",
                    "evidence": f"trace turn {tf['turn']}",
                    "_recovered": True,
                })

    return sidecar


def recover_all(
    trace_dir: Path,
    project_root: Path,
    output_dir: Path | None = None,
    skip_existing: bool = True,
) -> list[dict]:
    """Recover sidecars for all agents in trace_dir."""
    output_dir = output_dir or trace_dir
    results = []

    for trace_path in sorted(trace_dir.glob("trace-*.jsonl")):
        agent = trace_path.stem.removeprefix("trace-")

        # Skip pass 1 agents
        if agent.startswith("knowledge-gen-"):
            continue

        # Skip if sidecar already exists
        if skip_existing:
            existing = [
                output_dir / f"findings-{agent}.json",
                output_dir / f"findings-{agent}-draft.json",
            ]
            if any(p.exists() for p in existing):
                results.append({
                    "agent": agent,
                    "status": "skipped",
                    "reason": "sidecar exists",
                })
                continue

        extraction = extract_from_trace(trace_path, project_root)

        if extraction["recovery_quality"] == "empty":
            results.append({
                "agent": agent,
                "status": "empty",
                "reason": "no recoverable data in trace",
            })
            continue

        sidecar = build_recovery_sidecar(extraction)

        out_path = output_dir / f"findings-{agent}-recovered.json"
        out_path.write_text(json.dumps(sidecar, indent=2) + "\n")

        results.append({
            "agent": agent,
            "status": "recovered",
            "quality": extraction["recovery_quality"],
            "output": str(out_path),
            "findings": len(sidecar["findings"]),
            "ruled_out": len(sidecar["vectors_ruled_out"]),
            "test_files": len(sidecar["test_files_created"]),
            "checklist_items": len(sidecar["checklist_coverage"]),
        })

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Recover sidecars from agent traces")
    parser.add_argument("--trace-dir", type=Path,
                        default=Path("audit/targets/full-system/artifacts"))
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing sidecars")
    parser.add_argument("--agent", type=str, default=None,
                        help="Recover single agent")
    args = parser.parse_args()

    output_dir = args.output_dir or args.trace_dir

    if args.agent:
        trace_path = args.trace_dir / f"trace-{args.agent}.jsonl"
        if not trace_path.exists():
            print(f"No trace for {args.agent}")
            sys.exit(1)
        extraction = extract_from_trace(trace_path, args.project_root)
        print(json.dumps({
            "agent": extraction["agent"],
            "quality": extraction["recovery_quality"],
            "total_turns": extraction["total_turns"],
            "sidecar_fragments": len(extraction["sidecar_fragments"]),
            "text_findings": len(extraction["text_findings"]),
            "text_analysis": len(extraction["text_analysis"]),
            "test_files_on_disk": extraction["test_files_on_disk"],
            "forge_tests": len(extraction["forge_test_commands"]),
            "checklist_items": extraction["checklist_items_seen"],
            "hypothesis_mentions": len(extraction["hypothesis_mentions"]),
        }, indent=2))

        if extraction["recovery_quality"] != "empty":
            sidecar = build_recovery_sidecar(extraction)
            out_path = output_dir / f"findings-{args.agent}-recovered.json"
            out_path.write_text(json.dumps(sidecar, indent=2) + "\n")
            print(f"\nSidecar written to {out_path}")
    else:
        results = recover_all(
            args.trace_dir, args.project_root, output_dir,
            skip_existing=not args.force,
        )
        for r in results:
            status = r["status"]
            agent = r["agent"]
            if status == "recovered":
                q = r["quality"]
                print(f"  {agent:<28} RECOVERED ({q}) — "
                      f"{r['findings']} findings, {r['ruled_out']} ruled_out, "
                      f"{r['test_files']} tests, {r['checklist_items']} checklist")
            elif status == "skipped":
                print(f"  {agent:<28} SKIPPED — {r['reason']}")
            else:
                print(f"  {agent:<28} EMPTY — {r['reason']}")


if __name__ == "__main__":
    main()
