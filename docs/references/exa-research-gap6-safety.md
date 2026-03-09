# Exa Research: Multi-Agent LLM Security & Observability (Gap 6)

> **Date**: 2026-03-09 | **Model**: exa-research-pro | **Cost**: $2.55 cumulative ($1.09 v1 + $1.46 v2) | **Sources**: 218 pages, 68 searches

## 1. Structured Observability Logging Schemas

### 1.1 OpenTelemetry GenAI Semantic Conventions (Industry Standard)

The OTel GenAI SIG (active since April 2024, Development status as of early 2026) defines standardized attribute schemas. Major vendors (Datadog, Honeycomb, New Relic) and frameworks (LangChain, CrewAI, AutoGen) already emit OTel-compliant spans.

**Core span types and their attributes:**

| Span Type | `gen_ai.operation.name` | Key Attributes |
|-----------|------------------------|----------------|
| LLM inference | `chat` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.request.temperature`, `gen_ai.request.max_tokens`, `gen_ai.response.finish_reasons` |
| Agent invocation | `invoke_agent` | `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.agent.description`, `gen_ai.operation.name` |
| Agent creation | `create_agent` | `gen_ai.agent.name`, `gen_ai.agent.id` |
| Tool execution | `execute_tool` | `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` |

**Token usage attributes (all Recommended level):**
- `gen_ai.usage.input_tokens` — Tokens in prompt
- `gen_ai.usage.output_tokens` — Tokens in completion
- `gen_ai.usage.cache_creation.input_tokens` — Tokens written to cache
- `gen_ai.usage.cache_read.input_tokens` — Tokens served from cache

**Prompt/completion content** — Captured as span _events_ (not attributes) to handle arbitrary size:
```
span.addEvent('gen_ai.content.prompt', {
  'gen_ai.prompt': JSON.stringify(messages),
});
span.addEvent('gen_ai.content.completion', {
  'gen_ai.completion': completion.content,
});
```

**Metrics (histograms, counters):**
- `gen_ai.client.token.usage` — Histogram of token counts per operation, tagged by model/system
- `gen_ai.client.operation.duration` — Duration of LLM operations in seconds
- `gen_ai.server.time_per_output_token` — Time-to-first-token and inter-token latency
- `gen_ai.agent.tool_loop_detected` — Counter for loop detection events

**Span naming conventions:**
- LLM calls: `{operation.name} {gen_ai.system}` → e.g. `chat anthropic`
- Agent invocations: `invoke_agent {gen_ai.agent.name}` → e.g. `invoke_agent SecurityAuditor`
- Tool calls: `execute_tool {gen_ai.tool.name}` → e.g. `execute_tool slither_scan`

**PR #2528** (closed Aug 2025) added `gen_ai.tool_definitions`, `gen_ai.tool.call.arguments`, and `gen_ai.tool.call.result` attributes for multi-agent traceability.

### 1.2 Concrete Per-Turn Log Schema (Composite)

Synthesized from Arize Phoenix, LangSmith, and OTel conventions — recommended for the audit framework:

```json
{
  "timestamp": "2026-03-09T17:00:00.000Z",
  "session_id": "audit-lbamm-v3-20260309",
  "agent_id": "auditor-clob-01",
  "agent_name": "CLOB Auditor",
  "turn_number": 7,
  "operation": "chat",
  "model": "claude-opus-4-6",
  "provider": "anthropic",
  "input_tokens": 12450,
  "output_tokens": 3200,
  "cache_read_tokens": 8000,
  "latency_ms": 4200,
  "cost_usd": 0.187,
  "tool_calls": [
    {
      "id": "call_abc123",
      "name": "grep_codebase",
      "arguments": {"pattern": "sqrtPriceX96", "path": "src/hooks/"},
      "result_summary": "12 matches in 4 files",
      "duration_ms": 45
    }
  ],
  "finish_reason": "end_turn",
  "outcome": "in_progress",
  "error": null
}
```

### 1.3 Per-Session Summary Schema

```json
{
  "session_id": "audit-lbamm-v3-20260309",
  "agent_id": "auditor-clob-01",
  "started_at": "2026-03-09T16:30:00Z",
  "completed_at": "2026-03-09T17:45:00Z",
  "total_turns": 28,
  "total_input_tokens": 340000,
  "total_output_tokens": 85000,
  "total_cost_usd": 5.12,
  "tool_calls_total": 47,
  "tool_calls_failed": 2,
  "findings_count": 3,
  "findings_severity": {"high": 0, "medium": 1, "low": 2},
  "exit_reason": "task_complete",
  "goal_drift_detected": false
}
```

### 1.4 Platform-Specific Notes

- **Arize Phoenix**: OpenAPI-defined schemas with `id`, `timestamp`, `type`, `agent_name`, `model_name`, `input`, `output`, `duration_ms`. Uses distributed tracing with Jaeger/Zipkin export.
- **LangSmith**: Message schemas with `role`, `content`, `tool_calls[]`, `name`. Tool definition schemas with `type`, `name`, `description`, `parameters`.
- **Anthropic Console**: Structured output schemas with `response`, `tool_calls[]` (each with `tool_name`, `input`). Claude Agent SDK adds session-level checkpoint states.

---

## 2. Output Validation and Hallucination Detection for Code Analysis

### 2.1 CRITIC Pattern (Iterative Self-Critique)

Generate → Tool-evaluate → Revise → Repeat:

```python
output = agent.generate(input)
while not is_valid(output):
    feedback = external_tool.evaluate(output)  # static analyzer, compiler, test runner
    output = agent.revise(output, feedback)
