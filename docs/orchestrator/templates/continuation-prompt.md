# {{AGENT_NAME}} — Compliance Continuation (Wave {{WAVE_NUMBER}})

You are continuing the work of a previous agent that did not complete its full checklist. Your job is to complete ONLY the uncompleted items.

## What Was Already Done

The previous agent completed this work:
- Ruled-out vectors: {{RULED_OUT_COUNT}}
- Findings: {{FINDINGS_COUNT}}
- Tools used: {{TOOLS_USED}}
- Checklist reported: {{CHECKLIST_REPORTED}}

Their sidecar is at: `{{SIDECAR_PATH}}`
Read it first to understand what was already investigated.

## What You Must Complete

The compliance scorer identified these gaps:

{{COMPLIANCE_GAPS}}

## Your Checklist

Complete every numbered item below that the previous agent did NOT complete. Skip items they already did (check their sidecar's ruled_out_vectors and metadata).

{{CHECKLIST}}

## Instructions

1. Read the previous agent's sidecar from `{{SIDECAR_PATH}}`
2. For each uncompleted checklist item: write a Forge test OR run the specified tool
3. Write your results to a NEW sidecar at `{{OUTPUT_SIDECAR_PATH}}`
4. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
5. In metadata, set `"continuation": true` and `"parent_agent": "{{AGENT_NAME}}"`
6. Your context window will be automatically compacted — do NOT stop early due to token budget concerns

## Scope

{{SCOPE_REPOS}}

## Tools Available

You have access to Forge, Halmos, Medusa, Slither MCP, Aderyn, and all Skills. Use them.
