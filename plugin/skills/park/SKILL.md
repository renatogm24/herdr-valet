---
name: park
description: Park this Claude Code session with `herdr-valet park`. It writes a card (summary of where things stood, folder, model) and closes the pane, to be resumed later from valet's page, `herdr-valet resume` or /valet:find. Use when the user asks to park this session, to "save it and close", "leave this for later", "aparcá esto", "guardala y cerrá", or runs /valet:park. Never on your own initiative. Before a machine reboot, use park-all instead.
---

# Park this session

Say in one line that this session gets parked and closes in a few seconds. Then:

```bash
herdr-valet park
```

It works on `$HERDR_PANE_ID` and carries on in the background: Haiku writes the card (~15 s),
then the pane closes. Nothing else to do after it. If it fails, the session stays open: show the
error as is.

**Without herdr** (no `$HERDR_PANE_ID`, or no `herdr-valet` on the PATH): there is nowhere to
park. Tell the user to `/exit` and to come back later with `claude --resume <session_id>` in the
same folder.