return output
```

Already implemented in the audit framework via: Forge compilation validates PoC code, Slither validates finding locations, red-team agent critiques auditor outputs.

### 2.2 Cross-Agent Validation (Table-Critic Pattern)

Multiple specialized agents critique and refine:
1. **Initial reasoning** — Auditor generates finding
2. **Judge** detects logical errors
3. **Critic** provides structured critique
4. **Refiner** revises finding
5. Iterate until convergence or max rounds

Maps to existing framework: auditor → red-team reviewer → PoC writer verification chain.

### 2.3 Deterministic AST-Based Verification (New — 2026)

From [arXiv:2601.19106](https://arxiv.org/html/2601.19106v1):
```python
code = agent.generate(input)
ast = parse_to_ast(code)          # Parse generated code
conflicts = detect_conflicts(ast, kb)  # Cross-reference with library KB
corrected_ast = auto_correct(ast, conflicts)
corrected_code = ast_to_code(corrected_ast)
```

**Applicability to audit framework**: Parse generated Solidity PoCs into AST, validate function selectors and state variable references exist in the target contract. Catches hallucinated function names/signatures.

### 2.4 HALT Framework (Multi-Signal Hallucination Detection)

From [OpenReview:YysFSiPQf7](https://openreview.net/forum?id=YysFSiPQf7):
- Uses confidence scoring, self-consistency checks, and cross-verification
- No external knowledge base required
- Detects hallucinations at inference time via multi-signal analysis

### 2.5 HaluGate (Token-Level Detection)

Real-time token-level hallucination detection — flags uncertain tokens during generation. More relevant for streaming applications than batch audit workflows.

### 2.6 Practical FP Gate for Audit Framework

Recommended composite validation pipeline:

```
Finding → Compile PoC (Forge) → Run PoC (forge test) → Verify location exists (grep/AST)
    → Cross-check with Slither detectors → Red-team challenge → PASS/FAIL
```

Each gate is a binary pass/fail. Finding must pass ALL gates to be reported.

---

## 3. Circuit Breakers, Kill Switches, and Runaway Agent Prevention

### 3.1 Layered Protection Architecture

```
┌─────────────────────────────────────────────┐
│         Orchestrator / Business Logic        │
├─────────────────────────────────────────────┤
│   Response Validation (Pydantic schema)      │  ← Catches malformed output
├─────────────────────────────────────────────┤
│   Observability (OTel spans + metrics)       │  ← Records everything
├─────────────────────────────────────────────┤
│   Circuit Breaker (per agent/provider)       │  ← Fast-fails during outages
├─────────────────────────────────────────────┤
│   Budget Control (token + dollar limits)     │  ← Prevents cost overrun
├─────────────────────────────────────────────┤
│   Loop Detection (state hashing)             │  ← Catches infinite loops
├─────────────────────────────────────────────┤
│   Turn Limiter (hard cap)                    │  ← Absolute safety net
├─────────────────────────────────────────────┤
│         LLM Provider API                     │
└─────────────────────────────────────────────┘
```

### 3.2 AgentBudget — Drop-in Cost Enforcement

[github.com/sahiljagtap08/agentbudget](https://github.com/sahiljagtap08/agentbudget) — Pure Python, zero infrastructure.

Three-layer protection:
```python
import agentbudget

