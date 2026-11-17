#!/usr/bin/env python3
"""Tests for agy-task against a fake agy (they never call the real agy or spend quota).

Run with Python 3.11 or newer:  python3 tests/test_agy_task.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGY_TASK = HERE.parent / "lib" / "agy_task.py"
LAUNCHER = HERE.parent / "bin" / "agy-task"
FAKE = HERE / "fake_agy"

DONE = {"status": "done", "summary": "done", "files_changed": [], "decisions": [], "questions": []}
GOOD = "def add(a, b):\n    return a + b\n"
BAD = "def add(a, b):\n    return a - b\n"
# Git identity for the tests: CI machines do not have one configured.
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
VERIFY = "python3 -c \"import sys; sys.path.insert(0, 'src'); import calc; assert calc.add(2, 3) == 5\""


def manual(tid, role="implement", risk="low", extra="", body=None):
    head = f'id = "{tid}"\ntitle = "task {tid}"\nrole = "{role}"\nrisk = "{risk}"\n{extra}'
    if role == "implement" and "allowed" not in extra:
        head += 'allowed = ["src/**"]\nprotected = ["tests/**"]\n'
    body = body or "## Goal\nImplement add.\n\n## Acceptance criteria\n- add(2, 3) == 5\n"
    return f"+++\n{head}+++\n\n{body}"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agytest-")).resolve()
        self.repo = self.tmp / "proj"
        (self.repo / "src").mkdir(parents=True)
        (self.repo / "tests").mkdir()
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    raise NotImplementedError\n")
        (self.repo / "tests" / "test_calc.py").write_text("# protected test\n")
        (self.repo / "README.md").write_text("project\n")
        self.git("init", "-q")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
        self.env = dict(os.environ, AGY_BIN=str(FAKE), AGY_BRIDGE_HOME=str(self.tmp / "home"),
                        FAKE_AGY_PLAN=str(self.tmp / "plan.json"), **IDENTITY)
        self.cli("init")
        (self.repo / ".agy" / "config.toml").write_text(f"verify = ['''{VERIFY}''']\n")
        self.containment(ok=True)

    def containment(self, ok=None):
        """Containment record for the fake agy's version (None = not verified)."""
        path = self.tmp / "home" / "containment.json"
        path.parent.mkdir(exist_ok=True)
        if ok is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(json.dumps({"agy_version": "0.0.0-fake", "ok": ok}))
        return path

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True, check=True,
                              env=dict(os.environ, **IDENTITY)).stdout

    def cli(self, *a, code=0):
        p = subprocess.run([sys.executable, str(AGY_TASK), *a], cwd=self.repo, env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, code, f"rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
        return p.stdout + p.stderr

    def plan(self, *steps):
        Path(self.env["FAKE_AGY_PLAN"]).write_text(json.dumps(list(steps)))
        calls = Path(self.env["FAKE_AGY_PLAN"] + ".calls")
        if calls.exists():
            calls.unlink()

    def calls(self):
        return json.loads(Path(self.env["FAKE_AGY_PLAN"] + ".calls").read_text())

    def task(self, tid, **kw):
        (self.repo / ".agy" / "tasks" / f"{tid}.md").write_text(manual(tid, **kw))

    def state(self, tid):
        return json.loads((self.repo / ".agy" / "runs" / tid / "state.json").read_text())


class Implement(Base):
    def test_happy_path_and_accept(self):
        self.task("T1")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        out = self.cli("run", "T1")
        self.assertIn("REVIEW", out)
        st = self.state("T1")
        self.assertEqual((st["state"], st["review_level"], st["attempts"]), ("review", "summary", 1))
        call = self.calls()[0]
        self.assertEqual(call["cwd"], st["worktree"])
        self.assertNotEqual(Path(st["worktree"]), self.repo)
        settings = json.loads(call["argv"][call["argv"].index("--settings") + 1])
        self.assertFalse(settings["allowNonWorkspaceAccess"])
        self.assertEqual(settings["permissions"]["allow"], [])
        self.assertIn("accept-edits", call["argv"])
        self.assertIn("File map", call["argv"][-1])
        self.assertIn("src/calc.py", call["argv"][-1].split("## File map")[1])
        self.assertNotIn("command(", call["argv"][call["argv"].index("--settings") + 1])
        # the main project does not change until the task is accepted
        self.assertIn("NotImplementedError", (self.repo / "src" / "calc.py").read_text())
        self.assertIn("return a + b", self.cli("diff", "T1"))
        out = self.cli("accept", "T1")
        self.assertIn("staged", out)
        self.assertEqual((self.repo / "src" / "calc.py").read_text(), GOOD)
        self.assertIn("src/calc.py", self.git("diff", "--cached", "--name-only"))
        self.assertEqual(self.git("log", "--oneline").count("\n"), 1)  # no new commit
        self.assertFalse(Path(st["worktree"]).exists())
        self.assertEqual(self.git("branch", "--list", "agy/T1").strip(), "")

    def test_out_of_scope_and_protected_are_reverted(self):
        self.task("T2")
        self.plan({"write": {"src/calc.py": GOOD, "README.md": "hacked\n", "tests/test_calc.py": "assert True\n",
                             "extra.txt": "x\n"}, "so": DONE})
        self.cli("run", "T2")
        st = self.state("T2")
        kinds = sorted((i["kind"], i["path"]) for i in st["incidents"])
        self.assertEqual(kinds, [("out_of_scope", "README.md"), ("out_of_scope", "extra.txt"),
                                 ("protected_modified", "tests/test_calc.py")])
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertEqual(st["review_level"], "diff")
        self.assertIn("--reviewed", self.cli("accept", "T2", code=1))
        self.cli("accept", "T2", "--reviewed")
        self.assertEqual((self.repo / "README.md").read_text(), "project\n")
        self.assertFalse((self.repo / "extra.txt").exists())

    def test_verify_failure_triggers_fixup(self):
        self.task("T3", risk="medium")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE}, {"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T3")
        st = self.state("T3")
        self.assertEqual((st["state"], st["attempts"], st["review_level"]), ("review", 2, "diff"))
        second = self.calls()[1]["argv"]
        self.assertEqual(second[second.index("--conversation") + 1], "conv-fake")
        self.assertIn("The supervisor's verification failed", second[-1])

    def test_verify_never_passes(self):
        self.task("T4", extra="max_fixups = 1\n")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        out = self.cli("run", "T4", code=3)
        self.assertIn("FAILED (gates)", out)
        self.assertEqual(self.state("T4")["attempts"], 2)
        self.cli("accept", "T4", code=1)
        # Claude can correct it with fix and the task recovers
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("fix", "T4", "use addition, not subtraction")
        self.assertEqual(self.state("T4")["state"], "review")
        st = self.state("T4")
        self.assertEqual(st["attempts"], 3)  # attempts accumulate across run and fix
        self.assertLess(st["active_secs"], 60)  # work time, not wall-clock time since the first run
        rows = [json.loads(l) for l in (self.repo / ".agy" / "runs" / "usage.jsonl").read_text().splitlines()]
        self.assertEqual([(r["id"], r["input"]) for r in rows], [("T4", 200), ("T4", 100)])  # per session
        self.assertEqual(st["usage"]["input"], 300)
        self.assertIn("use addition, not subtraction", self.calls()[0]["argv"][-1])

    def test_blocked_then_fix(self):
        self.task("T5")
        self.plan({"so": dict(DONE, status="blocked", questions=["integers or floats?"])})
        out = self.cli("run", "T5", code=2)
        self.assertIn("integers or floats?", out)
        self.assertIn("BLOCKED (questions)", out)
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("fix", "T5", "integers")
        self.assertEqual(self.state("T5")["state"], "review")

    def test_denied_action_and_missing_report_retry(self):
        self.task("T6")
        self.plan({"denied": [{"action": "command", "display_name": "Bash"}]}, {"write": {"src/calc.py": GOOD}},
                  {"so": DONE})
        self.cli("run", "T6")
        st = self.state("T6")
        self.assertEqual((st["state"], st["attempts"]), ("review", 3))
        self.assertIn("action that is not allowed", self.calls()[1]["argv"][-1])
        self.assertIn("did not deliver the structured report", self.calls()[2]["argv"][-1])

    def test_no_changes_fails(self):
        self.task("T7", extra="max_fixups = 0\n")
        self.plan({"so": DONE})
        self.cli("run", "T7", code=3)

    def test_executor_errors(self):
        self.task("T8")
        self.plan({"status": "ERROR", "rc": 1, "stderr": "RESOURCE_EXHAUSTED: quota exceeded"})
        self.cli("run", "T8", code=10)
        self.assertEqual(len(self.calls()), 1)  # quota failures are not retried
        self.cli("run", "T8", code=1)  # there is previous work: --restart is required
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T8", "--restart")

    def test_reject_cleans_up(self):
        self.task("T9")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T9")
        wt = Path(self.state("T9")["worktree"])
        self.cli("reject", "T9", "--reason", "not convinced")
        self.assertFalse(wt.exists())
        self.assertEqual(self.state("T9")["state"], "rejected")
        self.assertEqual(self.git("status", "--porcelain", "--", "src").strip(), "")

    def test_linked_dependencies_stay_out_of_the_diff(self):
        # git does not copy ignored paths (dependencies, SDK): they are symlinked and never enter agy's diff.
        (self.repo / "deps").mkdir()
        (self.repo / "deps" / "lib.py").write_text("x = 1\n")
        (self.repo / ".gitignore").write_text("deps/\n")
        self.git("add", ".gitignore")
        self.git("commit", "-qm", "ignore")
        (self.repo / ".agy" / "config.toml").write_text(f"verify = [\'\'\'{VERIFY}\'\'\', 'test -f deps/lib.py']\nlink = ['deps']\n")
        self.task("T10")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T10")
        st = self.state("T10")
        self.assertEqual(st["links"], ["deps"])
        self.assertEqual(st["incidents"], [])
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertEqual(st["review_level"], "summary")

    def test_accept_conflict_leaves_project_intact(self):
        self.task("T11")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T11")
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    return 0  # local change\n")
        self.assertIn("could not integrate", self.cli("accept", "T11", code=3))
        self.assertIn("local change", (self.repo / "src" / "calc.py").read_text())
        self.assertEqual(self.state("T11")["state"], "review")

    def test_seed_files_reach_agy_but_stay_out_of_the_diff(self):
        # Claude writes the test first and does not commit it: agy must see it, cannot change it,
        # and it is not part of what agy delivers.
        seed = self.repo / "tests" / "test_add.py"
        seed.write_text("import sys; sys.path.insert(0, 'src')\nimport calc\nassert calc.add(2, 3) == 5\n")
        (self.repo / ".agy" / "config.toml").write_text("verify = ['python3 tests/test_add.py']\n")
        self.task("S1", extra='allowed = ["src/**"]\nseed = ["tests/test_add.py"]\n')
        self.plan({"write": {"src/calc.py": BAD, "tests/test_add.py": "assert True\n"}, "so": DONE},
                  {"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "S1")
        st = self.state("S1")
        self.assertEqual((st["state"], st["attempts"]), ("review", 2))
        self.assertEqual([(i["kind"], i["path"]) for i in st["incidents"]],
                         [("supervisor_file_modified", "tests/test_add.py")])
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertIn("tests/test_add.py", self.calls()[0]["argv"][-1])
        self.cli("accept", "S1", "--reviewed")
        self.assertEqual(self.git("diff", "--cached", "--name-only").split(), ["src/calc.py"])
        self.assertIn("calc.add(2, 3) == 5", seed.read_text())  # Claude's test is still intact

    def test_seed_must_exist(self):
        self.task("S2", extra='allowed = ["src/**"]\nseed = ["tests/nope.py"]\n')
        self.assertIn("is not an existing file", self.cli("check", "S2", code=1))

    def test_autofix_runs_before_gates(self):
        # The "formatter" fixes what agy got wrong; without it, verification would fail.
        fixer = "python3 -c \"import pathlib; p = pathlib.Path('src/calc.py'); p.write_text(p.read_text().replace('a - b', 'a + b'))\""
        (self.repo / ".agy" / "config.toml").write_text(f"verify = [\'\'\'{VERIFY}\'\'\']\nautofix = [\'\'\'{fixer}\'\'\']\n")
        self.task("A1")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        self.cli("run", "A1")
        self.assertEqual((self.state("A1")["state"], self.state("A1")["attempts"]), ("review", 1))
        self.assertIn("return a + b", self.cli("diff", "A1"))

    def test_search_results_are_embedded(self):
        self.task("Q1", extra='allowed = ["src/**"]\nsearch = ["NotImplementedError", "does-not-exist-zzz"]\n')
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "Q1")
        prompt = self.calls()[0]["argv"][-1]
        self.assertIn("src/calc.py:2:    raise NotImplementedError", prompt)
        self.assertIn("`does-not-exist-zzz` — 0 match(es)", prompt)

    def test_baseline(self):
        self.assertIn("BASELINE VERIFICATION FAILS", self.cli("baseline", code=3))  # add does not exist yet
        (self.repo / ".agy" / "config.toml").write_text("verify = ['test -f src/calc.py']\n")
        self.assertIn("baseline verification passed", self.cli("baseline"))
        self.assertEqual(self.git("worktree", "list").count("\n"), 1)  # leaves no worktrees behind

    def test_file_map_omits_media(self):
        (self.repo / "photo.PNG").write_bytes(b"x")
        (self.repo / "src" / ".gitkeep").write_text("")
        self.git("add", "-A")
        self.git("commit", "-qm", "media")
        self.task("M1")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "M1")
        fmap = self.calls()[0]["argv"][-1].split("## File map")[1]
        self.assertNotIn("photo.PNG", fmap)
        self.assertNotIn(".gitkeep", fmap)
        self.assertIn("2 media, binary or placeholder files omitted", fmap)
        self.assertIn("README.md", fmap)

    def test_accept_several_tasks_in_a_row(self):
        # Parallel workflow: two independent tasks are accepted one after the other, with other
        # uncommitted changes present in the project.
        (self.repo / "README.md").write_text("local uncommitted edit\n")
        self.task("P1", extra='allowed = ["src/calc.py"]\n')
        self.task("P2", extra='allowed = ["src/extra.py"]\nverify = ["test -f src/extra.py"]\n')
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "P1")
        self.plan({"write": {"src/extra.py": "y = 2\n"}, "so": DONE})
        self.cli("run", "P2")
        self.cli("accept", "P1")
        self.cli("accept", "P2")
        self.assertEqual(sorted(self.git("diff", "--cached", "--name-only").split()), ["src/calc.py", "src/extra.py"])
        self.assertEqual((self.repo / "README.md").read_text(), "local uncommitted edit\n")
        self.assertEqual(self.git("worktree", "list").count("\n"), 1)

    def test_overlap_with_running_task(self):
        self.task("T12")
        other = self.repo / ".agy" / "runs" / "OTHER"
        other.mkdir(parents=True)
        (other / "state.json").write_text(json.dumps(
            {"id": "OTHER", "role": "implement", "state": "running", "pid": os.getpid(), "allowed": ["src/calc.py"]}))
        self.assertIn("scope conflict", self.cli("run", "T12", code=1))


