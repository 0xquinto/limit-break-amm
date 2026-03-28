# SessionStart Hook Setup

Add this to `.claude/settings.local.json` to auto-run context-sync on compact and resume:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/skills/context-sync/scripts/context_sync.py --auto",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

If you already have hooks in settings.local.json, merge the `SessionStart` entry into your existing `hooks` object.

The `--auto` flag runs in quiet mode — only outputs staleness warnings, no verbose logging.
