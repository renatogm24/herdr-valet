---
name: new
description: Start a new Claude Code session in a project, in a herdr tab, with `herdr-valet new <id>[@<branch>]`. It opens that branch's worktree (creating it if needed), or a dated scratch folder with `adhoc:[name]`, with an optional model and first message. Use when the user asks to "open a new session in <project>", "start Claude in <project>@<branch> to …", "abrime una sesión nueva en …", "lanzá Claude en …", or runs /valet:new. To reopen an old session, use /valet:find.
---

# New session in a project

`/valet:new <id>[@<branch>] [goal]`, e.g. `/valet:new exp-track@fix-tz fix the log timezone`.

```bash
herdr-valet new <id>[@<branch>] [--as <profile>] [--model <model>] [--prompt "<goal>"]
```

- **`<id>`** is the project's id in the launcher's registry, not the folder name. When the user
  gave a rough name or none, `herdr-valet new nope` fails and lists the valid ids. Pick the
  right one, and ask if two could fit.
- **`@<branch>`:**
  - With a branch, it opens that branch's worktree, or creates it (from the local branch, from
    origin, or as a new branch).
  - Without one, it opens the most recent worktree; for a `direct` project, its clone.
  - A `direct` project takes no `@<branch>`.
- **`adhoc:[name]`** instead of an id: a new dated scratch folder, no git.
- **`--as <profile>`:** required when the launcher takes a profile (`launch_command` with
  `{profile}`; the error says "pick a profile"). The profiles are in `herdr-valet config`
  (`profiles`). Use the one the user named; otherwise ask, never guess: a profile can be an
  account (work vs personal).
- **`--prompt`:** the goal, in the user's words. Without one, the session starts and waits.
- **`--model`:** only when the user asked (`opus`, `opusplan`, `sonnet`, `haiku`). Without it,
  Claude's default.
- **Where it opens:** in the herdr workspace that already holds that repository, or in a new one
  named after the project. This session is not touched.

End with one line: project, branch or folder, and whether the worktree is new (`created` in the
JSON).

**Errors:**
- **`new sessions are off`:** the launcher commands are missing from the config. Say so, and do
  not edit it.
- **`herdr is not running`:** there is nowhere to open it.
- **Anything else** (bad branch, repo not cloned) comes from the launcher: show it as is.
