"""New session from the page: projects_command lists, prepare_command finds or creates the directory
and its stderr is the error, and the tab goes in the workspace that holds the same repository. The
launcher commands are small shell scripts; herdr is stubbed.

    python3 -m unittest discover -s tests
"""

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ["XDG_DATA_HOME"] = str(TMP)
os.environ["HERDR_VALET_CONFIG"] = str(TMP / "missing.toml")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
valet = importlib.import_module("valet")


def git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": str(TMP / "gitconfig"),
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


REPO = TMP / "repo"
REPO.mkdir()
git("init", "-q", "-b", "main", str(REPO))
git("commit", "-q", "--allow-empty", "-m", "init", cwd=REPO)
WT = TMP / "wt-feat"
git("worktree", "add", "-q", "-b", "feat/x", str(WT), cwd=REPO)
OTHER = TMP / "other"
OTHER.mkdir()
git("init", "-q", str(OTHER))


class FakeHerdr:
    """Workspaces with panes at given directories; records what valet asks for."""

    def __init__(self, workspaces):
        self.workspaces = workspaces  # {ws_id: [cwd, ...]}
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("workspace", "list"):
            return {"workspaces": [{"workspace_id": w, "label": w} for w in self.workspaces]}
        if args[:2] == ("pane", "list"):
            ws = args[3]
            return {"panes": [{"pane_id": f"{ws}:p{i}", "cwd": c, "tab_id": f"{ws}:t1"}
                              for i, c in enumerate(self.workspaces.get(ws, ["/"]))]}
        if args[:2] == ("tab", "create"):
            return {"root_pane": {"pane_id": f"{args[3]}:pNEW"}}
        if args[:2] == ("workspace", "create"):
            self.workspaces["wNEW"] = [args[3]]
            return {"workspace": {"workspace_id": "wNEW"}}
        return {}


class NewSession(unittest.TestCase):
    def setUp(self):
        self.conf = dict(valet.CONF)
        self.saved = (valet.herdr, valet.herdr_running)
        valet.herdr_running = lambda: True
        prep = TMP / "prepare.sh"
        prep.write_text(
            "#!/bin/sh\n"
            'case "$1" in\n'
            f'  proj@feat/x) echo \'{{"path": "{WT}", "branch": "feat/x", "created": false, "project": "proj"}}\' ;;\n'
            f'  other) echo \'{{"path": "{OTHER}", "branch": "main", "created": true, "project": "other"}}\' ;;\n'
            f'  "adhoc:mi cosa") echo \'{{"path": "{OTHER}", "branch": "", "created": true, "project": "adhoc"}}\' ;;\n'
            '  *) printf "\\033[31m✗\\033[0m Proyecto desconocido: %s\\n" "$1" >&2; exit 1 ;;\n'
            "esac\n")
        prep.chmod(0o755)
        valet.CONF.update(
            projects_command=f"echo '[{{\"id\": \"proj\", \"worktrees\": []}}]'",
            prepare_command=f"{prep} {{target}}",
            launch_command="code launch {path} --model {model} --prompt {prompt} --plugins {plugins}",
        )

    def tearDown(self):
        valet.CONF.clear()
        valet.CONF.update(self.conf)
        valet.herdr, valet.herdr_running = self.saved

    def test_off_without_the_three_commands(self):
        valet.CONF["launch_command"] = ""
        self.assertFalse(valet.can_launch())
        with self.assertRaisesRegex(ValueError, "off"):
            valet.new_session("proj@feat/x")

    def test_projects(self):
        self.assertEqual(valet.projects(), [{"id": "proj", "worktrees": []}])

    def test_goes_in_the_workspace_of_the_same_repo(self):
        # The main clone is open in w2: a worktree of the same repo goes there, as a tab named after the branch.
        h = valet.herdr = FakeHerdr({"w1": [str(OTHER)], "w2": [str(REPO)]})
        r = valet.new_session("proj@feat/x", "opus", "fix the tz; it's 'urgent'", "")
        self.assertEqual(r["workspace"], "w2")
        create = next(c for c in h.calls if c[:2] == ("tab", "create"))
        self.assertEqual(create, ("tab", "create", "--workspace", "w2", "--cwd", str(WT), "--label", "feat/x", "--no-focus"))
        run = next(c for c in h.calls if c[:2] == ("pane", "run"))
        self.assertEqual(run[2], "w2:pNEW")
        self.assertEqual(run[3], f"code launch {WT} --model opus --prompt 'fix the tz; it'\"'\"'s '\"'\"'urgent'\"'\"'' --plugins ''")

    def test_new_workspace_named_after_the_project(self):
        h = valet.herdr = FakeHerdr({"w1": [str(REPO)]})
        r = valet.new_session("other", "", "", "none")
        self.assertEqual(r["workspace"], "wNEW")
        self.assertTrue(r["created"])
        self.assertIn(("workspace", "create", "--cwd", str(OTHER), "--label", "other", "--no-focus"), h.calls)
        self.assertIn(("tab", "rename", "wNEW:t1", "main"), h.calls)

    def test_launcher_error_is_its_stderr_without_colors(self):
        valet.herdr = FakeHerdr({})
        with self.assertRaises(ValueError) as e:
            valet.new_session("nope")
        self.assertEqual(str(e.exception), "✗ Proyecto desconocido: nope")

    def test_rejects_odd_targets(self):
        valet.herdr = FakeHerdr({})
        for bad in ("", "a b", "x;rm", "p@b c", "$(id)"):
            with self.assertRaises(ValueError, msg=bad):
                valet.new_session(bad)

    def test_adhoc_target(self):
        h = valet.herdr = FakeHerdr({})
        r = valet.new_session("adhoc:mi cosa", "opus", "", "")
        self.assertTrue(r["created"])
        self.assertIn(("workspace", "create", "--cwd", str(OTHER), "--label", "adhoc", "--no-focus"), h.calls)
        for bad in ("adhoc:a/b", "adhoc:" + "x" * 61, "adhoc:a\nb"):
            with self.assertRaises(ValueError, msg=bad):
                valet.new_session(bad)

    def test_herdr_down(self):
        valet.herdr_running = lambda: False
        with self.assertRaises(valet.HerdrDown):
            valet.new_session("proj@feat/x")


