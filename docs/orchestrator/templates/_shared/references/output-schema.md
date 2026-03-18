### Sidecar Schema

Write your JSON sidecar as a DRAFT first, then validate it through the gate. Use the agent_name and output paths from your main prompt's "Your Output Paths" section.

1. Write to: your draft sidecar path (see "Your Output Paths" in your main prompt)
2. Validate: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py <draft-path>`
3. If ACCEPTED — done. The gate promotes it to the final path.
4. If REJECTED — read the error output, fix the gaps, rewrite the draft, and retry.

DO NOT write directly to the final findings JSON — the gate is the only path to the final sidecar. If you skip the gate, your work will not be scored.

Sidecar schema:
```json
{
  "agent_name": "YOUR_AGENT_NAME",
  "agent_role": "YOUR_AGENT_ROLE",
  "wave": 1,
  "findings": [
    {
      "id": "PREFIX-NNN",
      "title": "one-line theft thesis",
      "severity": "critical",
      "confidence_score": 100,
      "confidence_deductions": [],
      "status": "confirmed",
      "category": "price-manipulation",
      "description": "one-line theft thesis",
      "impact": "who loses what + estimated USD or token amount",
      "proof_sketch": "Forge test path or reasoning chain",
      "victim": "who loses what",
      "extractable_value": "estimated USD or token amount",
      "attack_sequence": ["step1", "step2", "step3"],
      "test_file": "path to Forge test",
      "test_passes": true,
      "prerequisites": ["flash loan", "specific token pair", "etc"],
      "repos": ["repo-name"],
      "contracts": ["Contract.sol"],
      "functions": ["function()"],
      "lines": {"Contract.sol": [123, 456]},
      "keywords": ["flash-loan", "price-manipulation"],
      "fp_gate": {
        "location_exists": true,
        "entry_reachable": true,
        "no_existing_guard": true,
        "concrete_attack_path": true,
        "poc_compiles": true
      }
    }
  ],
  "ruled_out_vectors": [
    {
      "vector": "description",
      "why_ruled_out": "reason — must reference a test file or concrete code evidence",
      "test_file": "path to Forge test that proves the guard holds",
      "repos": ["repo-name"],
      "contracts": ["Contract.sol"],
      "functions": ["function()"],
      "keywords": ["keyword1", "keyword2"]
    }
  ],
  "theft_theses": [
    {
      "thesis": "description",
      "victim": "who",
      "asset": "what",
      "estimated_ev": 0,
      "status": "hypothesis|tested|confirmed|ruled_out"
    }
  ],
  "metadata": {
    "num_turns": 0, "tool_uses": 0, "files_read": 0,
    "tools_run": {},
    "theses_tested": 0, "theses_confirmed": 0, "theses_ruled_out": 0,
    "triage_log": {"skip": 0, "borderline": 0, "survive": 0}
  }
}
```

Replace `YOUR_AGENT_NAME`, `YOUR_AGENT_ROLE`, and `PREFIX` with the values from your main prompt.

**test_file format rule**: `"N/A"` is NOT acceptable as a test_file value. Use one of:
- **Test file path**: `"lbamm-core/test/audit/AuditStateDesync.t.sol"` — for Forge/Halmos/Medusa tests you wrote
- **Code citation**: `"code-analysis: AMMModule.sol:2144-2180"` — for vectors ruled out by code path analysis (cite specific lines)
- **Not applicable**: `"not-applicable: [reason]"` — only if the vector genuinely cannot be tested

`"code-analysis:"` citations receive PARTIAL credit only (50%). To get FULL credit, write a Forge test file. Even a simple `assertEq` test that demonstrates the vector was investigated counts as full credit. Prioritize writing tests over citing code.