class Containment(Base):
    PROBE_OK = {"write": {"inside.txt": "OK"}, "so": {"note": "hello"}}

    def test_unverified_agy_is_probed_once_and_then_trusted(self):
        record = self.containment(ok=None)
        self.task("C1")
        self.plan(*[self.PROBE_OK] * 8, {"write": {"src/calc.py": GOOD}, "so": DONE})
        out = self.cli("run", "C1")
        self.assertIn("probing", out)
        self.assertEqual(json.loads(record.read_text())["ok"], True)
        self.assertEqual(len(self.calls()), 9)  # 8 probes + the task
        self.assertEqual(self.state("C1")["state"], "review")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.assertNotIn("probing", self.cli("run", "C1", "--restart"))
        self.assertEqual(len(self.calls()), 1)

    def test_broken_containment_blocks_delegation(self):
        record = self.containment(ok=None)
        self.task("C2")
        # An agy that writes where it must not: outside the workspace and in read-only mode.
        self.plan({"write": {"inside.txt": "OK", "ro.txt": "OK", "../outside/escape.txt": "OK"}, "so": {"note": "hello"}})
        out = self.cli("run", "C2", code=4)
        self.assertIn("containment check failed for agy 0.0.0-fake", out)
        self.assertIn("writing outside the workspace is denied", out)
        self.assertIn("creating files is denied", out)
        self.assertEqual(json.loads(record.read_text())["ok"], False)
        self.assertEqual(self.git("worktree", "list").count("\n"), 1)  # nothing was delegated
        self.assertIn("pending", self.cli("status"))

    def test_failed_record_is_reprobed_on_explore_too(self):
        self.containment(ok=False)
        self.task("C3", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"so": {"note": "wrote nothing"}})  # it cannot even write inside: still broken
        self.assertIn("can write inside the workspace", self.cli("run", "C3", code=4))

    def test_doctor(self):
        self.assertIn("containment verified for agy 0.0.0-fake (", self.cli("doctor"))
        self.containment(ok=None)
        self.assertIn("containment not yet verified", self.cli("doctor"))
        self.plan(self.PROBE_OK)
        self.assertIn("containment verified for agy 0.0.0-fake.", self.cli("doctor", "--probe"))
        self.assertIn("✓ containment verified", self.cli("doctor"))