budget = AgentBudget(
    max_spend="$5.00",
    soft_limit=0.9,               # Warn at 90% spent
    max_repeated_calls=10,         # Trip after 10 repeated calls
    loop_window_seconds=60.0,      # Within a 60-second window
    on_soft_limit=lambda r: log.warning("90% budget used"),
    on_hard_limit=lambda r: alert_ops_team(r),
    on_loop_detected=lambda r: log.error("Loop detected!"),
)
# Raises BudgetExhausted when $5 limit is hit
```

Real-time structured logging:
```
agentbudget · session_7f3a
14:23:01 INFO  Session started · budget: $5.00
14:23:02 LLM   gpt-4o · 847 tokens · cost: $0.0029
14:23:05 LLM   gpt-4o · 2,104 tokens · cost: $0.0073
14:23:06 COST  Running total: $0.0202 · remaining: $4.98
14:24:51 WARN  Soft limit reached · 90%
```

### 3.3 AgentCircuit — Decorator-Based Safety

[github.com/simranmultani197/AgentCircuit](https://github.com/simranmultani197/AgentCircuit) — `@reliable` decorator with 4 components:

```python
from agentcircuit import reliable, GlobalBudget

budget = GlobalBudget(max_cost_usd=10.0, max_seconds=120)

@reliable(
    sentinel_schema=FindingReport,  # Pydantic validation
    fuse_limit=3,                   # Loop detection (3 identical states)
    budget=budget,                  # Shared cost tracking
    model="claude-opus-4-6"
)
def audit_module(state):
    return call_agent(state)
```

Execution flow:
```
Budget → Over budget? → STOP (BudgetExceededError)
  ↓
Fuse → Loop detected? → STOP (LoopError)
  ↓
Run function
  ↓
Pricing → Track cost (model-aware)
  ↓
Sentinel → Output valid? → Return result
  ↓ (invalid)
Medic → LLM fixes output → Sentinel validates again
```

### 3.4 Aura Guard — Middleware for Tool-Using Agents

[github.com/auraguardhq/aura-guard](https://github.com/auraguarddev-debug/aura-guard) — Deterministic policy engine, sub-millisecond overhead, no LLM calls.

```python
from aura_guard import AgentGuard, PolicyAction

guard = AgentGuard(
    secret_key=b"your-secret-key",
    side_effect_tools={"refund", "cancel"},  # Mark dangerous tools
    max_calls_per_tool=3,                     # Cap expensive tools
    max_cost_per_run=1.00,                    # Budget per run
)

decision = guard.check_tool("search_kb", args={"query": "refund policy"})
if decision.action == PolicyAction.ALLOW:
    result = execute_tool(...)
elif decision.action == PolicyAction.BLOCK:
    stop_agent(decision.reason)
```

6 policy actions: `ALLOW`, `CACHE`, `BLOCK`, `REWRITE`, `ESCALATE`, + system prompt injection for steering.

**Demo result**: Without guard = 60 rounds, 79,525 tokens, never stops. With guard = immediate detection and halt.

### 3.5 Reverse Proxy Kill Switch (AIR Blackbox)

YAML-based policy enforcement via reverse proxy between agent and LLM:

```yaml
policies:
  - name: loop-detector
    trigger:
      type: rate-limit
      max_requests: 50
      window_seconds: 60
    action: block
    alert: true

  - name: budget-cap
    trigger:
      type: cost-limit
      max_cost_usd: 5.00
    action: block

  - name: tool-restriction
    trigger:
      type: tool-call
      blocked_tools: ["execute_command", "run_shell", "delete_file"]
    action: block
