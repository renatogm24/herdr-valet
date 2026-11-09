---
name: fork
description: Open a copy of this conversation in a new herdr tab with `herdr-valet fork` (claude --resume --fork-session), to ask something else without cluttering this one. The copy has the whole history under its own session id; this session stays as it is. Use when the user asks for a fork, "open another window with this context", "ask it something on the side", "bifurcá", "abrí otra con este contexto", or runs /valet:fork.
---

# Fork into another tab

```bash
herdr-valet fork
```

- **What it opens:** a tab next to this one (same workspace, folder and model), focused. It
  prints JSON with the copy's `pane_id` and `session_id`. This session is untouched.
- **A question for the copy:** if the user already said what to ask there, send it:

  ```bash
  sleep 2 && herdr pane run "<pane_id from the JSON>" "<the question, as they said it>"
  ```

- **When done:** one line with the tab the copy is in, and whether the question went.
- **"resumed the same session instead of a copy":** the `fork_command` launcher drops
  `--fork-session`, so two processes are writing one conversation. Close that tab and tell the
  user to fix `fork_command` in `~/.config/herdr-valet/config.toml`.
- **A parked or past session:** use `herdr-valet resume <session_id> --fork` instead (see
  /valet:find).

**Without herdr:** give the command to run by hand in another terminal, in the same folder:
`cd "<cwd>" && claude --resume <session_id> --fork-session`.
