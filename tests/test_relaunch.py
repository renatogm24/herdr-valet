"""relaunch: the plan (handoff while the cache is warm, fresh once cold), the hook that stops a message
that looks like new work in a long session, and "relaunch:" typed in the session. Synthetic
transcripts; herdr and detached processes are stubbed.

    python3 -m unittest discover -s tests
"""

import importlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = TMP
os.environ["HERDR_VALET_CONFIG"] = str(Path(TMP) / "missing.toml")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
valet = importlib.import_module("valet")

PROJ = Path(TMP) / "claude" / "projects" / "-home-x-relaunch"


def iso(minutes_ago):
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def transcript(sid, context, minutes_ago=1, said=("arreglemos el F-014",), model="claude-opus-5-5"):
    """A session at `context` tokens whose last reply was `minutes_ago` ago, on a 5 min cache."""
    PROJ.mkdir(parents=True, exist_ok=True)
    rows = [{"type": "user", "timestamp": iso(30), "message": {"content": t}} for t in said]
    usage = {"input_tokens": 10, "output_tokens": 50, "cache_read_input_tokens": context - 1010,
             "cache_creation_input_tokens": 1000,
             "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 1000}}
    rows.append({"type": "assistant", "timestamp": iso(minutes_ago), "uuid": "a1",
                 "message": {"id": "a1", "model": model, "usage": usage, "content": "ok"}})
    p = PROJ / f"{sid}.jsonl"
    p.write_text("\n".join(json.dumps({"sessionId": sid, **r}) for r in rows) + "\n")
    return p


def event(sid, prompt):
    return {"session_id": sid, "prompt": prompt, "transcript_path": str(PROJ / f"{sid}.jsonl"),
            "hook_event_name": "UserPromptSubmit"}


class Plan(unittest.TestCase):
    def test_warm_recommends_a_handoff_and_prices_it(self):
        p = valet.relaunch_plan(valet.tail_stats(transcript("p1", 400_000, minutes_ago=1)))
        self.assertEqual((p["recommended"], p["warm"], p["context_tokens"]), ("handoff", True, 400_000))
        # Reading 400k from the cache ($0.08) plus ~4k tokens written ($0.08), Opus 5.5 list prices.
        self.assertEqual(p["handoff_usd"], 0.16)

    def test_cold_recommends_fresh_and_the_handoff_shows_its_cold_price(self):
        p = valet.relaunch_plan(valet.tail_stats(transcript("p2", 400_000, minutes_ago=20)))
        self.assertEqual((p["recommended"], p["warm"]), ("fresh", False))
        # The whole context written again at 1.25x ($2.00), plus the handoff's output.
        self.assertEqual(p["handoff_usd"], 2.08)


class Hook(unittest.TestCase):
    def setUp(self):
        os.environ["HERDR_PANE_ID"] = "w1:p1"
        self.detached = []
        valet.detach = lambda argv: self.detached.append(argv)
        for f in valet.RELAUNCH.glob("*") if valet.RELAUNCH.is_dir() else []:
            f.unlink()

    def test_a_small_session_is_left_alone(self):
        transcript("h1", 50_000)
        self.assertIsNone(valet.hook(event("h1", "comencemos con el F-016")))

    def test_a_200k_window_stops_new_work_before_it_compacts(self):
        # 60% of 200k: 120k, where a 1M window still waits for 200k.
        transcript("h7", 130_000, model="claude-sonnet-4-6")
        self.assertEqual(valet.hook(event("h7", "comencemos con el F-016"))["decision"], "block")
        transcript("h8", 130_000)
        self.assertIsNone(valet.hook(event("h8", "comencemos con el F-016")))

    def test_park_handoff_asks_for_a_handoff_and_a_park(self):
        transcript("h9", 50_000)
        ctx = valet.hook(event("h9", "park handoff:"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("parking this session", ctx)
        self.assertRegex(ctx, r"valet\.py park w1:p1 --handoff \S+/handoffs/h9-")
        self.assertNotIn(" continue ", ctx)

    def test_outside_herdr_nothing_happens(self):
        transcript("h2", 400_000)
        del os.environ["HERDR_PANE_ID"]
        self.assertIsNone(valet.hook(event("h2", "comencemos con el F-016")))

    def test_new_work_is_stopped_once_and_sending_it_again_stays(self):
        transcript("h3", 400_000)
        out = valet.hook(event("h3", "ok ya está, comencemos con f-016"))
        self.assertEqual(out["decision"], "block")
        self.assertIn('"comencemos"', out["reason"])
        self.assertIn("f-016", out["reason"])
        self.assertIn("recommended handoff + continue (≈ $0.16)", out["reason"])
        self.assertIsNone(valet.hook(event("h3", "ok ya está, comencemos con f-016")))
        # Its id was let through for good, and its words for a while.
        self.assertIsNone(valet.hook(event("h3", "comencemos a revisar el f16 otra vez")))

    def test_an_id_the_session_already_worked_on_is_not_new_work(self):
        transcript("h4", 400_000, said=("arreglemos el F-014", "listo"))
        self.assertIsNone(valet.hook(event("h4", "y el F-014 ya está en prod?")))
        self.assertEqual(valet.hook(event("h4", "y el F-015?"))["decision"], "block")

    def test_english_and_pasted_text(self):
        transcript("h5", 400_000)
        self.assertEqual(valet.hook(event("h5", "great, let's start on the next story"))["decision"], "block")
        transcript("h6", 400_000)
        # Ids inside a pasted thread are not the user asking for new work.
        self.assertIsNone(valet.hook(event("h6", 'mira esto <pasted_content id="1">AVIT0079378 PLATAPI-999</pasted_content>')))
        self.assertIsNone(valet.hook(event("h6", "the build uses UTF-8 and SHA-256")))

    def test_relaunch_fresh_parks_in_the_background_with_the_request(self):
        transcript("h7", 400_000)
        out = valet.hook(event("h7", "relaunch fresh: sigamos con el F-025"))
        self.assertEqual(out["decision"], "block")
        argv = self.detached[0]
        self.assertEqual(argv[:4], ["relaunch", "w1:p1", "--mode", "fresh"])
        self.assertEqual(Path(argv[argv.index("--prompt-file") + 1]).read_text(), "sigamos con el F-025")

    def test_plain_relaunch_takes_the_stopped_message_and_the_recommended_way(self):
        transcript("h8", 400_000)
        valet.hook(event("h8", "comencemos con el F-030"))
        out = valet.hook(event("h8", "relaunch:"))
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("comencemos con el F-030", ctx)
        self.assertIn(" continue ", ctx)
        self.assertIn("--from w1:p1 --prompt-file", ctx)
        self.assertIn(str(PROJ / "h8.jsonl"), ctx)
        self.assertEqual(self.detached, [])
        # The stopped message was used up: sending it now is not "sending it again".
        self.assertNotIn("prompt", valet._relaunch_state("h8"))

    def test_relaunch_with_a_cold_cache_goes_fresh(self):
        transcript("h9", 400_000, minutes_ago=30)
        self.assertEqual(valet.hook(event("h9", "relaunch: otra cosa"))["decision"], "block")
        self.assertEqual(self.detached[0][3], "fresh")


class FirstMessage(unittest.TestCase):
    def test_short_inline_long_to_a_file(self):
        h = Path(TMP) / "handoff.md"
        self.assertEqual(valet.first_message(h, "", "continue_prompt"), valet.CONF["continue_prompt"].format(handoff=h))
        self.assertTrue(valet.first_message(h, "sigamos con F-025", "fresh_prompt").endswith("the user's request: sigamos con F-025"))
        msg = valet.first_message(h, "línea uno\nlínea dos", "fresh_prompt")
        f = Path(TMP) / "handoff.request.md"
        self.assertIn(f"it is in {f}", msg)
        self.assertEqual(f.read_text(), "línea uno\nlínea dos\n")


if __name__ == "__main__":
    unittest.main()


class RetireHandoffs(unittest.TestCase):
    """The handoff skill's active files for the checkout stop loading once a relaunch hands over."""

    def write(self, d, name, status, branch):
        (d / ".claude" / "handoffs").mkdir(parents=True, exist_ok=True)
        f = d / ".claude" / "handoffs" / name
        f.write_text(f"---\nstatus: {status}\nbranch: {branch}\nupdated: 2026-10-01T10:00\n---\n\n# H\n\n## Audit log\n- x\n")
        return f

    def test_session_directory_active_handoff_is_superseded_others_untouched(self):
        home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(setattr, valet, "HOME", valet.HOME)
        valet.HOME = home
        d = home / "2026-10-24-task"
        (d / "sub").mkdir(parents=True)
        (d / ".last-accessed").touch()
        mine = self.write(d, "a.md", "active", d.name)
        done = self.write(d, "b.md", "done", d.name)
        other = self.write(d, "c.md", "active", "another-branch")
        self.assertEqual(valet.retire_handoffs(str(d / "sub"), "/h/new.md"), [str(mine)])
        text = mine.read_text()
        self.assertIn("status: superseded", text)
        self.assertTrue(text.rstrip().endswith("superseded by a herdr-valet relaunch, handoff /h/new.md"))
        self.assertIn("status: done", done.read_text())
        self.assertIn("status: active", other.read_text())

    def test_outside_a_checkout_nothing_happens(self):
        self.assertEqual(valet.retire_handoffs(tempfile.mkdtemp(), "/h/new.md"), [])


class HandoffTemplate(unittest.TestCase):
    def instructions(self, template):
        self.addCleanup(valet.CONF.__setitem__, "handoff_template", valet.CONF["handoff_template"])
        valet.CONF["handoff_template"] = template
        return valet.handoff_instructions("t1", transcript("t1", 300_000), "w1:p1", "")

    def test_the_skill_template_when_there_is_one(self):
        tpl = Path(tempfile.mkdtemp()) / "handoff.md"
        tpl.write_text("# Handoff: <title>\n")
        text = self.instructions(str(tpl))
        self.assertIn(f"Follow the sections of the handoff template at {tpl}", text)
        self.assertNotIn("Short and specific", text)
        self.assertIn("not with the handoff skill", text)

    def test_a_short_list_without_it(self):
        self.assertIn("Short and specific", self.instructions(str(Path(TMP) / "missing.md")))
        self.assertIn("Short and specific", self.instructions(""))


class ContextLimits(unittest.TestCase):
    def test_capped_at_a_share_of_the_window(self):
        self.assertEqual(valet.context_limit("alert_context_tokens", 1_000_000), 300_000)
        self.assertEqual(valet.context_limit("alert_context_tokens", 200_000), 150_000)
        self.assertEqual(valet.context_limit("relaunch_context_tokens", 1_000_000), 200_000)
        self.assertEqual(valet.context_limit("relaunch_context_tokens", 200_000), 120_000)

    def test_a_200k_session_alerts_and_shows_its_own_limit(self):
        st = valet.stats(transcript("c1", 160_000, model="claude-sonnet-4-6"))
        self.assertEqual((st["context_window"], st["alert_context_tokens"]), (200_000, 150_000))
        self.assertIn("160k tokens of context", st["alerts"])
        self.assertEqual(valet.stats(transcript("c2", 160_000))["alerts"][:1], [])


# test_actions stubs write_card on the shared module: keep the real one.
WRITE_CARD = valet.write_card


class SummaryFromHandoff(unittest.TestCase):
    """A card parked with a handoff is summarized from the handoff, not from the transcript's tail
    (the request to write it, which Haiku took as its own task)."""

    def setUp(self):
        self.calls = []
        self._run, self._dirs = valet.subprocess.run, valet.CONFIG_DIRS
        valet.CONFIG_DIRS = [Path(TMP) / "claude"]

        def run(args, input=None, **kw):
            self.calls.append(input)
            return type("R", (), {"returncode": 0, "stdout": "Title: From the handoff\nNext step: x",
                                  "stderr": ""})()
        valet.subprocess.run = run

    def tearDown(self):
        valet.subprocess.run, valet.CONFIG_DIRS = self._run, self._dirs

    def test_the_handoff_is_what_gets_summarized(self):
        sid = "77777777-0000-0000-0000-000000000000"
        transcript(sid, 80_000, said=("park handoff:",))
        h = Path(TMP) / "h.md"
        h.write_text("# Handoff: real work\n\n## Current state\n- PR #40 open\n")
        card = WRITE_CARD(sid, "w/t", None, "manual", {"handoff": str(h)})
        self.assertEqual(valet.title(card), "From the handoff")
        prompt = next(c for c in self.calls if c and "<handoff>" in c)
        self.assertIn("PR #40 open", prompt)
        self.assertNotIn("<transcript>", prompt)

    def test_without_a_handoff_the_transcript_still_is(self):
        sid = "88888888-0000-0000-0000-000000000000"
        transcript(sid, 80_000)
        WRITE_CARD(sid, "w/t", None, "manual")
        self.assertTrue(any(c and "<transcript>" in c for c in self.calls))
