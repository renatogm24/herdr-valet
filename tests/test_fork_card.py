"""Fork and "Other branch…" on a parked card: the fork runs fork_command with the model the session
asked for, the context file is the one Start fresh writes, and in both the card stays parked.
herdr is stubbed.

    python3 -m unittest discover -s tests
"""

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ["XDG_DATA_HOME"] = str(TMP)
os.environ["HERDR_VALET_CONFIG"] = str(TMP / "missing.toml")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
valet = importlib.import_module("valet")

CLAUDE = TMP / "claude"
CWD = TMP / "repo"
CWD.mkdir()
SID = "11111111-2222-3333-4444-555555555555"


class ForkCard(unittest.TestCase):
    def setUp(self):
        self.saved = (list(valet.CONFIG_DIRS), valet.herdr_running, valet.open_in_herdr, dict(valet.CONF))
        valet.CONFIG_DIRS[:] = [CLAUDE]
        proj = CLAUDE / "projects" / "-repo"
        proj.mkdir(parents=True, exist_ok=True)
        (proj / f"{SID}.jsonl").write_text("\n".join(json.dumps(x) for x in [
            {"type": "user", "cwd": str(CWD), "timestamp": "2026-11-01T10:00:00Z", "message": {"content": "fix the tz"}},
            {"type": "assistant", "requestedModel": "claude-opus-5-5[1m]", "timestamp": "2026-11-01T10:01:00Z",
             "message": {"model": "claude-opus-5-5", "content": [{"type": "text", "text": "done, test missing"}]}},
        ]) + "\n")
        valet.DATA.mkdir(parents=True, exist_ok=True)
        valet.card_path(SID).write_text(json.dumps({
            "session_id": SID, "label": "repo/fix-tz", "cwd": str(CWD), "branch": "fix-tz", "model": "claude-opus-5-5",
            "summary": "Title: Fix tz\\nWhere we left off: done\\nNext step: test", "reason": "manual",
            "parked_at": "2026-11-02T10:00:00+00:00"}))
        self.opened = []
        valet.herdr_running = lambda: True
        valet.open_in_herdr = lambda c, cmd: (self.opened.append((c["label"], cmd)), "w9")[1]
        valet.CONF["fork_command"] = "code fork {session_id} --model {model}"

    def tearDown(self):
        valet.CONFIG_DIRS[:], valet.herdr_running, valet.open_in_herdr, conf = self.saved
        valet.CONF.clear()
        valet.CONF.update(conf)

    def test_fork_runs_fork_command_and_keeps_the_card(self):
        r = valet.fork_card(SID)
        self.assertEqual(r, {"workspace": "w9"})
        self.assertEqual(self.opened, [("repo/fix-tz", f"code fork {SID} --model 'claude-opus-5-5[1m]'")])
        self.assertTrue(valet.card_path(SID).exists())

    def test_fork_with_herdr_down_gives_the_command(self):
        valet.herdr_running = lambda: False
        with self.assertRaises(valet.HerdrDown) as e:
            valet.fork_card(SID)
        self.assertIn(f"code fork {SID}", str(e.exception))

    def test_context_for_new_keeps_the_card(self):
        r = valet.context_for_new(SID)
        self.assertTrue(Path(r["context"]).is_file())
        self.assertEqual(r["context"], str(valet.FRESH / f"{SID}.md"))
        self.assertIn(r["context"], r["prompt"])
        self.assertEqual(r["cwd"], str(CWD))
        self.assertTrue(valet.card_path(SID).exists())
        self.assertEqual(self.opened, [])

    def test_no_card(self):
        with self.assertRaises(FileNotFoundError):
            valet.fork_card("00000000-0000-0000-0000-000000000000")


class Reopen(unittest.TestCase):
    """A session without a card (from the chat): resume_command or fork_command in its repo's tab."""
    SID2 = "99999999-2222-3333-4444-555555555555"

    def setUp(self):
        self.saved = (list(valet.CONFIG_DIRS), valet.herdr_running, valet.open_tab_in_repo, valet.session_owners,
                      valet.transcript_index, dict(valet.CONF))
        valet.CONFIG_DIRS[:] = [CLAUDE]
        proj = CLAUDE / "projects" / "-repo"
        proj.mkdir(parents=True, exist_ok=True)
        (proj / f"{self.SID2}.jsonl").write_text("\n".join(json.dumps(x) for x in [
            {"type": "user", "cwd": str(CWD), "gitBranch": "feat/x", "timestamp": "2026-11-01T10:00:00Z", "message": {"content": "hola"}},
            {"type": "assistant", "requestedModel": "sonnet", "timestamp": "2026-11-01T10:01:00Z",
             "message": {"model": "claude-sonnet-5-5", "content": [{"type": "text", "text": "ok"}]}},
        ]) + "\n")
        self.opened = []
        valet.herdr_running = lambda: True
        valet.session_owners = lambda sid: []
        valet.transcript_index = lambda: {}
        valet.open_tab_in_repo = lambda path, tab, ws, cmd: (self.opened.append((path, tab, ws, cmd)), ("w5", "w5:p1"))[1]
        valet.CONF.update(resume_command="code resume {session_id}", fork_command="code fork {session_id} --model {model}")

    def tearDown(self):
        (valet.CONFIG_DIRS[:], valet.herdr_running, valet.open_tab_in_repo, valet.session_owners,
         valet.transcript_index, conf) = self.saved
        valet.CONF.clear()
        valet.CONF.update(conf)

    def test_resume_and_fork(self):
        self.assertEqual(valet.reopen(self.SID2), {"workspace": "w5", "pane": "w5:p1"})
        self.assertEqual(self.opened[-1], (str(CWD), "feat/x", "repo", f"code resume {self.SID2}"))
        valet.reopen(self.SID2, fork=True)
        self.assertEqual(self.opened[-1], (str(CWD), "feat/x fork", "repo", f"code fork {self.SID2} --model sonnet"))

    def test_running_session_is_not_resumed_twice(self):
        valet.session_owners = lambda sid: [123]
        with self.assertRaisesRegex(ValueError, "already running"):
            valet.reopen(self.SID2)
        valet.reopen(self.SID2, fork=True)  # a copy is fine
        self.assertEqual(len(self.opened), 1)

    def test_herdr_down_gives_the_command(self):
        valet.herdr_running = lambda: False
        with self.assertRaises(valet.HerdrDown) as e:
            valet.reopen(self.SID2)
        self.assertIn(f"code resume {self.SID2}", str(e.exception))

    def test_unknown_session(self):
        with self.assertRaisesRegex(ValueError, "no conversation"):
            valet.reopen("00000000-0000-0000-0000-000000000009")


if __name__ == "__main__":
    unittest.main()