class Lifecycle(Base):
    def test_cancel_stops_agy_and_marks_the_task(self):
        self.task("L1")
        self.plan({"sleep": 60, "so": DONE})
        proc = subprocess.Popen([sys.executable, str(AGY_TASK), "run", "L1"], cwd=self.repo, env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        calls = Path(self.env["FAKE_AGY_PLAN"] + ".calls")
        deadline = time.time() + 20
        while not calls.exists() and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(calls.exists(), "agy was never launched")
        self.assertIn("running (alive)", self.cli("result", "L1"))
        self.assertIn("is already running", self.cli("run", "L1", code=1))
        self.assertIn("cancellation signal sent", self.cli("cancel", "L1"))
        self.assertEqual(proc.wait(timeout=30), 4)
        proc.communicate()
        st = self.state("L1")
        self.assertEqual((st["state"], st["reason"]), ("failed", "cancelled"))
        self.assertIn("is not running", self.cli("cancel", "L1"))

    def test_failed_result_shows_why_and_changed_files(self):
        self.task("L2", extra="max_fixups = 0\n")
        (self.repo / ".agy" / "config.toml").write_text("verify = ['echo failure-reason-xyz; exit 7']\n")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        out = self.cli("run", "L2", code=3)
        self.assertIn("tail of the failed verification:", out)
        self.assertIn("| failure-reason-xyz", out)
        self.assertIn("M src/calc.py", out)
        self.assertIn("no passing baseline verification", out)
        self.assertEqual(out, self.cli("result", "L2"))  # result reproduces exactly the same text

    def test_accepted_task_cannot_be_rejected(self):
        self.task("L3")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "L3")
        self.cli("accept", "L3")
        self.assertIn("was already accepted", self.cli("reject", "L3", code=1))
        self.assertEqual(self.state("L3")["state"], "accepted")
        self.assertIn("only a task in the review state", self.cli("accept", "L3", code=1))

    def test_accept_reports_missing_branch(self):
        self.task("L4")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "L4")
        self.git("worktree", "remove", "--force", self.state("L4")["worktree"])
        self.git("branch", "-D", "agy/L4")
        self.assertIn("the work of L4 was not found", self.cli("accept", "L4", code=4))

    def test_setup_failure_is_reported_before_calling_agy(self):
        (self.repo / ".agy" / "config.toml").write_text(f"verify = ['''{VERIFY}''']\nsetup = ['exit 9']\n")
        self.task("L5")
        self.plan({"so": DONE})
        out = self.cli("run", "L5", code=4)
        self.assertIn("FAILED (setup)", out)
        self.assertFalse(Path(self.env["FAKE_AGY_PLAN"] + ".calls").exists())

    def test_stats_and_version(self):
        self.assertIn("no runs recorded yet", self.cli("stats"))
        self.task("L6")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE}, {"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "L6")
        self.task("L7", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"so": {"status": "blocked", "summary": "cannot tell", "questions": ["which one?"], "findings": []}})
        self.cli("run", "L7", code=2)
        out = self.cli("stats")
        self.assertIn("sessions: 2", out)
        self.assertRegex(out, r"implement\s+1 sessions · ready: 1 \(first try: 0\)")
        self.assertRegex(out, r"explore\s+1 sessions · ready: 0 .* blocked: 1")
        self.assertRegex(self.cli("--version"), r"^agy-task \d+\.\d+\.\d+\n$")


