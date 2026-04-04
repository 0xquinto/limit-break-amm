# Dry-Run Mode for Full Pipeline

## Status: PLANNED (not started)

## Problem
--dry-run only renders prompts. Cannot validate scoring, synthesis,
or reflection without spending API credits.

## Design
- --dry-run loads sidecars from most recent archive run
- Runs full post-processing pipeline (kill gate → synthesis → scoring → reflection)
- Skips: agent spawning, Pass 1, compliance continuation
- Outputs: compliance score, synthesis, reflection — all from cached data

## Acceptance Criteria
- [ ] --dry-run runs full pipeline with zero API calls
- [ ] Uses latest archived sidecars as mock agent output
- [ ] Produces same compliance score as the original run (regression test)

## Estimated Effort: 1 day
