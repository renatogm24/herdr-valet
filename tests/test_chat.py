"""Chat on the page: the Cloudflare Access token is checked by valet itself (a forged or foreign one
is refused), and the model only picks among what search found. The RSA key is made with openssl;
the model and search are stubbed.

    python3 -m unittest discover -s tests
"""

import base64
import importlib
import json
import os
import subprocess
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

KEY = TMP / "key.pem"
subprocess.run(["openssl", "genrsa", "-out", str(KEY), "2048"], check=True, capture_output=True)
N = int(subprocess.run(["openssl", "rsa", "-in", str(KEY), "-noout", "-modulus"], check=True,
                       capture_output=True, text=True).stdout.strip().split("=", 1)[1], 16)
TEAM, AUD, EMAIL = "team.cloudflareaccess.com", "aud-123", "me@example.com"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def token(payload: dict, header: dict | None = None, key: Path = KEY) -> str:
    h = b64(json.dumps(header or {"alg": "RS256", "kid": "k1"}).encode())
    p = b64(json.dumps(payload).encode())
    sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(key)], input=f"{h}.{p}".encode(),
                         check=True, capture_output=True).stdout
    return f"{h}.{p}.{b64(sig)}"


def claims(**over) -> dict:
    return {"aud": [AUD], "iss": f"https://{TEAM}", "email": EMAIL, "exp": time.time() + 600,
            "nbf": time.time() - 10, **over}


class Access(unittest.TestCase):
    def setUp(self):
        self.conf = dict(valet.CONF)
        valet.CONF.update(chat_access_team=TEAM, chat_access_aud=AUD, chat_access_emails=["Me@Example.com"])
        valet._ACCESS_CERTS.update(at=time.time(), keys={"k1": (N, 65537)})

    def tearDown(self):
        valet.CONF.clear()
        valet.CONF.update(self.conf)

    def test_valid(self):
        self.assertEqual(valet.access_email(token(claims())), EMAIL)

    def test_refused(self):
        other = TMP / "other.pem"
        subprocess.run(["openssl", "genrsa", "-out", str(other), "2048"], check=True, capture_output=True)
        good = token(claims())
        h, p, s = good.split(".")
        forged_payload = b64(json.dumps(claims(email="me@example.com", aud=["x"])).encode())
        cases = {
            "another app's aud": token(claims(aud=["other-aud"])),
            "another person": token(claims(email="vanessa@example.com")),
            "expired": token(claims(exp=time.time() - 120)),
            "not yet valid": token(claims(nbf=time.time() + 600)),
            "another team": token(claims(iss="https://evil.cloudflareaccess.com")),
            "signed with another key": token(claims(), key=other),
            "payload swapped": f"{h}.{forged_payload}.{s}",
            "alg none": f"{b64(json.dumps({'alg': 'none', 'kid': 'k1'}).encode())}.{p}.",
            "unknown kid": token(claims(), header={"alg": "RS256", "kid": "k9"}),
            "garbage": "a.b",
            "empty": "",
        }
        for why, tok in cases.items():
            self.assertIsNone(valet.access_email(tok), why)

    def test_off_without_config(self):
        valet.CONF["chat_access_emails"] = []
        self.assertFalse(valet.chat_enabled())
        self.assertIsNone(valet.access_email(token(claims())))


def hit(sid, title):
    return {"session_id": sid, "state": "parked", "title": title, "where": "", "first": "", "label": "exp-track",
            "cwd": "/x", "branch": "main", "at": "2026-10-01T00:00:00Z", "score": 1}


class Chat(unittest.TestCase):
    def setUp(self):
        self.saved = (valet.llm_json, valet.search, valet.can_launch, valet.projects)
        valet.can_launch = lambda: True
        valet.projects = lambda: [{"id": "exp-track", "label": "Expense Tracker"}]
        self.searched = []

        def search(q, limit=10, with_live=True):
            self.searched.append(q)
            return [hit("s-bank", "Bank login"), hit("s-other", "Other")] if "banco" in q else []
        valet.search = search

    def tearDown(self):
        valet.llm_json, valet.search, valet.can_launch, valet.projects = self.saved

    def test_picks_only_what_search_found(self):
        replies = iter([{"queries": [["login", "banco"], ["bank"]], "new": None},
                        {"answer": "Sí, en octubre.", "picks": ["s-bank", "made-up-id"]}])
        prompts = []
        valet.llm_json = lambda system, prompt, timeout=90: (prompts.append(prompt), next(replies))[1]
        r = valet.chat("hace tiempo estuve con el login del banco, ¿no?")
        self.assertEqual(self.searched, ["login banco", "bank"])
        self.assertEqual([x["session_id"] for x in r["results"]], ["s-bank"])
        self.assertEqual(r["answer"], "Sí, en octubre.")
        self.assertIn("s-other", prompts[1])  # the model saw both candidates

    def test_new_session_only_for_a_known_project(self):
        replies = iter([{"queries": [], "new": {"project": "exp-track", "branch": "fix tz;rm", "goal": "arreglar tz"}},
                        {"answer": "Listo", "picks": []}])
        valet.llm_json = lambda system, prompt, timeout=90: next(replies)
        r = valet.chat("abrime una sesión nueva en exp-track para arreglar tz")
        self.assertEqual(r["new"], {"project": "exp-track", "branch": "", "goal": "arreglar tz"})
        replies = iter([{"queries": [], "new": {"project": "nope"}}, {"answer": "", "picks": []}])
        self.assertIsNone(valet.chat("nueva en nope").get("new"))

    def test_without_the_model_it_still_searches(self):
        valet.llm_json = lambda system, prompt, timeout=90: None
        r = valet.chat("estuve con el banco hace tiempo")
        self.assertTrue(self.searched)
        self.assertFalse(r["llm"])
        self.assertEqual([x["session_id"] for x in r["results"]], ["s-bank", "s-other"])

    def test_limits(self):
        with self.assertRaises(ValueError):
            valet.chat("")
        with self.assertRaises(ValueError):
            valet.chat("x" * 501)


if __name__ == "__main__":
    unittest.main()
