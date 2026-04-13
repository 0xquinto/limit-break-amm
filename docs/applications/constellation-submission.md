# Constellation Form — Anthropic Fellows Program (AI Security)

> URL: https://airtable.com/appiuxxfhf5moRwTx/pagmAb8OBNWyM5NDX/form
> Deadline: April 26, 2026 for July 2026 cohort
> This is the real application.

---

## General Information

| Field | Value |
|-------|-------|
| First Name | Diego |
| Last Name | Gomez |
| Email | diego.gomez210@gmail.com |
| Pronunciation | dee-EH-go GO-mez |
| Pronouns | _(fill in or leave blank)_ |
| Resume | _(attach PDF)_ |
| Applied to MATS/Astra/Fellows in past year? | _(fill in: Yes or No)_ |
| AI policy confirmation | Yes |

---

## Links & Code Samples

| Field | Value |
|-------|-------|
| Google Scholar | _(fill in or leave blank)_ |
| LinkedIn | https://linkedin.com/in/dgomezi21 |
| GitHub | https://github.com/0xquinto |
| Personal website | _(fill in or leave blank)_ |

### Code Samples — Description

> Paste into the "Share links and descriptions" box.

**Primary project: Limit Break AMM Security Audit Framework**
https://github.com/0xquinto/limit-break-amm

Role: Sole author. Built a multi-agent security audit orchestrator using the Claude Agent SDK to hunt vulnerabilities across 6 Solidity repos (Limit Break AMM, ~15K lines of Solidity 0.8.24) for the Guardian Defender bug bounty contest (Feb-Apr 2026).

The system has two modes: compliance mode (9 agents, 500 turns each, builds a structured knowledge base) and exploit mode (3 agents, consumes the knowledge base to find exploitable bugs). Both use per-archetype system prompts with hypothesis injection, structured checklists, and 4-stage verification gates (Forge test compilation, FP dedup, net-value check, config protection).

Key technical contributions:
- 34 Python modules, 283 pytest tests orchestrating Claude Opus 4.6 and Sonnet 4.6 agents
- 6-dimension compliance scoring system (0-120) with experiment tracking across 24 runs
- Evidence-gated enforcement to counter agent compliance theater (agents faking thoroughness)
- Cross-run hypothesis persistence (375 tracked hypotheses, 60 catalogued false positives)
- Trace analyzer with 16-dimension intelligence extraction from agent JSONL traces
- Coverage sweep pipeline (Slither call graph + Sonnet classification + gap detection)

Research grounded in Anthropic's SCONE-bench methodology (Best@K sampling, dollar-value scoring, forked-chain validation) and SHADE-Arena findings (agent outputs cannot be blindly trusted, motivating the artifact-existence gates).

Score trajectory: 39.8/120 (F) to 112.5/120 (A) over 17 compliance experiments. First novel finding (CP-006, CLOBHelper double-rounding) discovered in a $29 exploit mode run.

---

## Motivation & Fit

### Why are you interested in participating in the Fellows program? (1-2 paragraphs)

I spent the last month building a multi-agent system that hunts smart contract vulnerabilities autonomously, and the hardest problem wasn't the security research — it was controlling the agents. Across 24 experiment runs I discovered that agents fake thoroughness when unsupervised (what I call "compliance theater"), quit early the moment a task feels done enough (satisficing), and silently corrupt their own output through schema deviations. These aren't theoretical concerns; they're empirical observations from deploying 18 agent archetypes across 500-turn sessions with real tool access. The enforcement mechanisms I built — artifact-existence gates, depth floors, structured verification pipelines — are the same class of problems Anthropic's AI Security team works on, just discovered from the applied side.

The Fellows program is the right next step because my work is empirical but unsupervised. I've read and built on Anthropic's published research (SCONE-bench for exploit benchmarking methodology, SHADE-Arena for understanding agent deception), but I've been working in isolation. I want access to the mentorship and research infrastructure to turn these applied observations into rigorous, publishable findings — specifically around detecting and preventing agent compliance theater in high-stakes agentic deployments. The security domain is where I have the deepest context, and it's where the failure modes are most consequential.

### Area of technical AI safety work you're excited about (1 paragraph)