class Validation(Base):
    def check_fails(self, tid, needle, **kw):
        self.task(tid, **kw)
        self.assertIn(needle, self.cli("check", tid, code=1))

    def test_rejections(self):
        self.check_fails("V1", "risk = high", risk="high")
        self.check_fails("V2", "Acceptance criteria", body="## Goal\nsomething\n")
        self.check_fails("V3", "placeholders", body="## Goal\n«fill in»\n\n## Acceptance criteria\n- x\n")
        self.check_fails("V4", "unknown keys", extra="alowed = ['x']\n")
        self.check_fails("V5", "path not allowed", extra="allowed = ['../outside/**']\n")
        self.check_fails("V7", "unknown keys", extra="commands = ['ls']\n")  # never a terminal
        self.check_fails("V10", "missing the '## Goal' section", body="## Objective\nx\n\n## Acceptance criteria\n- x\n")
        (self.repo / ".agy" / "config.toml").write_text("")
        self.check_fails("V6", "without automatic verification")

    def test_section_names_ignore_case(self):
        self.task("V11", body="## GOAL\nx\n\n## acceptance CRITERIA\n- x\n")
        self.assertIn("valid manual", self.cli("check", "V11"))

    def test_manual_tolerates_bom_and_leading_blank_lines(self):
        self.task("V8")
        path = self.repo / ".agy" / "tasks" / "V8.md"
        path.write_text("﻿\n\n" + path.read_text())
        self.assertIn("valid manual", self.cli("check", "V8"))

    def test_config_rejects_unknown_keys(self):
        (self.repo / ".agy" / "config.toml").write_text("verifi = ['x']\n")
        self.task("V9")
        self.assertIn("unknown keys: verifi", self.cli("check", "V9", code=1))

    def test_new_template_is_rejected_until_filled(self):
        self.cli("new", "N1", "--title", "something")
        self.assertIn("placeholders", self.cli("check", "N1", code=1))


