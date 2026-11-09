---
name: restart
description: Restart this Claude Code session in the same herdr tab with `herdr-valet restart`. Claude closes and the same conversation reopens, to load a Claude Code update, new or changed MCP servers, plugins or skills. Use when the user asks to restart, reload MCPs or plugins, "reiniciá", or runs /valet:restart. Never on your own initiative: when a restart is needed (an MCP was installed), suggest it and wait for a yes.
---

# Restart this session

Say in one line that the session restarts and comes back by itself in this tab. Then:

```bash
herdr-valet restart
```

It works on `$HERDR_PANE_ID` and carries on in the background. The same conversation (same id,
same history) comes back in the same tab, with the update, MCPs and plugins loaded. Nothing else
to do after it. If it fails, the session stays open: show the error as is.

**Another session:** `herdr-valet restart <pane_id>` (ids from `herdr-valet live`). It refuses
while that session is working or waiting for an answer; `--force` restarts it anyway, so ask
first.

**Without herdr:** tell the user to `/exit` and come back with `claude --continue` in the same
folder.
