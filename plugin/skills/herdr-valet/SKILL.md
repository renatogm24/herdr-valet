---
name: herdr-valet
description: How to use herdr-valet well from inside a Claude Code session. Covers which command fits (park, continue, fresh, restart, fork, new, find/resume, park-all, restore), which session a command acts on, what happens when a command closes the session it runs in, what each one costs, how to search, and what its errors mean. Load it before running any `herdr-valet` command, or when the user asks about their Claude sessions in herdr (parked, open, past), in any language ("aparcá", "reiniciá", "¿dónde quedó…?").
user-invocable: false
---

# herdr-valet

herdr-valet keeps Claude Code sessions that run in herdr (a terminal multiplexer) from getting
lost. It **parks** a session by writing a card (directory, model, a short summary of where things
stood) and then closing its pane. It **resumes** it later with the whole conversation
(`claude --resume`). It also starts sessions over without their history, hands work over to a
new session, and finds any past session. Everything goes through the `herdr-valet` CLI; the
command skills of this plugin (`/valet:park`, `/valet:find`, …) are thin wrappers around it.

## Which session a command acts on

- **This session:** commands that take a pane (`park`, `restart`, `fork`, `relaunch`, `continue`,
  `recap`) default to `$HERDR_PANE_ID`, the pane this session runs in.
- **Another open session:** pass its pane id, from `herdr-valet live --json`.
- **A parked or past session:** use its session id, from `herdr-valet list --json` or
  `herdr-valet search <words> --json`.

**A command that closes the session it runs in** (`park`, `restart`, `relaunch`, `continue`,
`park-all`) checks first, then carries on in the background and returns at once. Say in one line
what is about to happen *before* running it. After it, there is nothing left to do: this session
is about to close, and anything running in the background (subagents, tasks) is cut off.

## Which command

| The user wants… | Command | Cost and notes |
|---|---|---|
| To stop and come back later | `herdr-valet park` | Haiku writes the card (~15 s, cents) |
| To go on in a fresh session, carefully | `continue <handoff.md>` (`/valet:continue`) | Claude writes a handoff with judgment, then a new tab starts on it. Best quality |
| To go on in a fresh session, quickly | `relaunch --mode fresh [--prompt]` (`/valet:fresh`) | Valet builds a context file from the card, the compaction summary, the requests, the files written and the repo. Cents; nothing is re-cached |
| To load an update, new MCPs, plugins or skills | `restart` | Same conversation, same tab |
| To ask something on the side | `fork` | A copy in a new tab; this session is untouched |
| Work in a project | `new <id>[@<branch>] [--prompt]` (`/valet:new`) | Opens the branch's worktree or creates it; `adhoc:[name]` makes a scratch folder |
| To create, clone or add a project, or clean up worktrees | The **Projects** view on valet's page (no CLI command) | Shows each worktree's git status and what can be removed without losing anything |
| An old session | `search <words>`, then `resume <session_id> [--fork]` (`/valet:find`) | Resume re-reads the whole conversation: on a big, cold one that costs dollars. `fresh <session_id>` starts it over from its card instead |
| To reboot the machine | `park-all`, then later `restore` | One batch; restore reopens it where it was |
| To know where an open session stands | `recap <pane_id>` | A summary without closing it |
| To know what a session costs | `stats <session_id>` | Context, compactions, estimated cost |

Never run `park`, `restart`, `relaunch`, `continue`, `park-all` or `--force` on your own
initiative. If one would help (a full context, a newly installed MCP), suggest it and wait for a
yes.

## Searching

`herdr-valet search` matches sessions whose title, summary, first message, project, folder or
branch contain **all** the words (accents ignored). It is ordered by relevance, then recency. It
covers cards, open sessions and every Claude Code transcript, and uses no LLM.

- Use 1 to 3 distinctive words: names, nouns, project ids. Leave out filler ("worked", "session",
  "hace tiempo").
- With no hits, try fewer words, a synonym or the other language (banco / bank), at most twice.
  Then say it was not found. Never invent a session.
- `state` in the results: `open`, `parked`, `closed`, `resumed` (already reopened, maybe under
  another id), or `transcript` (no card). `resume` works for all of them except `open`: for an
  open one, say where it is (`label`, `pane_id`).

## Errors

| Message | Meaning |
|---|---|
| `herdr is not running` | Nowhere to open it. The error includes the command to run by hand |
| `… is working` / `waiting for an answer` | That session is busy. Wait, or `--force` after asking the user |
| `already running` | That conversation is open somewhere. Do not open a second copy; say where it is |
| `no conversation for that session` | Wrong id, or its transcript is gone |
| `new sessions are off` | `projects_command`, `prepare_command` and `launch_command` are missing from the config. Say so; do not edit it |
| Anything from `new` (bad branch, repo not cloned) | It comes from the launcher. Show it as is |

## The rest

- Config: `herdr-valet config` prints it; the file is `~/.config/herdr-valet/config.toml`. Never
  edit it without asking.
- The page (cards, open sessions, New session, Park all, Restore) is at
  `http://127.0.0.1:<port>`, port from the config.
- `herdr-valet <command> --help` documents each command's flags.
- Answer in the user's language.