Agent behavioral integrity in high-stakes tool-use settings. When agents have access to compilers, static analyzers, and blockchain forking infrastructure, the gap between "claiming to have tested something" and "actually testing it" becomes safety-critical. In my audit framework, I found that without artifact-existence verification, agents self-reported thoroughness that was contradicted by their actual tool usage logs — and this happened with both Opus and Sonnet models, across offensive and defensive framings. I'm excited about building systematic benchmarks and detection methods for this class of failure, because it generalizes beyond security: any agentic system where outputs have real-world consequences (code deployment, financial transactions, infrastructure changes) needs reliable methods to verify that the agent actually did the work it claims to have done.

### Relevant AI safety background (1 paragraph, optional)

Built and operated a 34-module Python orchestrator using the Claude Agent SDK that spawns up to 18 specialized agents (Opus 4.6 + Sonnet 4.6) with per-archetype system prompts, adaptive thinking budgets, and MCP tool integration (Slither, Halmos, Medusa, Forge). Ran 24 tracked experiments with controlled variables and keep/discard decisions, producing 10 published agent engineering findings on compliance theater, satisficing, schema tolerance, and knowledge persistence. Participated in the Guardian Defender smart contract bug bounty contest. Research grounded in SCONE-bench (Anthropic, Dec 2025), SHADE-Arena / Sabotage Risk Report, PoCo (KTH), VulTrial (ICSE 2026), and 20+ papers from the AI-for-security and agent reliability literature. All code and findings are open source at github.com/0xquinto/limit-break-amm.

### How likely to accept a full-time offer? (brief + %)

90%. Anthropic is where the most consequential AI safety work is happening, and the security team's research direction — empirical evaluation of agentic capabilities and risks — is exactly what I want to do. The only scenario where I wouldn't accept is if the fellowship research leads me to a specific problem that another organization is better positioned to address, which I consider unlikely given Anthropic's breadth.

### How likely to continue working on AI safety after the program? (brief + %)

95%. My trajectory over the past two months has moved entirely toward AI safety through the security lens. The agent behavioral integrity problems I've encountered are too important and too underexplored to walk away from. Whether at Anthropic or elsewhere, this is the work I want to do.

---

## References

> YOU MUST FILL THESE IN. I've left placeholders. You need 3 references who can speak to technical collaboration.

### Reference 1

| Field | Value |
|-------|-------|
| Name | _(fill in)_ |
| Email | _(fill in)_ |
| Background | _(title, website, Google Scholar, public info)_ |
| Relationship | _(what you worked on, when, how long, how closely)_ |

### Reference 2

| Field | Value |
|-------|-------|
| Name | _(fill in)_ |
| Email | _(fill in)_ |
| Background | _(title, website, Google Scholar, public info)_ |
| Relationship | _(what you worked on, when, how long, how closely)_ |

### Reference 3

| Field | Value |
|-------|-------|
| Name | _(fill in)_ |
| Email | _(fill in)_ |
| Background | _(title, website, Google Scholar, public info)_ |
| Relationship | _(what you worked on, when, how long, how closely)_ |

---

## Logistics

| Field | Value |
|-------|-------|
| Cohort | July 2026 |
| Timelines/deadlines | _(fill in or leave blank)_ |
| Earliest full-time start | _(fill in, e.g., "Immediately after the program ends")_ |
| Country of residence | _(fill in)_ |
| Work authorization | _(select: USA, UK, Canada, or None)_ |
| Work authorization details | _(fill in if needed)_ |
| Workspace | _(select: Berkeley entire/25%+, London entire/25%+, or Other)_ |
| Previously applied to Anthropic? | _(Yes or No)_ |
| Other commitments | _(fill in, e.g., "No other commitments. I am available full-time, 40 hours per week for the entire duration of the program.")_ |
| How did you hear about it? | _(fill in or leave blank)_ |

### Anything else? (optional)

The 10 agent engineering findings published in the project README (https://github.com/0xquinto/limit-break-amm#agent-engineering-findings) are a condensed version of what I learned from this work. Finding #2 (compliance theater) and Finding #3 (satisficing) are directly relevant to the AI Security team's research on agentic risk evaluation — they're empirical observations of the same phenomena studied in the SHADE-Arena paper, discovered independently through applied deployment.

| Field | Value |
|-------|-------|
| Share info with other AI safety orgs? | _(Yes or No)_ |