class ReadOnlyRoles(Base):
    def test_explore(self):
        self.task("E1", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"so": {"status": "done", "summary": "in calc", "questions": [],
                          "findings": [{"path": "src/calc.py", "line": 1, "note": "definition"}]}})
        out = self.cli("run", "E1")
        self.assertIn("src/calc.py:1 — definition", out)
        call = self.calls()[0]
        self.assertEqual(call["cwd"], str(self.repo))
        settings = json.loads(call["argv"][call["argv"].index("--settings") + 1])
        self.assertEqual(settings["permissions"]["ask"], ["write_file(*)", "command(*)"])
        self.assertNotIn("--mode", call["argv"])
        self.assertEqual((settings["agentMode"], settings["toolPermission"]), ("", "request-review"))
        self.assertEqual(self.state("E1")["state"], "done")

    def test_explore_write_is_flagged(self):
        self.task("E2", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"write": {"src/intruder.py": "x = 1\n"},
                   "so": {"status": "done", "summary": "s", "questions": [], "findings": []}})
        out = self.cli("run", "E2")
        self.assertIn("tree_modified_during_read_only", out)

    def test_review_of_task(self):
        self.task("T1")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T1")
        self.task("R1", role="review", extra='target = "T1"\n', body="## Goal\nReview add.\n")
        self.plan({"so": {"status": "done", "verdict": "request_changes", "summary": "needs validation",
                          "questions": [],
                          "issues": [{"severity": "medium", "path": "src/calc.py", "line": 2, "note": "no types"}]}})
        out = self.cli("run", "R1")
        self.assertIn("verdict: request_changes", out)
        self.assertIn("[medium] src/calc.py:2", out)
        self.assertIn("return a + b", self.calls()[0]["argv"][-1])  # the diff travels in the prompt

    def test_review_of_uncommitted_changes(self):
        (self.repo / "src" / "calc.py").write_text(GOOD)
        self.task("R2", role="review", extra='target = "working"\n', body="## Goal\nReview add.\n")
        self.plan({"so": {"status": "done", "verdict": "approve", "summary": "fine", "questions": [], "issues": []}})
        out = self.cli("run", "R2")
        self.assertIn("verdict: approve", out)
        call = self.calls()[0]
        self.assertEqual(call["cwd"], str(self.repo))
        self.assertIn("+    return a + b", call["argv"][-1])

    def test_review_needs_something_to_review(self):
        self.task("R3", role="review", extra='target = "working"\n', body="## Goal\nReview.\n")
        self.assertIn("there are no changes to review", self.cli("run", "R3", code=1))
        self.task("R4", role="review", extra='target = "NOPE"\n', body="## Goal\nReview.\n")
        self.assertIn("has no active worktree", self.cli("run", "R4", code=1))

    def test_readonly_retries_after_denied_action(self):
        self.task("E3", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"denied": [{"action": "write_file", "display_name": "Edit"}]},
                  {"so": {"status": "done", "summary": "in calc", "questions": [], "findings": []}})
        self.cli("run", "E3")
        self.assertEqual((self.state("E3")["state"], self.state("E3")["attempts"]), ("done", 2))
        self.assertIn("read-only", self.calls()[1]["argv"][-1])

    def test_status_lists_tasks(self):
        self.task("T1")
        self.assertIn("pending", self.cli("status"))