```

Agent code change = 1 line (`base_url="http://localhost:8080/v1"`). Includes Jaeger tracing + Prometheus metrics + episode replay.

### 3.6 Goal Drift Detection

From [arXiv:2602.22302](https://arxiv.org/html/2602.22302v1) — Agent Behavioral Contracts:
- Define formal behavioral invariants per agent
- Runtime checks compare agent actions against contract
- Violations trigger shutdown or correction

**For audit framework**: Contract = "agent must only analyze files in `src/` scope, must not modify source files, must produce findings in specified JSON schema."

### 3.7 Recommended Configuration for Audit Framework

Based on v2 calibration data:

| Agent Type | max_turns | max_cost_usd | fuse_limit | timeout_min |
|------------|-----------|--------------|------------|-------------|
| Auditor (plan) | 15 | $3.00 | 3 | 15 |
| Auditor (impl) | 30 | $8.00 | 3 | 30 |
| Fuzz-writer | 35 | $10.00 | 5 | 35 |
| PoC-writer | 12 | $3.00 | 3 | 15 |
| Economic modeler | 22 | $5.00 | 3 | 20 |
| Red-team reviewer | 22 | $5.00 | 3 | 20 |

---

## 4. Cascading Failure Prevention in Hub-and-Spoke Architectures

### 4.1 Error Cascade Model

From [arXiv:2603.04474](https://arxiv.org/html/2603.04474v1) — "From Spark to Fire":
- Errors propagate through message dependencies in multi-agent systems
- A single hallucinated finding from one agent can poison the orchestrator's context
- **Genealogy-graph tracking**: Track message provenance, suppress propagation when risk exceeds threshold

### 4.2 Isolation Patterns

1. **Per-agent context isolation** — Each agent gets its own conversation context; orchestrator selectively merges results
2. **Resource quotas** — Token budgets, turn limits, and time limits per agent (see §3.7)
3. **Sandboxed execution** — Forge tests run in isolated environments; agent file access restricted to scope
4. **Memory isolation with TTL**:
   ```python
   class SecureMemory:
       def __init__(self, max_items=100, ttl_seconds=3600):
           self.memory = []
           self.max_items = max_items
       def add(self, item):
           if len(self.memory) >= self.max_items:
               self.memory.pop(0)
           self.memory.append(item)
   ```

### 4.3 Consensus/Voting Mechanisms

From [Patterns for Democratic Multi-Agent AI](https://medium.com/@edoardo.schepis/patterns-for-democratic-multi-agent-ai-voting-based-council-part-1-9a9164a173ff):
- **Majority voting**: Multiple agents evaluate same finding; accepted only if majority agrees
- **Quorum validation**: Minimum N agents must confirm before finding escalates
- **Weighted voting**: Specialist agents (e.g., economic modeler for economic findings) get higher weight

**For audit framework**: Red-team + PoC-writer + original auditor = 3-vote quorum. Finding requires 2/3 agreement.

### 4.4 Backpressure

- **Concurrency limits**: Max N agents running simultaneously (prevents context/API saturation)
- **Event-sourcing**: Serialize agent outputs through an ordered queue; orchestrator processes one at a time
- **Rate limiting per agent**: Prevent any single agent from dominating API quotas

### 4.5 Independent Verification Pipeline

```
Auditor finding → PoC-writer compiles & runs → Red-team challenges →
  Slither cross-check → Orchestrator accepts/rejects
```

Each stage is independent and can fail without cascading to other agents.

---

## 5. Agent Autonomy Boundaries and Privilege Escalation Prevention

### 5.1 Mandatory Access Control for LLM Agents

From [arXiv:2601.11893](https://arxiv.org/html/2601.11893v1) — "Taming Various Privilege Escalation in LLM-Based Agent Systems":
- Formal MAC framework preventing agents from escalating privileges
- Three escalation vectors: **vertical** (gaining admin access), **horizontal** (accessing other agents' data), **context** (manipulating system prompts)
- Mitigation: Explicit capability declarations + runtime enforcement

### 5.2 Least-Privilege Tool Access

Scope permissions explicitly per agent:
```python
tools = [
    {
        "name": "file_reader",
        "allowed_paths": ["/app/src/*", "/app/test/*"],
        "allowed_operations": ["read"],
        "denied_paths": ["/app/.env", "/app/secrets/*"]
    },
    {
        "name": "forge_test",
        "allowed_operations": ["test", "build"],
        "denied_operations": ["deploy", "broadcast"]
    }
]
```

Middleware confirmation for sensitive actions:
```python
SENSITIVE_TOOLS = {"file_writer", "git_push", "deploy"}

