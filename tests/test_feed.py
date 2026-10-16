"""feed: Jira and GitHub to the webhook, with both faked (synthetic data, invented names).

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

ME = "acc-me"


def adf(text):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


class FakeJira:
    def __init__(self):
        self.calls = []
        self.issues = []
        self.standing = []
        self.full = {}

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path == "/rest/api/3/myself":
            return {"accountId": ME}
        if path == "/rest/api/3/search/jql":
            if "updated >=" not in body["jql"]:
                return {"issues": self.standing}
            return {"issues": self.issues, "isLast": True}
        key = path.split("/issue/")[1].split("?")[0]
        return self.full.get(key, {})


class FakeGh:
    def __init__(self):
        self.calls = []
        self.mine, self.asked, self.merged = [], [], []
        self.views = {}
        self.events, self.notifs = [], []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("search", "prs"):
            if "--review-requested" in args:
                return self.asked
            if "--merged" in args:
                return self.merged
            return self.mine
        if args[:2] == ("pr", "view"):
            return self.views[f"{args[args.index('--repo') + 1]}#{args[2]}"]
        if args[0] == "api" and args[1].startswith("users/"):
            return self.events
        if args[0] == "api" and args[1].startswith("notifications"):
            return self.notifs
        raise AssertionError(args)


def pr(repo, n, updated, title="Fix login"):
    return {"number": n, "title": title, "repository": {"nameWithOwner": repo}, "updatedAt": updated, "isDraft": False, "url": f"https://github.com/{repo}/pull/{n}", "state": "OPEN"}


def view(repo, n, updated, state="OPEN", decision="", author="rex-acme", requests=()):
    return {"number": n, "title": "Fix login", "url": f"https://github.com/{repo}/pull/{n}", "state": state, "isDraft": False, "updatedAt": updated,
            "reviewDecision": decision, "reviewRequests": [{"login": r} for r in requests], "statusCheckRollup": [{"conclusion": "SUCCESS"}], "author": {"login": author}}


class FeedTest(unittest.TestCase):
    def setUp(self):
        valet.CONF.update({
            "sync_url": "http://wb.test/ingest", "feed_jira_api": "https://jira.test", "feed_jira_site": "https://acme.atlassian.net",
            "feed_jira_email": "rex@acme.test", "feed_github_login": "rex-acme", "feed_jira_token_expires": "",
        })
        valet.SYNC_STATE.unlink(missing_ok=True)
        self.jira, self.gh, self.sent = FakeJira(), FakeGh(), []
        valet._jira, valet._gh, valet.jira_token = self.jira, self.gh, lambda: "tok"
        valet._send = lambda events, agent="valet": self.sent.append((agent, events)) or True

    def events(self):
        return [e for _, batch in self.sent for e in batch]

    def test_jira_state_changes_and_comments(self):
        self.jira.issues = [{"key": "ABC-1", "fields": {"summary": "Fix the retry", "updated": "2099-01-02T10:00:00.000-0500",
                                                        "status": {"name": "In Progress", "statusCategory": {"key": "indeterminate"}},
                                                        "issuetype": {"name": "Task"}, "assignee": {"accountId": ME}}}]
        self.jira.full["ABC-1"] = {
            "changelog": {"histories": [{"id": "9", "created": "2099-01-02T10:00:00.000-0500", "author": {"displayName": "Ana Torres"},
                                         "items": [{"field": "status", "fromString": "To Do", "toString": "In Progress"}]},
                                        {"id": "1", "created": "2000-01-01T00:00:00.000+0000", "items": [{"field": "old"}]},
                                        {"id": "10", "created": "2099-01-02T10:01:00.000-0500", "author": {"displayName": "Automation for Jira", "accountType": "app"},
                                         "items": [{"field": "Link", "toString": "relates to ABC-2"}]},
                                        {"id": "11", "created": "2099-01-02T10:02:00.000-0500", "author": {"displayName": "Ana Torres"},
                                         "items": [{"field": "status", "fromString": "Done", "toString": "Done"}]}]},
            "fields": {"comment": {"comments": [{"id": "77", "created": "2099-01-02T11:00:00.000-0500", "author": {"displayName": "Leo Paz", "accountId": "x"},
                                                 "body": adf("Can you check the logs?")}]}},
        }
        r = valet.feed()
        self.assertEqual(r["jira"], 3)
        state, change, comment = [e for e in self.events() if e["kind"] == "jira"]
        self.assertEqual(state["meta"]["event"], "state")
        self.assertEqual(state["meta"]["category"], "indeterminate")
        self.assertTrue(state["meta"]["assignee_me"])
        self.assertEqual(state["meta"]["url"], "https://acme.atlassian.net/browse/ABC-1")
        self.assertEqual(state["ts"], "2099-01-02T10:00:00.000-05:00")
        self.assertEqual(state["ref"], "ABC-1")
        self.assertEqual(change["text"], "Ana Torres: status: To Do → In Progress")
        self.assertEqual(change["meta"]["by"], "Ana Torres")
        self.assertEqual(comment["text"], "Leo Paz: Can you check the logs?")
        self.assertEqual(self.sent[0][0], "feed")
        jql = self.jira.calls[1][2]["jql"]
        # A standing assigned issue that did not change: state only, no changelog call.
        self.sent.clear()
        self.jira.issues = []
        self.jira.standing = [{"key": "ABC-7", "fields": {"summary": "Old epic", "updated": "2000-01-01T00:00:00.000+0000",
                                                          "status": {"name": "To Do", "statusCategory": {"key": "new"}},
                                                          "issuetype": {"name": "Epic"}, "assignee": {"accountId": ME}}}]
        self.jira.calls.clear()
        valet.feed()
        self.assertEqual([(e["ref"], e["meta"]["event"]) for e in self.events()], [("ABC-7", "state")])
        self.assertFalse([c for c in self.jira.calls if "/issue/" in c[1]])
        self.assertIn("assignee = currentUser() OR reporter = currentUser() OR watcher = currentUser()", jql)

    def test_github_only_what_changed_and_final_state(self):
        self.gh.mine = [pr("acme/mine", 7, "2099-01-01T10:00:00Z")]
        self.gh.asked = [pr("acme/other", 12, "2099-01-01T11:00:00Z")]
        self.gh.views = {"acme/mine#7": view("acme/mine", 7, "2099-01-01T10:00:00Z", requests=["porter"]),
                         "acme/other#12": view("acme/other", 12, "2099-01-01T11:00:00Z", author="ana")}
        self.gh.events = [{"id": "5", "type": "PullRequestReviewEvent", "created_at": "2099-01-01T12:00:00Z", "repo": {"name": "acme/x"},
                           "payload": {"review": {"state": "approved", "body": ""}, "pull_request": {"number": 3, "title": "Y", "html_url": "https://github.com/acme/x/pull/3"}}},
                          {"id": "4", "type": "PushEvent", "created_at": "2099-01-01T12:00:00Z", "repo": {"name": "acme/x"}, "payload": {}},
                          {"id": "6", "type": "PullRequestEvent", "created_at": "2099-01-01T12:00:00Z", "repo": {"name": "acme/x"},
                           "payload": {"action": "labeled", "pull_request": {"number": 3, "title": "Y"}}}]
        self.gh.notifs = [{"id": "n1", "reason": "mention", "updated_at": "2099-01-01T12:00:00Z", "repository": {"full_name": "acme/x"},
                           "subject": {"title": "Deploy plan", "url": "https://api.github.com/repos/acme/x/pulls/3"}},
                          {"id": "n2", "reason": "ci_activity", "updated_at": "2099-01-01T12:00:00Z", "repository": {"full_name": "acme/x"}, "subject": {}}]
        valet.CONF["feed_jira_api"] = ""
        valet.feed()
        ev = self.events()
        states = {e["ref"]: e["meta"] for e in ev if e["meta"].get("event") == "pr_state"}
        self.assertTrue(states["acme/mine#7"]["author_me"])
        self.assertEqual(states["acme/mine#7"]["reviewers"], "porter")
        self.assertTrue(states["acme/other#12"]["review_requested_me"])
        self.assertEqual([e["text"] for e in ev if e["meta"].get("event") == "activity"], ["review approved: acme/x#3 Y"])
        notif = [e for e in ev if e["meta"].get("event") == "notification"]
        self.assertEqual([(n["ref"], n["meta"]["url"]) for n in notif], [("acme/x#3", "https://github.com/acme/x/pull/3")])

        # Nothing changed: no `pr view`, no events.
        self.sent.clear()
        self.gh.calls.clear()
        self.gh.events, self.gh.notifs = [], []
        valet.feed()
        self.assertFalse([c for c in self.gh.calls if c[:2] == ("pr", "view")])
        self.assertEqual(self.events(), [])

        # I reviewed #12: it leaves the asked list while open → its state says so.
        self.gh.asked = []
        self.gh.views["acme/other#12"] = view("acme/other", 12, "2099-01-01T13:00:00Z", author="ana")
        valet.feed()
        last = [e for e in self.events() if e["ref"] == "acme/other#12"][-1]
        self.assertFalse(last["meta"]["review_requested_me"])

    def test_failed_send_does_not_advance(self):
        valet.CONF["feed_github_login"] = ""
        self.jira.issues = []
        valet._send = lambda events, agent="valet": False
        valet.CONF["feed_jira_token_expires"] = "2000-01-01"  # already expired → note
        r = valet.feed()
        self.assertTrue(r["failed"])
        self.assertEqual(r["notes"], 1)
        state = json.loads(valet.SYNC_STATE.read_text()) if valet.SYNC_STATE.exists() else {}
        self.assertNotIn("last", (state.get("feed") or {}).get("jira", {}))

    def test_jira_401_becomes_a_note(self):
        valet.CONF["feed_github_login"] = ""

        def boom(*a, **k):
            raise valet.FeedAuthError("Jira 401")

        valet._jira = boom
        r = valet.feed()
        self.assertEqual(r["jira_error"], "Jira 401")
        note = [e for e in self.events() if e["kind"] == "note"]
        self.assertIn("Jira 401", note[0]["text"])


    def test_auto_respects_feed_every_min(self):
        valet.CONF["feed_github_login"] = ""
        self.addCleanup(valet.CONF.update, {"feed_every_min": 10.0})
        valet.CONF["feed_every_min"] = 30.0
        self.jira.issues = []
        self.assertEqual(valet.feed(force=False)["jira"], 0)  # first time: runs
        r = valet.feed(force=False)
        self.assertIn("skipped", r)  # 10 min later from the timer: too soon
        self.assertNotIn("skipped", valet.feed())  # by hand: always
        st = json.loads(valet.SYNC_STATE.read_text())
        st["feed"]["last_ok"] -= 30 * 60
        valet.SYNC_STATE.write_text(json.dumps(st))
        self.assertNotIn("skipped", valet.feed(force=False))  # 30 min later: runs


class PostTest(unittest.TestCase):
    def test_network_error_is_a_failed_send_not_a_crash(self):
        import urllib.error
        orig = valet.urllib.request.urlopen

        def down(*a, **k):
            raise urllib.error.URLError("[Errno 65] No route to host")

        valet.urllib.request.urlopen = down
        self.addCleanup(setattr, valet.urllib.request, "urlopen", orig)
        valet.CONF["sync_url"] = "http://wb.test/ingest"
        self.assertEqual(valet._post([{"x": 1}]), 0)


if __name__ == "__main__":
    unittest.main()