class ShippedManuals(Base):
    def test_examples_are_valid_manuals(self):
        (self.repo / ".agy" / "config.toml").write_text("verify = ['true']\n")
        for example in sorted((HERE.parent / "examples").glob("[a-z]*.md")):
            text = example.read_text()
            tid = text.split('id = "')[1].split('"')[0]
            (self.repo / ".agy" / "tasks" / f"{tid}.md").write_text(text)
            self.assertIn("valid manual", self.cli("check", tid), example.name)

    def test_every_role_has_template_and_rules(self):
        for role in ("implement", "explore", "review"):
            self.cli("new", f"N-{role}", "--role", role, "--title", "t", "--target", "T-001")
            self.assertTrue((HERE.parent / "rules" / f"{role}.md").read_text().strip())

    def test_filled_templates_are_valid(self):
        # Replacing every «…» placeholder must be enough to get a valid manual.
        (self.repo / ".agy" / "config.toml").write_text("verify = ['true']\n")
        for role in ("implement", "explore", "review"):
            tid = f"F-{role}"
            self.cli("new", tid, "--role", role, "--title", "t", "--target", "T-001")
            path = self.repo / ".agy" / "tasks" / f"{tid}.md"
            path.write_text(path.read_text().replace("«", "").replace("»", ""))
            self.assertIn("valid manual", self.cli("check", tid), role)