def require_confirmation(tool_name):
    if tool_name in SENSITIVE_TOOLS:
        return prompt_user_for_approval()
    return True
```

### 5.3 Agent Capability Declaration (A2A-Style)

Each agent declares its capabilities at spawn time:
```json
{
  "agent_name": "clob-auditor",
  "capabilities": ["read_source", "grep_codebase", "run_slither", "write_finding"],
  "restrictions": ["no_file_write", "no_git_operations", "no_network_access"],
  "scope": "src/handlers/clob/",
  "max_tokens": 500000,
  "max_turns": 30
}
```

Runtime enforcement validates every tool call against declared capabilities.

### 5.4 Zero Trust for AI Agents

From [Cloud Security Alliance — Agentic Trust Framework](https://cloudsecurityalliance.org/blog/2026/02/02/the-agentic-trust-framework-zero-trust-governance-for-ai-agents):
- Never trust agent output by default
- Verify every action against policy
- Log everything for audit trail
- Assume agents can be compromised (prompt injection, hallucination)

### 5.5 OWASP Agentic Top 10 (2026) Relevant Items

From [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026):
1. **Agentic Resource Exhaustion** — Infinite loops draining budgets (→ §3)
2. **Privilege Escalation** — Agent gaining unauthorized access (→ §5.1)
3. **Broken Access Control** — Missing tool-level authorization (→ §5.2)
4. **Cascading Hallucination** — One agent's hallucination propagating (→ §4)

---

## 6. Resilience Patterns for LLM API Calls

### 6.1 Error Classification

```python
class ErrorSeverity(Enum):
    TRANSIENT = "transient"   # Retry with backoff (429, timeout, connection)
    PERMANENT = "permanent"   # Fail immediately (auth, bad request)
    DEGRADED = "degraded"     # Switch to fallback (context overflow, content filter)
```

Key insight from [AI Workflow Lab](https://aiworkflowlab.dev): "A 2026 study found agents achieve only 60% success on single runs, dropping to 25% across eight consecutive runs without resilience engineering."

### 6.2 Defense-in-Depth Stack

```
Response Validation (Pydantic/schema)  ← Catches malformed output
Observability (OTel logging/metrics)   ← Records everything
Circuit Breaker (per provider)         ← Fast-fails during outages
Fallback Chain (multi-provider)        ← Switches providers on failure
Retry with Exponential Backoff+Jitter  ← Handles transient errors
LLM Provider API                       ← Bottom layer
```

### 6.3 Production Circuit Breaker (PyBreaker)

```python
import pybreaker

# One breaker per provider — NEVER share across providers
anthropic_breaker = pybreaker.CircuitBreaker(
    fail_max=5,           # Open after 5 consecutive failures
    reset_timeout=60,     # Try again after 60 seconds
    success_threshold=2,  # Require 2 successes before closing
    name="anthropic-claude",
)

@anthropic_breaker
def call_claude(client, messages, **kwargs):
    return client.messages.create(
        model="claude-opus-4-6",
        messages=messages,
        max_tokens=8192,
        timeout=30,
    )
