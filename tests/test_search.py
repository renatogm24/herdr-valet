"""search: cards (parked, closed, resumed) and transcripts, by words, without an LLM; the transcript
index is cached and re-read only when a transcript changes. herdr is off.

    python3 -m unittest discover -s tests
"""

import importlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ["XDG_DATA_HOME"] = str(TMP)
os.environ["HERDR_VALET_CONFIG"] = str(TMP / "missing.toml")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
valet = importlib.import_module("valet")

CLAUDE = TMP / "claude"
PROJ = CLAUDE / "projects" / "-home-x-repo"


def transcript(sid, first, title="", cwd="/home/x/repo", branch="main", ts="2026-11-01T10:00:00Z"):
    PROJ.mkdir(parents=True, exist_ok=True)
    lines = [
        {"type": "permission-mode", "sessionId": sid},
        {"type": "user", "cwd": cwd, "gitBranch": branch, "timestamp": ts, "message": {"content": "<system-reminder>x</system-reminder>"}},
        {"type": "user", "cwd": cwd, "gitBranch": branch, "timestamp": ts, "message": {"content": first}},
        {"type": "assistant", "timestamp": ts, "message": {"content": [{"type": "text", "text": "ok"}]}},
    ]
    if title:
        lines.append({"type": "ai-title", "aiTitle": title})
    p = PROJ / f"{sid}.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    return p


def card(sid, summary, reason="manual", label="repo/main", history=False):
    d = valet.HISTORY if history else valet.DATA
    d.mkdir(parents=True, exist_ok=True)
    c = {"session_id": sid, "label": label, "cwd": "/home/x/repo", "branch": "main", "summary": summary,
         "reason": reason, "parked_at": "2026-11-02T10:00:00+00:00"}
    if history:
        c["resumed_at"] = "2026-11-03T10:00:00+00:00"
    (d / f"{sid}.json").write_text(json.dumps(c))


class Search(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = (list(valet.CONFIG_DIRS), valet.herdr_running)
        valet.CONFIG_DIRS[:] = [CLAUDE]
        valet.herdr_running = lambda: False
        transcript("t-tz", "arreglá el log de timezone del banco", title="Fix timezone en logs")
        transcript("t-other", "migrar el gateway a LiteLLM", title="Gateway LiteLLM", cwd="/home/x/gw", branch="feat/gw")
        transcript("t-parked", "algo")
        card("t-parked", "Title: Sesión de parking\nWhere we left off: el hook de relaunch quedó instalado\nNext step: probar")
        card("c-closed", "Title: Revisión de Orca\nWhere we left off: herdr se queda", reason="closed")
        card("c-resumed", "Title: Dashboard del hogar\nWhere we left off: falta el tile de red", history=True)

    @classmethod
    def tearDownClass(cls):
        valet.CONFIG_DIRS[:], valet.herdr_running = cls.saved

    def ids(self, q):
        return [r["session_id"] for r in valet.search(q, with_live=False)]

    def test_words_in_title_and_first_message(self):
        self.assertEqual(self.ids("timezone banco"), ["t-tz"])

    def test_every_word_must_match(self):
        self.assertEqual(self.ids("timezone litellm"), [])

    def test_accents_do_not_matter(self):
        self.assertEqual(self.ids("sesion parking"), ["t-parked"])
        self.assertEqual(self.ids("REVISIÓN orca"), ["c-closed"])

    def test_states_and_summary(self):
        r = {x["session_id"]: x for x in valet.search("hook relaunch", with_live=False)}
        self.assertEqual(r["t-parked"]["state"], "parked")
        self.assertEqual(r["t-parked"]["where"], "el hook de relaunch quedó instalado")
        self.assertEqual(valet.search("orca", with_live=False)[0]["state"], "closed")
        self.assertEqual(valet.search("tile red", with_live=False)[0]["state"], "resumed")

    def test_branch_and_directory(self):
        r = valet.search("feat/gw", with_live=False)
        self.assertEqual([x["session_id"] for x in r], ["t-other"])
        self.assertEqual(r[0]["cwd"], "/home/x/gw")

    def test_title_outranks_a_mention(self):
        transcript("t-mention", "de paso: el gateway", title="Otra cosa")
        try:
            self.assertEqual(self.ids("gateway")[0], "t-other")
        finally:
            (PROJ / "t-mention.jsonl").unlink()

    def test_index_is_cached_and_refreshed(self):
        valet.transcript_index()
        self.assertTrue(valet.SEARCH_INDEX.exists())
        p = transcript("t-new", "un tema nuevo: kubernetes")
        self.assertEqual(self.ids("kubernetes"), ["t-new"])
        time.sleep(0.01)
        transcript("t-new", "cambió: terraform")
        self.assertEqual(self.ids("terraform"), ["t-new"])
        self.assertEqual(self.ids("kubernetes"), [])
        p.unlink()
        self.assertNotIn("t-new", valet.transcript_index())

    def test_index_is_not_a_card(self):
        valet.transcript_index()
        self.assertNotIn(None, [c.get("session_id") for c in valet.cards()])

    def test_empty_query(self):
        self.assertEqual(valet.search("   ", with_live=False), [])


if __name__ == "__main__":
    unittest.main()
