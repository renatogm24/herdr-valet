---
name: park-all
description: Park every Claude Code session open in herdr as one batch with `herdr-valet park-all`, before a machine reboot; /valet:restore brings them back where they were. Each session gets its card before its pane closes. Use when the user asks to park everything, "close it all, I'm rebooting", "save everything before the update", "aparcá todo", or runs /valet:park-all.
---

# Park everything

1. See what would close:

   ```bash
   herdr-valet park-all --dry-run
   ```

   "still busy: …" lists sessions that are working or waiting for an answer. Show them and ask:
   wait for them, or park anyway with `--force` (what they are doing gets cut).

2. Say in one line how many get parked and that /valet:restore (or Restore on valet's page)
   brings them back. Then:

   ```bash
   herdr-valet park-all
   ```

   It writes every card in parallel (~15–30 s) and closes only the sessions that have one, **this
   one last**: the command carries on in the background and returns at once. Nothing else to do.

Outside herdr (no `$HERDR_PANE_ID`), it waits until done and prints JSON with `sessions` and
`failed`. The ones in `failed` stayed open, without a card: list them.

A reboot nobody prepared for is covered too: valet writes cards for the sessions it cut off, and
restore brings those back as well.
