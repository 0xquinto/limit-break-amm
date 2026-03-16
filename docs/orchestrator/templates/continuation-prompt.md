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

## MANDATORY TOOL RUNS

The following tools were NOT run by the original agent. You MUST run each one:

{{TOOLS_MISSING_BLOCK}}

For each tool:
1. Run it on every repo in scope
2. Log the result in metadata.tools_run (ran: true/false, note: what happened)
3. If it errors, log the error — that counts as completed

DO NOT SKIP THESE. Your sidecar will be scored on tool_breadth.

## Your Checklist

Complete every numbered item below that the previous agent did NOT complete. Skip items they already did (check their sidecar's ruled_out_vectors and metadata).

{{CHECKLIST}}

## Instructions

1. Read the previous agent's sidecar from `{{SIDECAR_PATH}}`
2. For each uncompleted checklist item: you MUST run the specified tool. If the item says "Halmos:", run halmos. If it says "Medusa:", run medusa. Writing a Forge test instead is NOT acceptable — the tool gate from Phase C applies to you. If the tool errors, log the error in your sidecar (that counts as completed). Only "not attempted" is a violation.
3. Write your results to a NEW sidecar at `{{OUTPUT_SIDECAR_PATH}}`
4. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
5. In metadata, set `"continuation": true` and `"parent_agent": "{{AGENT_NAME}}"`
6. Your context window will be automatically compacted — do NOT stop early due to token budget concerns

## PRE-COMPLETION GATE

Before writing your final sidecar:
1. Count tools_run entries with ran=true. Every tool listed in MANDATORY TOOL RUNS above must show ran=true.
2. Count ruled_out_vectors. You should have added vectors for each checklist item you completed.
3. Report checklist_items_completed in metadata: "C: N/M" format.

If any required tool shows ran=false without an error logged, you are NOT done.

## Scope

{{SCOPE_REPOS}}

## Tools Available

You have access to Forge, Halmos, Medusa, Slither MCP, Aderyn, and all Skills. Use them.
