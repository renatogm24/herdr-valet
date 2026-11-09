---
name: restore
description: Reopen the newest batch of parked sessions with `herdr-valet restore`, each in its project's workspace in herdr, in the order they were. The batch is the last park-all, or what a reboot cut off. Use after a reboot, when the user asks to "bring everything back", restore, reopen the sessions, "restaurá", "volvé todo como estaba", or runs /valet:restore.
---

# Restore the last batch

```bash
herdr-valet restore
```

- **Output:** one line per session, `resumed` or the error. Each comes back with its whole
  conversation in a tab of its project's workspace, created if missing.
- **Errors:** sessions that fail stay parked: show the error as is. `already running` means it is
  open elsewhere already; nothing to do.
- **`nothing to restore`:** there is no batch. Loose parked sessions are resumed one at a time
  with `herdr-valet resume <session_id>` (list them with `herdr-valet list`), or from the page.
- **`herdr is not running`:** herdr has to be opened first.

End with one line: how many came back, and in which workspaces.
