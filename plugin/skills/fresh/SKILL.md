---
name: fresh
description: Start this Claude Code session over without its history, with `herdr-valet relaunch --mode fresh`. It parks this session and opens a new one next to it (same folder and model) that starts by reading a context file valet builds from the card, the compaction summary, what the user asked, the files written and the repo as it is now. Nothing of the old conversation is re-cached, so it costs cents. Use when the user asks to "start clean", "fresh session", "the context is too full", "empezá de cero con esto", "sesión limpia", or runs /valet:fresh. Never on your own initiative: suggest it and wait for a yes. When a handoff written with judgment matters, use /valet:continue instead.
---

# Start fresh

Say in one line that this session gets parked and the new one opens in a tab next to it. Then:

```bash
herdr-valet relaunch --mode fresh --prompt "<what the new session should do>"
```

- **`--prompt`** is optional. If the user said what comes next, pass it in their words. Without
  it, the new session reads the context file and waits.
- **What it does:** works on `$HERDR_PANE_ID` and carries on in the background. It parks this
  session (Haiku writes the card, ~15 s), then opens the new tab. Anything running in the
  background gets cut.
- **Versus `/valet:continue`:** nobody writes a handoff here. Valet assembles the context file
  from what exists, so it is faster and cheaper but less curated.
- **If it fails,** the session stays open: show the error as is.

**Without herdr:** suggest `/compact`, or `/clear` with a short summary written by hand.
