# herdr-valet

Parks the [Claude Code](https://claude.com/claude-code) sessions that have sat idle for days in
[herdr](https://herdr.dev), and hands them back with a summary of where you left off.

An idle session does nothing, but Claude plus its MCP servers weighs 0.5 to 1.2 GB. People keep
sessions open so they don't forget what they were doing, and with 30 open, swap fills up.
herdr-valet:

1. **Parks:** Haiku writes a card (title, where we left off, what is still pending, next step)
   with the directory, branch and model. Only then is the pane closed.
2. **Parks automatically:** every 10 min, whatever has been idle for more than `idle_days` (3).
   Never a session that is working, waiting for an answer or focused.
3. **Survives a reboot:** it keeps a snapshot of what is open. If the machine reboots, every
   session that did not come back gets its card ("cut off by a reboot").
4. **Web page** (`127.0.0.1:8790`): parked sessions with their summary and a **Resume in herdr**
   button, open sessions with **Park**, and recently resumed ones. Works from a phone.

Resume opens a herdr workspace with `claude --resume <id>`: the whole conversation comes back;
the card is just the index.

## Requirements

- herdr with the Claude integration (`herdr integration status` shows `claude: current`): that
  is where each pane's session id comes from. Developed against herdr 0.7.1.
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
- CLI: `herdr-valet live`, `list`, `park <pane_id>`, `resume <session_id>`,
  `auto --dry-run` (what it would park), `config`.

## Configuration

`~/.config/herdr-valet/config.toml`, see [`config.example.toml`](config.example.toml). The most
useful key is `resume_command`: if you launch Claude through a wrapper (MCP secrets, flags,
another account), put it there so the session comes back the way it was opened.
`summary_command` does the same for summaries: if a session belonged to a work account, its
summary should not go out through your personal one.

## Security

The page listens only on `127.0.0.1`, actions require a header that a form on another site
cannot send, and it only answers requests with a loopback `Host` (which stops DNS rebinding).
To reach it from another device, put a proxy **with authentication** in front that passes
`Host: 127.0.0.1:<port>` to the backend (nginx's default with
`proxy_pass http://127.0.0.1:<port>/`): the page can resume and close sessions on your machine.

The summary runs with no tools (`--tools ""`): the transcript is untrusted input.

## Limitations

- Claude Code only. herdr already tells which agent runs in each pane; adding Codex or another
  agent is an adapter (where the transcript lives, how to resume).
- Parking ends the process: background tasks, running subagents and MCP server state do not
  come back.

## License

MIT