class Launcher(unittest.TestCase):
    def test_skips_an_old_python_first_in_path(self):
        # On macOS the system python3 is 3.9 and is often first on the PATH.
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "python3"
            old.write_text("#!/bin/sh\nexit 1\n")
            old.chmod(0o755)
            real = Path(tmp) / "real"
            real.mkdir()
            name = f"python3.{sys.version_info.minor}"
            (real / name).symlink_to(sys.executable)
            env = {"PATH": f"{tmp}:{real}:/usr/bin:/bin", "HOME": tmp}
            p = subprocess.run([str(LAUNCHER), "--version"], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertRegex(p.stdout, r"^agy-task \d+\.\d+\.\d+")
            link = Path(tmp) / "link"
            link.symlink_to(LAUNCHER)  # installed as a symlink, the way install.sh does it
            p = subprocess.run([str(link), "--version"], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 0, p.stderr)

    def test_reports_when_no_suitable_python_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "AGY_BRIDGE_PYTHON": "/bin/sh"}
            p = subprocess.run([str(LAUNCHER), "--version"], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 1)
            self.assertIn("is not a Python >= 3.11", p.stderr)


class Globs(unittest.TestCase):
    def test_matching(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("agy_task", str(AGY_TASK))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("agy_task", loader))
        loader.exec_module(mod)
        m = mod.matches
        self.assertTrue(m("src/a/b.py", ["src/**"]))
        self.assertTrue(m("src/a/b.py", ["src"]))
        self.assertTrue(m("src/a/b.py", ["src/"]))
        self.assertTrue(m("src/a/b.py", ["**/*.py"]))
        self.assertTrue(m("b.py", ["**/*.py"]))
        self.assertFalse(m("src/a/b.py", ["src/*.py"]))
        self.assertFalse(m("srcx/b.py", ["src/**"]))
        self.assertFalse(m("src/b.pyc", ["src/*.py"]))
        self.assertTrue(mod.patterns_overlap(["src/**"], ["src/a/x.py"]))
        self.assertIsNone(mod.patterns_overlap(["src/a/**"], ["src/b/**"]))


if __name__ == "__main__":
    unittest.main(verbosity=1)
