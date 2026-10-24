# herdr-valet

Parks the [Claude Code](https://claude.com/claude-code) sessions that have sat idle for days in
[herdr](https://herdr.dev), and hands them back with a summary of where you left off.

An idle session does nothing, but Claude plus its MCP servers weighs 0.5 to 1.2 GB. People keep
sessions open so they don't forget what they were doing, and with 30 open, swap fills up.
herdr-valet:

1. **Parks:** Haiku writes a card (title, where we left off, what is still pending, next step)
   with the directory, branch and model. Only then is the pane closed.
2. **Parks automatically:** every 10 min, whatever has been idle for more than `idle_days` (3).
   Never a session that is working, waiting for an answer or focused. When Claude Code moves a
   running conversation to a new session id (`continued-in` in the old transcript), idle time,
   the card and the resume follow the new one.
3. **Survives a reboot:** it keeps a snapshot of what is open. If the machine reboots, every
   session that did not come back gets its card ("cut off by a reboot").
   A session closed by hand (pane closed, Claude exited) gets one too, kept for
   `closed_keep_days` (7); empty sessions, `/clear` and `/resume` don't.
4. **Web page** (`127.0.0.1:8790`): parked sessions with their summary and a **Resume in herdr**
   button, open sessions with **Park**, and recently resumed ones. Works from a phone. The map
   shows the cards active in the last 7 days (3, 30 or all from the selector; search looks
   through all of them).
5. **Watches open sessions:** context in use, compactions and estimated cost (subagents
   included), with an alert when one is worth continuing in a fresh session (context past
   `alert_context_tokens`, or `alert_context_window_pct` of its window if less, compacted `alert_compactions` times, or a cold cache whose next message
   costs more than `alert_cold_usd`) and a **Relaunch** button next to it (see below), and a **Recap** of what each one is doing without
   closing it (parking right after reuses it). It also shows the **prompt cache**: how long it
   stays warm (Claude Code keeps it 1 h on a subscription, 5 min on an API key, counted from the
   last reply, which the transcript's cache writes tell), and once it is cold, what the next
   message costs to write the whole context again (`cold ≈ $…`, at list prices).
6. **Profiles (optional):** if you launch Claude in more than one way (two accounts, a proxy, a
   wrapper), each session shows which one it runs with, and can be resumed, or switched while
   open, with another.
7. **Continues a long session in a fresh one:** `valet.py continue handoff.md`, run from inside
   the session (a skill or command of yours writes the handoff first), opens a tab next to it
   where Claude starts on that file with the same model, waits until it is up, and only then
   parks the old one. The two cards point at each other (`continued_in` / `continued_from`).
8. **Restarts and forks an open session:** `restart` closes Claude and reopens the same
   conversation in the same tab, so a Claude Code update, MCP servers or plugins load. `fork`
   opens a copy of the conversation in a new tab next to it (`--fork-session`: same history, new
   session id) to ask something else there; the original goes on untouched. Both default to the
   pane they run in, so a skill or command inside the session can call them.
9. **Parks everything before a reboot, and brings it back:** `park-all` writes every open
   session's card in parallel and only then closes them, as one batch; `restore` reopens the
   newest batch, each session in its project's workspace, in the order they sat in herdr's
   sidebar. A reboot nobody prepared for leaves a batch too (the snapshot's), so `restore` also
   brings back what it cut off. Both are buttons on the page as well.
10. **Syncs to a webhook (optional):** with `sync_url` set, every 10 min it POSTs what is new
   since the last run: each conversation entry (user and assistant text, by `uuid`), cards and
   recaps. No LLM on the machine; whoever receives it summarizes. Sessions in a herdr tab named
   `knowledge-…` send everything, tool calls and results included. Secrets are masked first.
11. **Feeds Jira and GitHub (optional):** right after sync, `feed` sends what changed in *your*
   Jira issues (assigned, reported or watched: state, changes, comments) and GitHub PRs (yours and
   the reviews asked of you: state, your reviews and comments, mentions) to the same webhook.
   Read-only on both sides; Jira through a read-only API token, GitHub through `gh`.

**Park + handoff**: an open session's Park becomes this while its cache is warm and it is past
`park_handoff_tokens` (50k); it needs the hook. It types `park handoff:` into the session: Claude
writes a handoff, decisions and their why included, and parks it. Start fresh on that card begins
from the handoff. The plain Park waits in ⋯ ("Park without handoff"), for work that is done.

**Start fresh** (`valet.py fresh <session_id>`, or the button on a card) starts a parked session
over without its history, so none of it is written to the cache again: a new Claude in the card's
directory, with its model, whose first message points at a context file in
`data_dir/fresh/<session_id>.md`. valet writes it from the transcript, with no LLM: the card,
Claude Code's own summary from the last compaction (it covers the whole session; the card only
its end), every message you typed (the first and the latest that fit), the files it wrote, the PRs,
issues and artifacts it published, the repo as it is now (branch, uncommitted changes, commits
since the session started) and the transcript's path, to look a detail up. Secrets are masked.
`--print` shows the file without starting anything.

**Relaunch** moves an open session's work to a new one that starts from the essentials instead of
the whole conversation. Moving on to other work inside a long session re-reads all of the old work
with every message, warm cache or cold; relaunching is how you stop that. Two ways:

- **handoff + continue:** Claude writes a handoff in the old session (goal, decisions and their
  why, what was ruled out, open items, the transcript's path), then runs `continue`. One message:
  cheap while the prompt cache is warm, the whole context written again once it is cold.
- **fresh:** the old session parks and starts fresh from its card (the context file above). No LLM,
  $0; some of the why is lost.

The recommendation is a handoff while the cache is warm and fresh once it is cold; the page's
Relaunch panel shows both with what each costs now, plus a box for the new session's first message.
From inside a session, type `relaunch:` (the recommended way), `relaunch fresh:` or
`relaunch handoff:`, followed by what the new session should do. That takes the **hook**: a
`UserPromptSubmit` hook in Claude Code's settings (`~/.claude/settings.json`):

```json
{"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "herdr-valet hook"}]}]}}
```

Besides `relaunch:`, the hook stops a message once when the session is past
`relaunch_context_tokens` (200k, or `relaunch_context_window_pct` of its window if less: 120k on a
200k window) and the message looks like new work: words that start something
("comencemos", "siguiente historia", "let's start", "next story", "today's report"…) or a story,
ticket or finding id the session never mentioned (`PLATAPI-1234`, `F-016`, `AVIT…`; ids in pasted
text don't count). It shows the plan; send the same message again to stay (that id won't stop a
message again). It never calls a model, takes about 0.1 s and lets every message through if
anything goes wrong. Only inside herdr. Without the hook, the page offers fresh only.

Resume runs `claude --resume <id>` in a new tab of the project's workspace if one is open, or in
a new workspace otherwise: the whole conversation comes back; the card is just the index.

## Requirements

- herdr with the Claude integration (`herdr integration status` shows `claude: current`): that
  is where each pane's session id comes from. Developed against herdr 0.9.3 (tabs).
- Claude Code (`claude` on PATH).
- Python 3.9 or newer, standard library only. Linux (systemd) or macOS (launchd).

## Install

```sh
git clone https://github.com/renatogm24/herdr-valet ~/herdr-valet
~/herdr-valet/install.sh
```

Re-run `install.sh` after a `git pull`. `install.sh --uninstall` removes the services and the
command; cards and config stay.

## Use

- Page: `http://127.0.0.1:8790` (the port is `8790 + (uid - 1000)`; on macOS, 8790).
- CLI: `herdr-valet live`, `list`, `park <pane_id>`, `resume <session_id> [--as PROFILE]`,
  `switch <pane_id> --as PROFILE`, `restart [pane_id]`, `fork [pane_id]`,
  `relaunch [pane_id] [--mode fresh|handoff] [--prompt TEXT]`, `hook`,
  `park-all [--dry-run]`, `restore`, `recap <pane_id>`, `stats <session_id>`,
  `auto --dry-run` (what it would park), `sync [--dry-run]`, `feed [--dry-run]`, `config`.

## Configuration

`~/.config/herdr-valet/config.toml`, see [`config.example.toml`](config.example.toml). The most
useful key is `resume_command`: if you launch Claude through a wrapper (MCP secrets, flags,
another account), put it there so the session comes back the way it was opened; `restart` uses
it too. `fork_command` is its twin for forks, and must pass `--fork-session` on to `claude` (if it
doesn't, `fork` notices the copy came back as the same session and says so).
`summary_command` does the same for summaries: if a session belonged to a work account, its
summary should not go out through your personal one.

`profile_command` prints which profile a session runs with and `profiles` lists the ones to
offer; `resume_command` gets the chosen one as `{profile}`. Costs are estimates at Anthropic list
prices: through a proxy or a cloud provider the bill can differ, and on a subscription they are
what the session would have cost.

## Security

The page listens only on `127.0.0.1`, actions require a header that a form on another site
cannot send, and it only answers requests with a loopback `Host` (which stops DNS rebinding).
To reach it from another device, put a proxy **with authentication** in front that passes
`Host: 127.0.0.1:<port>` to the backend (nginx's default with
`proxy_pass http://127.0.0.1:<port>/`): the page can resume and close sessions on your machine.

The summary runs with no tools (`--tools ""`): the transcript is untrusted input.

`sync` sends conversation text off the machine: point `sync_url` only at a receiver you
control, over a network you trust (or TLS). Masking covers common token formats (Anthropic,
GitHub, Slack, AWS, Atlassian, JWTs, `KEY=value`, credentials in URLs, long hex/base64), not
everything: treat it as a second line, not the only one. The Bearer token lives in its own file
(`sync_token_file`, chmod 600), not in the config. Payload, per event: `source`, `source_id`
(`<session_id>/<uuid>`), `kind` (`session`, `session_knowledge`, `card`, `recap`), `ts`, `ref`
(the session id), `role`, `text`, `title`, `meta` (cwd, branch, tab, label). Answer 200 to
advance; a 400 is logged and skipped; anything else is retried on the next run.

`feed` uses the same webhook and token, with `agent: "feed"`. Jira events (`kind: jira`, `ref` = the issue
key) and GitHub events (`kind: github`, `ref` = `owner/repo#n`) carry `meta.event`: `state` (an issue's
summary, status, status category, whether it is assigned to you) and `pr_state` (a PR's state, draft,
approved, whether you are its author or a requested reviewer) for keeping a to-do list in step; `change`,
`comment`, `activity` and `notification` as one-line happenings. `meta.url` links back. The Jira token
should be read-only (`read:jira-work`, `read:jira-user`); with `feed_jira_token_expires` set, three days
before it expires (or on a 401) feed sends a `note` asking to renew it. Tests: `python3 -m unittest discover -s tests`.

## Limitations

- Claude Code only. herdr already tells which agent runs in each pane; adding Codex or another
  agent is an adapter (where the transcript lives, how to resume).
- Parking ends the process: background tasks, running subagents and MCP server state do not
  come back.

## License

MIT
