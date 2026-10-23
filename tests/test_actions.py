"""park-all and restore: which sessions go, in what order, and what stays open. herdr, the
summaries and resuming are stubbed.

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


def live(sid, pane, ws, tab, status="idle"):
    return {"session_id": sid, "pane_id": pane, "workspace_id": f"w{ws}", "label": "proj", "tab": f"t{tab}",
            "workspace_panes": 2, "workspace_number": ws, "tab_number": tab, "cwd": "/x", "status": status}


def card(sid, batch, position, reason="park-all"):
    valet.DATA.mkdir(parents=True, exist_ok=True)
    valet.card_path(sid).write_text(json.dumps({"session_id": sid, "label": f"proj/{sid}", "batch": batch,
                                                "position": position, "reason": reason, "parked_at": batch}))


class Actions(unittest.TestCase):
    def setUp(self):
        for p in valet.DATA.glob("*.json"):
            p.unlink()
        self.closed, self.resumed = [], []
        valet.herdr_running = lambda: True
        valet.close_pane = lambda s: self.closed.append(s["pane_id"])
        valet.kill_strays = lambda sid: []
        valet.resume_in_herdr = lambda sid, profile=None: self.resumed.append(sid) or "w1"
        valet.write_card = lambda sid, label, cwd, reason, extra=None: {"session_id": sid, **(extra or {})}
        os.environ.pop("HERDR_PANE_ID", None)

    def test_park_all_refuses_while_a_session_works_but_not_for_its_own_pane(self):
        valet.live_sessions = lambda: [live("a", "w1:p1", 1, 1), live("b", "w1:p2", 1, 2, "working")]
        with self.assertRaisesRegex(ValueError, "still busy"):
            valet.park_all()
        os.environ["HERDR_PANE_ID"] = "w1:p2"
        self.assertEqual(len(valet.park_all()["sessions"]), 2)
        # The pane running park-all closes last: closing it ends the process.
        self.assertEqual(self.closed, ["w1:p1", "w1:p2"])

    def test_a_session_without_its_card_stays_open(self):
        valet.live_sessions = lambda: [live("a", "w1:p1", 1, 1), live("b", "w1:p2", 1, 2)]

        def fail_b(sid, label, cwd, reason, extra=None):
            if sid == "b":
                raise RuntimeError("summary failed")
            return {}
        valet.write_card = fail_b
        r = valet.park_all()
        self.assertEqual([x["session_id"] for x in r["failed"]], ["b"])
        self.assertEqual(self.closed, ["w1:p1"])

    def test_restore_takes_the_newest_batch_in_sidebar_order(self):
        card("old", "2026-10-20T10:00:00+00:00", [1, 1])
        card("c", "2026-10-23T10:00:00+00:00", [2, 1], "reboot")
        card("a", "2026-10-23T10:00:00+00:00", [1, 2], "reboot")
        card("b", "2026-10-23T10:00:00+00:00", None, "reboot")
        card("z", "2026-10-23T10:00:00+00:00", [1, 1], "reboot")
        r = valet.restore()
        self.assertEqual(r["batch"], "2026-10-23T10:00:00+00:00")
        self.assertEqual(self.resumed, ["z", "a", "c", "b"])

    def test_restore_without_a_batch(self):
        with self.assertRaisesRegex(ValueError, "nothing to restore"):
            valet.restore()


if __name__ == "__main__":
    unittest.main()
