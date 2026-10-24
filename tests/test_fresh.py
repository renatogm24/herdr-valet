"""The prompt cache in stats, and the context file a fresh session starts from. Synthetic transcripts.

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

PROJ = Path(TMP) / "claude" / "projects" / "-home-x-proj"


def transcript(sid, *records):
    PROJ.mkdir(parents=True, exist_ok=True)
    p = PROJ / f"{sid}.jsonl"
    p.write_text("\n".join(json.dumps({"sessionId": sid, **r}) for r in records) + "\n")
    return p


def reply(ts, uid, *, read=0, w1h=0, w5m=0, model="claude-opus-5-5", content="ok"):
    usage = {"input_tokens": 10, "output_tokens": 50, "cache_read_input_tokens": read,
             "cache_creation_input_tokens": w1h + w5m,
             "cache_creation": {"ephemeral_1h_input_tokens": w1h, "ephemeral_5m_input_tokens": w5m}}
    return {"type": "assistant", "timestamp": ts, "uuid": uid,
            "message": {"id": uid, "model": model, "usage": usage, "content": content}}


def user(text, **kw):
    return {"type": "user", "timestamp": "2026-10-20T10:00:00Z", "message": {"content": text}, **kw}


def tool_use(tid, name, inp):
    return {"type": "assistant", "timestamp": "2026-10-20T10:01:00Z",
            "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def tool_result(tid, text):
    return {"type": "user", "timestamp": "2026-10-20T10:01:01Z",
            "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": text}]}}


class Cache(unittest.TestCase):
    def test_ttl_expiry_and_cost_from_the_last_reply(self):
        p = transcript("c1", reply("2026-10-20T10:00:00Z", "a", w1h=100_000),
                       reply("2026-10-20T11:30:00Z", "b", read=100_000, w1h=990))
        c = valet.stats(p)["cache"]
        self.assertEqual(c["ttl"], "1h")
        self.assertEqual(c["expires_at"], "2026-10-20T12:30:00+00:00")
        # 101,000 tokens of context: cold writes them at 2x input ($4/MTok), warm reads at $0.20.
        self.assertEqual(c["cold_usd"], 0.81)
        self.assertEqual(c["warm_usd"], 0.02)

    def test_a_reply_that_only_read_keeps_the_last_lifetime_seen(self):
        p = transcript("c2", reply("2026-10-20T10:00:00Z", "a", w5m=50_000),
                       reply("2026-10-20T10:03:00Z", "b", read=50_000))
        c = valet.stats(p)["cache"]
        self.assertEqual((c["ttl"], c["expires_at"]), ("5m", "2026-10-20T10:08:00+00:00"))

    def test_no_cache_before_a_write(self):
        self.assertIsNone(valet.stats(transcript("c3", user("hola")))["cache"])

    def test_alerts_are_reasons_to_start_fresh_not_money_spent(self):
        # 310,000 tokens, last reply days ago: past the context limit (300k), and the cold cache
        # costs 310k x $4 x 2 = $2.48 to write again (alert_cold_usd is 2.0).
        p = transcript("c5", reply("2026-10-20T10:00:00Z", "a", w1h=1000), reply("2026-10-20T10:05:00Z", "b", read=308_990, w1h=1000))
        alerts = valet.stats(p)["alerts"]
        self.assertEqual(alerts, ["310k tokens of context", "cache cold: the next message re-sends it all (≈ $2.48)"])

    def test_under_the_limit_a_cold_cache_alone_alerts(self):
        # 260,000 tokens: under 300k, but coming back cold costs $2.08.
        p = transcript("c7", reply("2026-10-20T10:00:00Z", "a", w1h=1000), reply("2026-10-20T10:05:00Z", "b", read=258_990, w1h=1000))
        self.assertEqual(valet.stats(p)["alerts"], ["cache cold: the next message re-sends it all (≈ $2.08)"])

    def test_a_warm_cache_raises_no_cold_alert(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        p = transcript("c6", reply(now, "a", read=499_990, w1h=0), reply(now, "b", read=499_990, w1h=10))
        self.assertEqual(valet.stats(p)["alerts"], ["500k tokens of context"])

    def test_an_unpriced_model_has_no_cost(self):
        p = transcript("c4", reply("2026-10-20T10:00:00Z", "a", w1h=1000, model="claude-future-9"))
        c = valet.stats(p)["cache"]
        self.assertEqual(c["ttl"], "1h")
        self.assertIsNone(c["cold_usd"])


class Digest(unittest.TestCase):
    def test_what_it_keeps(self):
        p = transcript(
            "d1",
            user("arma la guía"),
            user("<system-reminder>ruido</system-reminder>"),
            user("contexto oculto", isMeta=True),
            tool_use("t1", "Write", {"file_path": "/x/a.html"}),
            tool_use("t2", "Edit", {"file_path": "/x/b.py"}),
            tool_use("t3", "Edit", {"file_path": "/x/a.html"}),
            tool_use("t4", "Artifact", {"action": "quickstart"}),
            tool_result("t4", "examples: https://claude.ai/artifact/Example1 https://claude.ai/artifact/Example2"),
            tool_use("t5", "Artifact", {"file_path": "/x/a.html"}),
            tool_result("t5", "Published /x/a.html at https://claude.ai/artifact/Mine1 (see https://claude.ai/artifact/Other)"),
            tool_use("t6", "Bash", {"command": "gh pr create --title x"}),
            tool_result("t6", "https://github.com/o/r/pull/7"),
            tool_use("t7", "Bash", {"command": "gh pr view 3"}),
            tool_result("t7", "https://github.com/o/r/pull/3"),
            {**user("This session is being continued… resumen A"), "isCompactSummary": True},
            {**user("resumen B"), "isCompactSummary": True},
            {**user("lo de un subagente"), "isSidechain": True},
            user("ahora sin scroll"),
        )
        d = valet.digest(p)
        self.assertEqual(d["asked"], ["arma la guía", "ahora sin scroll"])
        self.assertEqual(d["files"], ["/x/b.py", "/x/a.html"])
        self.assertEqual(d["published"], ["https://claude.ai/artifact/Mine1", "https://github.com/o/r/pull/7"])
        self.assertEqual(d["compact"], "resumen B")
        self.assertEqual(d["started"], "2026-10-20T10:00:00Z")

    def test_asked_keeps_the_first_and_the_latest_that_fit(self):
        valet_each, valet_total = valet.ASKED_EACH, valet.ASKED_TOTAL
        valet.ASKED_EACH, valet.ASKED_TOTAL = 10, 30
        try:
            lines = valet._asked_lines(["primero", "dos", "tres", "cuatro", "x" * 30])
        finally:
            valet.ASKED_EACH, valet.ASKED_TOTAL = valet_each, valet_total
        self.assertEqual(lines, ["1. primero", "(… 2 messages left out, in the transcript)", "4. cuatro", "5. xxxxxxxxxx […]"])

    def test_context_file_without_a_repo(self):
        p = transcript("d2", user("hola"), reply("2026-10-20T10:00:00Z", "a", w1h=10))
        card = {"session_id": "d2", "label": "proj", "cwd": TMP, "model": "claude-opus-5-5",
                "last_activity": "2026-10-20T10:00:00+00:00", "summary": "Title: Algo\nNext step: seguir"}
        text = valet.fresh_context(card, p)
        self.assertTrue(text.startswith("# Picking up: Algo\n"))
        self.assertIn(str(p), text)
        self.assertIn("1. hola", text)
        self.assertNotIn("## The repo now", text)

    def test_context_file_starts_from_the_handoff_left_on_park(self):
        p = transcript("d4", user("hola"), reply("2026-10-20T10:00:00Z", "a", w1h=10))
        h = Path(TMP) / "d4-handoff.md"
        h.write_text("# Handoff: X\n\n## Decisions\n- A because B\n")
        card = {"session_id": "d4", "label": "proj", "cwd": TMP, "summary": "Title: Algo", "handoff": str(h)}
        text = valet.fresh_context(card, p)
        self.assertIn(f"## The handoff it wrote before parking ({h})", text)
        self.assertIn("- A because B", text)
        # A card that continued elsewhere: its handoff went to that session already.
        self.assertNotIn("A because B", valet.fresh_context({**card, "continued_in": "d5"}, p))

    def test_continue_command_gets_the_old_sessions_id_and_profile(self):
        transcript("d3", user("hola"), reply("2026-10-20T10:00:00Z", "a", w1h=10))
        card = {"session_id": "d3", "label": "proj", "cwd": TMP, "model": "claude-opus-5-5",
                "profile": "gd", "summary": "Title: Algo"}
        valet.card_path("d3").parent.mkdir(parents=True, exist_ok=True)
        valet.card_path("d3").write_text(json.dumps(card))
        ran = []
        saved = valet.CONF["continue_command"], valet.herdr_running, valet.open_in_herdr, valet.mark_resumed, valet.CONFIG_DIRS
        valet.CONFIG_DIRS = [PROJ.parent.parent]
        valet.CONF["continue_command"] = "launch --new --as {profile} --model {model} {session_id} {prompt}"
        valet.herdr_running = lambda: True
        valet.open_in_herdr = lambda c, cmd: ran.append(cmd) or "w1"
        valet.mark_resumed = lambda *a, **k: None
        try:
            valet.start_fresh("d3")
        finally:
            valet.CONF["continue_command"], valet.herdr_running, valet.open_in_herdr, valet.mark_resumed, valet.CONFIG_DIRS = saved
        self.assertTrue(ran[0].startswith("launch --new --as gd --model claude-opus-5-5 d3 "), ran[0])


if __name__ == "__main__":
    unittest.main()
