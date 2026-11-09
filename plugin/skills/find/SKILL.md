---
name: find
description: Find past or open Claude Code sessions with `herdr-valet search` (parked, closed, resumed and open sessions, and every transcript, by title, summary, first message, project, folder or branch) and, once the user says yes, resume one, fork it, start it fresh, or open a new session in a project. Use when the user asks "I worked on X a while ago, didn't I?", "where did Y end up?", "which session did Z?", "hace tiempo estuve con X, ¿no?", "¿dónde quedó lo de Y?", "buscame la sesión de…", or runs /valet:find.
---

# Find a session (and reopen it)

## 1. Search

Use the keywords of what the user said: nouns and names, no filler. "A while ago I was on the
bank login" becomes `login bank`. Every word must match; accents do not matter.

```bash
herdr-valet search login bank --json --limit 8
```

Each result has `session_id`, `state`, `title`, `where` (where it was left), `first` (the user's
first request), `label`, `cwd`, `branch`, `at` and, if open, `pane_id`.

| state | What it is |
|---|---|
| `open` | Open in herdr right now |
| `parked` | Parked, with a card |
| `closed` | Closed by hand; its card goes away in a few days |
| `resumed` | Already reopened: may be open under another id, or finished |
| `transcript` | Only its conversation exists, no card |

- **No hits:** try fewer words, a synonym or the other language (banco / bank), at most twice.
  Then say it was not found. Never invent a session.
- **Many hits:** keep the top 3–5 (ordered by relevance, then recency).

## 2. Show and ask

Show one line per candidate, in the user's language: `date · state · project [branch] · title`.
Under it, `where` (or `first` when there is no `where`), trimmed.

Then ask what they want. **Never open or start anything without a yes.** If the question was only
"did I work on this?", answering is enough; offer nothing extra.

## 3. Do what they chose

| They want… | State | Command |
|---|---|---|
| That conversation back | `parked`, `closed`, `resumed`, `transcript` | `herdr-valet resume <session_id>` |
| That conversation back | `open` | Nothing to start: say where it is (`label`, `pane_id`) |
| A copy, to ask it something else | any but `open` | `herdr-valet resume <session_id> --fork` |
| A copy of an open one | `open` | `herdr-valet fork <pane_id>` |
| To pick it up clean, without its history | `parked`, `closed` | `herdr-valet fresh <session_id> [--prompt "<what to do>"]` |
| New work in a project | — | `herdr-valet new <id>[@<branch>] [--prompt "<goal>"]` (see /valet:new) |

`resume` works with or without a card. Without one, it opens the conversation in a tab of its
repository's workspace, and refuses if the conversation is already running; then say where it is.
`--fork` opens a copy with its own session id and leaves the original as it is. To fork *this*
session, use /valet:fork.

A big conversation that has gone cold costs dollars to resume, because all of it is re-read. If
`herdr-valet stats <session_id>` shows a large one, mention that `fresh` costs cents instead.

End with one line: what opened, and where (workspace or tab, folder and branch).

**Errors:**
- **`herdr is not running`:** there is nowhere to open it. The error includes the command to run
  by hand.
- **`new sessions are off`:** the launcher commands are missing from the config. Say so, and do
  not edit it.
- **Anything else from `new`** (bad branch, repo not cloned) comes from the launcher: show it as
  is.
