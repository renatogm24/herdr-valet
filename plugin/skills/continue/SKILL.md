---
name: continue
description: Hand this Claude Code session over to a new one in another herdr tab. Write a handoff with what the next session needs, then `herdr-valet continue` opens a tab next to this one (same workspace, folder and model), waits until the new session starts reading the handoff, and only then parks this one. Use when the user asks to go on in another session or window, "continue clean", "move this to a new session", "seguí en otra sesión", "pasalo a una nueva", or runs /valet:continue. Never on your own initiative: if the context is getting full, suggest it and wait for a yes. For a quicker handover without a written handoff, see /valet:fresh.
---

# Continue in a new session

There are two parts:
- **The handoff:** judgment about what the new session needs to know.
- **The handover:** mechanical, done by `herdr-valet continue`.

If the user gave a focus ("go on with F0", "only the tests"), write the handoff for that focus.

## 1. Write the handoff

File: `${XDG_DATA_HOME:-$HOME/.local/share}/claude-handoffs/<YYYY-MM-DD>-<slug>.md`. It lives
outside the repos, so git stays clean. If the user asks for another place, use that.

The new session saw nothing of this conversation. The handoff gives it **what it cannot get from
the files**, and for everything else says what to read. Do not copy what is already in a file, a
PR, an issue or a commit: give the path or the link.

```markdown
# Handoff — <topic> (<date>)

## Goal
What is being done and why, in 2–3 lines.

## Read first
- `/absolute/path` — why it matters (in reading order)
- PRs, issues, commits, with links

## State
- Done and verified: …
- Done, not verified: …
- Decided (with the why, when it is not written elsewhere): …

## Next step
The first concrete step, with the command or the file. Then what follows.

## Watch out
What was tried and failed, gotchas, things that look true and are not.

## Skills to use
The ones the new session should load for the next step, each with a one-line why. Only skills
that exist on this machine.

## Open questions for the user
Only the ones still unanswered.

## How the user works
Preferences seen in this session that are not already in CLAUDE.md or memory.
```

Leave out empty sections. Paths always absolute; dates absolute ("2026-11-08", not "yesterday").
Write it in the user's language.

## 2. Hand over

Say in one line where the handoff is and that the conversation goes on in the new tab. Then:

```bash
herdr-valet continue "<handoff path>"
```

- **What it does:** works on `$HERDR_PANE_ID`. A tab opens next to this one with the same model,
  and its first message points at the handoff. Once the new session shows up, this one is
  parked, and its card links to the new one (`continued_in` / `continued_from`).
- **This session closes by itself seconds later.** Nothing else to do after the command.
- **`--keep`:** leaves this session open, for when the user wants to come back to it.
- **"no session showed up":** the old session stays open. Say so, and leave the command to run by
  hand.

**Without herdr:** write the handoff anyway and give the command to start the new session by
hand in the same folder:
`cd "<cwd>" && claude --model <model> "Continue the work handed over in <path>: read it first, then carry on from where it leaves off."`
