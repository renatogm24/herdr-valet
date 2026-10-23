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
   button, open sessions with **Park**, and recently resumed ones. Works from a phone.
5. **Watches open sessions:** context in use, compactions and estimated cost (subagents
   included), with alerts past a threshold, and a **Recap** of what each one is doing without
   closing it (parking right after reuses it).
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
