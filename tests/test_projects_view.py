"""The Projects view: create, clone, edit, fetch and worktree removal go to project_command with their
flags; promoting an ad-hoc folder also moves its Claude conversations and parked cards along. The
launcher is a small shell script that records its argv; Claude's processes are stubbed.

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


class ProjectsView(unittest.TestCase):
    def setUp(self):
        self.conf, self.dirs, self.procs = dict(valet.CONF), list(valet.CONFIG_DIRS), valet.claude_processes
        self.argv = TMP / "argv.txt"
        self.reply = TMP / "reply.json"
        cmd = TMP / "project.sh"
        # Records its argv; `create --from X` moves X to the --dir (or $TMP/code/<name>) like the
        # launcher does; prints reply.json.
        cmd.write_text("#!/bin/sh\n"
                       f'printf "%s\\n" "$@" > {self.argv}\n'
                       'if [ "$1" = create ]; then name="$2"; from=""; shift 2\n'
                       '  while [ $# -gt 0 ]; do case "$1" in --from) from="$2"; shift 2;; *) shift;; esac; done\n'
                       f'  [ -n "$from" ] && mv "$from" "{TMP}/code/$name"\n'
                       'fi\n'
                       f'cat {self.reply}\n')
        cmd.chmod(0o755)
        valet.CONF["project_command"] = f"{cmd} {{args}}"
        valet.claude_processes = lambda: []
        (TMP / "code").mkdir(exist_ok=True)

    def tearDown(self):
        valet.CONF.clear()
        valet.CONF.update(self.conf)
        valet.CONFIG_DIRS[:] = self.dirs
        valet.claude_processes = self.procs

    def args(self):
        return self.argv.read_text().splitlines()

    def test_create_flags(self):
        self.reply.write_text('{"id": "x", "path": "/p/x", "github": "https://github.com/o/x"}')
        valet.project_create("x", "personal", github="o", public=True)
        self.assertEqual(self.args(), ["create", "x", "--context", "personal", "--type", "single",
                                       "--github", "o", "--public", "--json"])
        valet.project_create("x", "test", github="o", no_github=True, public=True, ptype="direct", label="X; y")
        self.assertEqual(self.args(), ["create", "x", "--context", "test", "--label", "X; y", "--type", "direct",
                                       "--no-github", "--json"])
        with self.assertRaisesRegex(ValueError, "lowercase"):
            valet.project_create("x", pid="Bad")

    def test_clone_edit_fetch(self):
        self.reply.write_text('{"id": "lib", "path": "/p/lib"}')
        valet.project_clone("someone/lib", "test", path="~/x")
        self.assertEqual(self.args(), ["clone", "someone/lib", "--context", "test", "--dir", "~/x", "--type", "single", "--json"])
        valet.project_edit("lib", context="personal")
        self.assertEqual(self.args(), ["edit", "lib", "--context", "personal", "--json"])
        self.reply.write_text('{"fetched": ["a", "b"], "failed": []}')
        self.assertEqual(valet.project_fetch(["a", "b"])["fetched"], ["a", "b"])
        self.assertEqual(self.args(), ["fetch", "a", "b", "--json"])
        with self.assertRaises(ValueError):
            valet.project_fetch(["$(id)"])
        with self.assertRaises(ValueError):
            valet.project_edit("Bad id")

    def test_worktree_remove_refuses_with_a_session_open(self):
        wt = TMP / "wt-a"
        (wt / "sub").mkdir(parents=True)
        valet.claude_processes = lambda: [{"cwd": str(wt / "sub"), "kind": "interactive"}]
        with self.assertRaisesRegex(ValueError, "session is open"):
            valet.worktree_remove(str(wt))
        # A background agent there does not count; a session in a sibling with the same prefix neither.
        valet.claude_processes = lambda: [{"cwd": str(wt), "kind": "bg"}, {"cwd": str(wt) + "-other"}]
        self.reply.write_text('{"path": "%s", "branch_deleted": true}' % wt)
        valet.worktree_remove(str(wt), force=True, delete_branch=True)
        self.assertEqual(self.args(), ["worktree", "remove", str(wt), "--force", "--delete-branch", "--json"])

    def test_list_counts_open_and_parked(self):
        wt, ad = str(TMP / "wt-b"), str(TMP / "adhoc-b")
        self.reply.write_text(json.dumps([{"id": "p", "worktrees": [{"path": wt}]}]))
        valet.claude_processes = lambda: [{"cwd": wt, "kind": "interactive"}, {"cwd": wt, "kind": "bg"}]
        card = valet.card_path("c-list")
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text(json.dumps({"session_id": "c-list", "cwd": wt + "/sub", "parked_at": "2026-11-09T00:00:00+00:00"}))
        orig = valet._project_cli
        valet._project_cli = lambda args, timeout=60: (orig(args, timeout) if args[0] == "list"
                                                        else [{"path": ad, "name": "adhoc-b"}])
        try:
            r = valet.project_list()
        finally:
            valet._project_cli = orig
            card.unlink()
        self.assertEqual((r["projects"][0]["worktrees"][0]["open"], r["projects"][0]["worktrees"][0]["parked"]), (1, 1))
        self.assertEqual((r["adhoc"][0]["open"], r["adhoc"][0]["parked"]), (0, 0))

    def test_promote_moves_conversations_and_cards(self):
        old = TMP / "adhoc" / "2026-11-09-idea"
        (old / "sub").mkdir(parents=True)
        new = TMP / "code" / "idea"
        conf = TMP / "claude-conf"
        valet.CONFIG_DIRS[:] = [conf]
        src = conf / "projects" / valet.claude_slug(str(old))
        src.mkdir(parents=True)
        tr = src / "s1.jsonl"
        tr.write_text("\n".join([
            json.dumps({"type": "user", "cwd": str(old), "message": {"content": "hola"}}, separators=(",", ":")),
            json.dumps({"type": "user", "cwd": str(old / "sub")}),
            json.dumps({"type": "user", "cwd": str(old) + "-other"}, separators=(",", ":")),
        ]) + "\n")
        os.utime(tr, (1_000_000, 1_000_000))
        card = valet.card_path("s1")
        card.write_text(json.dumps({"session_id": "s1", "cwd": str(old), "parked_at": "2026-11-09T00:00:00+00:00"}))
        self.reply.write_text(json.dumps({"id": "idea", "path": str(new)}))

        valet.claude_processes = lambda: [{"cwd": str(old), "kind": "interactive"}]
        with self.assertRaisesRegex(ValueError, "park it first"):
            valet.project_promote(str(old), "idea", no_github=True)
        valet.claude_processes = lambda: []

        r = valet.project_promote(str(old), "idea", "personal", no_github=True)
        self.assertEqual(self.args(), ["create", "idea", "--from", str(old), "--context", "personal",
                                       "--type", "single", "--no-github", "--json"])
        self.assertEqual(r["conversations_moved"], 1)
        moved = conf / "projects" / valet.claude_slug(str(new)) / "s1.jsonl"
        self.assertFalse(src.exists())
        cwds = [json.loads(line)["cwd"] for line in moved.read_text().splitlines()]
        self.assertEqual(cwds, [str(new), str(new / "sub"), str(old) + "-other"])
        self.assertEqual(moved.stat().st_mtime, 1_000_000)
        self.assertEqual(json.loads(card.read_text())["cwd"], str(new))
        self.assertTrue((new / "sub").is_dir())
        card.unlink()


if __name__ == "__main__":
    unittest.main()