```

---

## 7. Actionable Recommendations for Audit Framework

### 7.1 Five Observability Log Lines (Gap 6 Deliverable)

Add these 5 structured log events to `agent-boilerplate.md`:

1. **SESSION_START**: `{timestamp, session_id, agent_id, agent_name, model, scope, max_turns, max_cost_usd}`
2. **TURN_COMPLETE**: `{timestamp, session_id, agent_id, turn_number, input_tokens, output_tokens, cost_usd, latency_ms, tool_calls[], finish_reason}`
3. **TOOL_CALL**: `{timestamp, session_id, agent_id, tool_name, arguments_summary, result_summary, duration_ms, success}`
4. **SAFETY_EVENT**: `{timestamp, session_id, agent_id, event_type[budget_warning|loop_detected|goal_drift|turn_limit], details, action_taken}`
5. **SESSION_END**: `{timestamp, session_id, agent_id, total_turns, total_tokens, total_cost_usd, findings_count, exit_reason[task_complete|budget_exhausted|turn_limit|error|killed]}`

### 7.2 Implementation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Turn limits + budget caps in orchestrator | Low | Prevents runaway costs |
| P0 | 5 log lines in boilerplate | Low | Enables all other observability |
| P1 | Per-agent context isolation | Medium | Prevents cascading hallucination |
| P1 | FP gate pipeline (compile → test → grep) | Medium | Reduces false positives |
| P2 | AgentCircuit/AgentBudget integration | Medium | Automated safety enforcement |
| P2 | Capability declarations per agent | Low | Least-privilege enforcement |
| P3 | OTel span export to Jaeger/Grafana | High | Production-grade dashboards |
| P3 | Voting/quorum for findings | Medium | Consensus-based accuracy |

---

## Key Sources

### Academic Papers
- [Privilege Escalation in LLM Agents (arXiv 2601.11893)](https://arxiv.org/html/2601.11893v1)
- [Agent Behavioral Contracts (arXiv 2602.22302)](https://arxiv.org/html/2602.22302v1)
- [Error Cascades in Multi-Agent (arXiv 2603.04474)](https://arxiv.org/html/2603.04474v1)
- [AST-Based Hallucination Detection (arXiv 2601.19106)](https://arxiv.org/html/2601.19106v1)
- [HALT Framework (OpenReview YysFSiPQf7)](https://openreview.net/forum?id=YysFSiPQf7)
- [HADA: Human-AI Decision Alignment (arXiv 2506.04253)](https://arxiv.org/html/2506.04253v1)

### Standards & Frameworks
- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/)
- [OTel GenAI Agent Spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
- [OWASP Top 10 Agentic 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026)
- [CSA Agentic Trust Framework](https://cloudsecurityalliance.org/blog/2026/02/02/the-agentic-trust-framework-zero-trust-governance-for-ai-agents)
- [Stanford: Kill Switches & Policy](https://law.stanford.edu/2026/03/07/kill-switches-dont-work-if-the-agent-writes-the-policy-the-berkeley-agentic-ai-profile-through-the-ailccp-lens)

### Tools & Libraries
- [AgentBudget](https://agentbudget.dev/) — Dollar-denominated cost enforcement
- [AgentCircuit](https://pypi.org/project/agentcircuit/) — Decorator-based safety (loop, budget, validation)
- [Aura Guard](https://github.com/auraguarddev-debug/aura-guard) — Deterministic policy engine for tool calls
- [AIR Blackbox](https://github.com/airblackbox/air-platform) — Reverse proxy kill switch
- [PyBreaker](https://github.com/danielfm/pybreaker) — Python circuit breaker pattern
- [Arize Phoenix](https://github.com/Arize-ai/phoenix) — LLM observability platform

### Production Guides
- [AI Agent Resilience Patterns (AI Workflow Lab)](https://aiworkflowlab.dev/article/ai-agent-resilience-production-retry-fallback-circuit-breaker-python)
- [OTel for AI Agents (Zylos Research)](https://zylos.ai/research/2026-02-28-opentelemetry-ai-agent-observability)
- [GenAI Semantic Conventions (OneUptime)](https://oneuptime.com/blog/post/2026-02-06-monitor-llm-opentelemetry-genai-semantic-conventions/view)
- [OpenClaw Reliability & Security Patterns](https://kenhuangus.substack.com/p/openclaw-design-patterns-part-5-of)
- [Securing AI Agents (System Weakness)](https://systemweakness.com/securing-ai-agents-an-architecture-for-systems-you-cant-fully-control-fad4b9d5c8ef)
- [Multi-Agent Tuning in Production (Towards AI)](https://pub.towardsai.net/i-spent-months-tuning-multi-agent-systems-in-production-87d3840d2a93)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [Anthropic: Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
