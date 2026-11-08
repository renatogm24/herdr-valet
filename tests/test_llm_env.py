"""The `claude -p` valet runs itself (summaries, recaps) goes through llm_base_url with the key in
llm_key_file, and without the credentials that would win over it. `claude` is a stub that prints
the variables it got.

    python3 -m unittest discover -s tests
"""

import importlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ["XDG_DATA_HOME"] = str(TMP)
os.environ["HERDR_VALET_CONFIG"] = str(TMP / "missing.toml")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
valet = importlib.import_module("valet")

STUB = TMP / "claude"
STUB.write_text("#!/bin/sh\ncat >/dev/null\n"
                'echo "Title: stub"\n'
                'echo "base=${ANTHROPIC_BASE_URL-<unset>}"\n'
                'echo "token=${ANTHROPIC_AUTH_TOKEN-<unset>}"\n'
                'echo "oauth=${CLAUDE_CODE_OAUTH_TOKEN-<unset>}"\n'
                'echo "apikey=${ANTHROPIC_API_KEY-<unset>}"\n')
STUB.chmod(STUB.stat().st_mode | stat.S_IXUSR)


class LlmEnv(unittest.TestCase):
    def setUp(self):
        self.conf = dict(valet.CONF)
        valet.CONF["summary_command"] = str(STUB)
        self.env = dict(os.environ)
        # Like the systemd service: nothing from ~/.claude/settings.json's env.
        os.environ.pop("ANTHROPIC_BASE_URL", None)
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "oauth-secret"
        os.environ["ANTHROPIC_API_KEY"] = "api-secret"

    def tearDown(self):
        valet.CONF.clear()
        valet.CONF.update(self.conf)
        os.environ.clear()
        os.environ.update(self.env)

    def summary(self):
        out = valet.summarize_text("s1", "prompt", "fallback")
        return dict(line.split("=", 1) for line in out.splitlines()[1:])

    def test_without_proxy_inherits_everything(self):
        got = self.summary()
        self.assertEqual(got["base"], "<unset>")
        self.assertEqual(got["oauth"], "oauth-secret")

    def test_proxy_with_key(self):
        key = TMP / "k.key"
        key.write_text("sk-virtual\n")
        valet.CONF.update(llm_base_url="http://127.0.0.1:4400", llm_key_file=str(key))
        got = self.summary()
        self.assertEqual(got["base"], "http://127.0.0.1:4400")
        self.assertEqual(got["token"], "sk-virtual")
        self.assertEqual(got["oauth"], "<unset>")
        self.assertEqual(got["apikey"], "<unset>")

    def test_proxy_without_key_file_still_drops_credentials(self):
        valet.CONF.update(llm_base_url="http://127.0.0.1:4400", llm_key_file=str(TMP / "nope.key"))
        got = self.summary()
        self.assertEqual(got["base"], "http://127.0.0.1:4400")
        self.assertEqual(got["token"], "<unset>")
        self.assertEqual(got["oauth"], "<unset>")


if __name__ == "__main__":
    unittest.main()
