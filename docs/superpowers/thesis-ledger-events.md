# Thesis Ledger — Event Log

**Append-only.** Never edit or delete past events. State (current P0/P1/P2 list) is *derived* by replaying this log — not stored directly.

## Event format

```
[ISO-8601 timestamp] [actor] OP item_id severity | one-line payload
```

- `actor`: one of `hostile-reviewer`, `methodology-critic`, `ai-safety-reviewer`, `defi-translator`, `technical-writer`, `application-strategist`, `lead`, `user`
- `OP`: one of `ADD_ISSUE`, `RESOLVE_ISSUE`, `REPRIORITIZE`, `NOTE`, `ROUND_STARTED`, `SPECIALIST_INVOKED`, `SPECIALIST_COMPLETED`, `ROUND_COMPLETED`, `ROUND_ABANDONED`
- `item_id`: stable identifier like `I-001`, `I-042`. Reused across events that refer to the same issue.
- `severity`: `P0` / `P1` / `P2` / `—` (for non-issue events)
- `payload`: one-line summary. If longer context is needed, link to a file or review-log entry.

## Event type reference

| OP | Actor(s) | Required fields | Purpose |
|---|---|---|---|
| `ADD_ISSUE` | any specialist | item_id, severity | Record a new issue surfaced in review |
| `RESOLVE_ISSUE` | specialist or user | item_id | Mark an issue as addressed |
| `REPRIORITIZE` | specialist | item_id, new_severity | Change P-level after re-review |
| `NOTE` | any | — | Freeform annotation (e.g., "draft revised, see commit abc123") |
| `ROUND_STARTED` | lead | — | Multi-specialist review round begins |
| `SPECIALIST_INVOKED` | lead | name | Lead spawned a specialist |
| `SPECIALIST_COMPLETED` | lead | name | Specialist returned output; items already logged |
| `ROUND_COMPLETED` | lead | — | All planned specialists in a round have completed |
| `ROUND_ABANDONED` | lead or user | — | Round terminated before completion (reason in payload) |

## Derived state (do not edit — regenerate by replay)

_Replay the event log to compute current P0/P1/P2 lists. Formula:_
- `current_issues = {item_id: latest_severity} for all ADD_ISSUE / REPRIORITIZE events, minus item_ids with matching RESOLVE_ISSUE events`
- Sort by severity (P0 first), then by first-seen timestamp

**Current P0:** _(none yet — no events logged)_
**Current P1:** _(none yet)_
**Current P2:** _(none yet)_

## Events

_No events yet. First event will be logged when the first specialist review runs._