class Projects(unittest.TestCase):
    """project_command gets its args shell-quoted; off when it is not set."""

    def setUp(self):
        self.conf = dict(valet.CONF)
        self.argv = TMP / "argv.txt"
        cmd = TMP / "project.sh"
        cmd.write_text("#!/bin/sh\n"
                       f'printf "%s\\n" "$@" > {self.argv}\n'
                       'if [ "$1" = add ]; then echo \'{"id": "my-repo"}\'; '
                       'elif [ "$2" = anku-x ]; then echo "anku-x es del equipo" >&2; exit 1; '
                       'else echo \'{"id": "x", "removed": true}\'; fi\n')
        cmd.chmod(0o755)
        valet.CONF["project_command"] = f"{cmd} {{args}}"

    def tearDown(self):
        valet.CONF.clear()
        valet.CONF.update(self.conf)

    def test_add(self):
        r = valet.project_add(str(OTHER), "", "My repo; ok", "personal", "direct")
        self.assertEqual(r, {"id": "my-repo"})
        self.assertEqual(self.argv.read_text().splitlines(),
                         ["add", str(OTHER), "--type", "direct", "--label", "My repo; ok", "--context", "personal", "--json"])

    def test_add_checks_the_folder_and_id(self):
        with self.assertRaisesRegex(ValueError, "no such directory"):
            valet.project_add(str(TMP / "nope"))
        with self.assertRaisesRegex(ValueError, "lowercase"):
            valet.project_add(str(OTHER), "Bad Id")

    def test_remove_and_its_error(self):
        self.assertTrue(valet.project_remove("x")["removed"])
        self.assertEqual(self.argv.read_text().splitlines(), ["remove", "x", "--json"])
        with self.assertRaisesRegex(ValueError, "del equipo"):
            valet.project_remove("anku-x")
        with self.assertRaises(ValueError):
            valet.project_remove("$(id)")

    def test_off(self):
        valet.CONF["project_command"] = ""
        with self.assertRaisesRegex(ValueError, "off"):
            valet.project_add(str(OTHER))
        with self.assertRaisesRegex(ValueError, "off"):
            valet.project_remove("x")


if __name__ == "__main__":
    unittest.main()
