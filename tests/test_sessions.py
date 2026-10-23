"""current_session: Claude Code moves a running conversation to a new session id ("continued-in")
while sessions/<pid>.json keeps the old one. Synthetic transcripts.

    python3 -m unittest discover -s tests
"""

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = TMP
os.environ["HERDR_VALET_CONFIG"] = str(Path(TMP) / "missing.toml")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
valet = importlib.import_module("valet")

CONF = Path(TMP) / "claude"
PROJ = CONF / "projects" / "-home-x-proj"


def transcript(sid, *records):
    PROJ.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"sessionId": sid, **r}) for r in records]
    (PROJ / f"{sid}.jsonl").write_text("\n".join(lines) + "\n")


def said(kind, ts):
    return {"type": kind, "timestamp": ts, "message": {"content": "hola"}}


def moved(to, ts):
    return {"type": "continued-in", "timestamp": ts, "continuedInSessionId": to}


class CurrentSession(unittest.TestCase):
    def setUp(self):
        valet.CONFIG_DIRS = [CONF]
        for f in PROJ.glob("*.jsonl"):
            f.unlink()

    def test_follows_the_move_and_skips_targets_without_transcript(self):
        # Como el 2026-10-16: la conversación sigue en "new"; después un /resume dejó una marca
        # hacia una sesión que nunca escribió nada.
        transcript("old", said("user", "2026-10-16T01:00:00Z"), said("assistant", "2026-10-16T02:03:07Z"),
                   {"type": "attachment", "timestamp": "2026-10-16T02:03:14Z"}, moved("new", "2026-10-16T02:03:15Z"),
                   {"type": "system", "subtype": "local_command", "timestamp": "2026-10-19T06:18:20Z"},
                   moved("ghost", "2026-10-19T06:18:20Z"))
        transcript("new", said("user", "2026-10-16T01:00:00Z"), said("user", "2026-10-21T01:52:00Z"))
        self.assertEqual(valet.current_session("old"), "new")
        self.assertEqual(valet.current_session("new"), "new")
        self.assertEqual(valet.current_session("unknown"), "unknown")

    def test_conversation_after_the_mark_means_the_old_id_is_in_use(self):
        transcript("old", said("user", "2026-10-16T01:00:00Z"), moved("new", "2026-10-16T02:03:15Z"),
                   said("user", "2026-10-23T15:45:00Z"), said("assistant", "2026-10-23T15:46:00Z"))
        transcript("new", said("user", "2026-10-21T01:52:00Z"))
        self.assertEqual(valet.current_session("old"), "old")

    def test_follows_a_chain_and_stops_on_a_loop(self):
        transcript("a", said("user", "2026-10-16T01:00:00Z"), moved("b", "2026-10-16T02:00:00Z"))
        transcript("b", said("user", "2026-10-17T01:00:00Z"), moved("c", "2026-10-17T02:00:00Z"))
        transcript("c", said("user", "2026-10-18T01:00:00Z"), moved("a", "2026-10-18T02:00:00Z"))
        self.assertIn(valet.current_session("a"), {"a", "b", "c"})  # sin colgarse
        transcript("c", said("user", "2026-10-18T01:00:00Z"))
        self.assertEqual(valet.current_session("a"), "c")

    def test_owners_include_the_process_that_still_names_the_old_id(self):
        transcript("old", said("user", "2026-10-16T01:00:00Z"), moved("new", "2026-10-16T02:03:15Z"))
        transcript("new", said("user", "2026-10-21T01:52:00Z"))
        real = valet.claude_processes
        valet.claude_processes = lambda: [{"pid": 4242, "sessionId": "old"}, {"pid": 7, "sessionId": "other"}]
        try:
            self.assertEqual(valet.session_owners("new"), [4242])
            self.assertEqual(valet.session_owners("other"), [7])
        finally:
            valet.claude_processes = real


if __name__ == "__main__":
    unittest.main()
