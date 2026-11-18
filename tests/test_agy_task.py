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

DONE = {"status": "done", "summary": "done", "files_changed": [], "decisions": [], "questions": [],
        "recommendations": []}
GOOD = "def add(a, b):\n    return a + b\n"
BAD = "def add(a, b):\n    return a - b\n"
# Git identity for the tests: CI machines do not have one configured.
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
VERIFY = "python3 -c \"import sys; sys.path.insert(0, 'src'); import calc; assert calc.add(2, 3) == 5\""


def brief(tid, role="implement", risk="low", extra="", body=None):
    head = f'id = "{tid}"\ntitle = "task {tid}"\nrole = "{role}"\nrisk = "{risk}"\n{extra}'
    if role == "implement" and "allowed" not in extra:
        head += 'allowed = ["src/**"]\nprotected = ["tests/**"]\n'
    body = body or "## Goal\nImplement add.\n\n## Acceptance criteria\n- add(2, 3) == 5\n"
    return f"+++\n{head}+++\n\n{body}"


def report(**kw):
    """A read-only report (explore, review, grill, answers) with every list present."""
    return {"status": "done", "summary": "s", "questions": [], "recommendations": [], **kw}


class Base(unittest.TestCase):
    MODE = "collaborative"

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
        self.config(f"verify = ['''{VERIFY}''']")
        self.containment(ok=True)

    def config(self, text):
        (self.repo / ".agy" / "config.toml").write_text(f"mode = '{self.MODE}'\n{text}\n")

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
        (self.repo / ".agy" / "tasks" / f"{tid}.md").write_text(brief(tid, **kw))

    def state(self, tid):
        return json.loads((self.repo / ".agy" / "runs" / tid / "state.json").read_text())

    def delivered(self, tid="T1"):
        """Runs an implement task that agy completes correctly on the first attempt."""
        self.task(tid)
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", tid)
        return self.state(tid)


def settings_of(call):
    return json.loads(call["argv"][call["argv"].index("--settings") + 1])


class Implement(Base):
    """Behaviour shared by both modes, exercised in the default collaborative mode."""

    def test_happy_path_and_accept(self):
        st = self.delivered()
        self.assertEqual((st["state"], st["review_level"], st["attempts"], st["mode"]),
                         ("review", "summary", 1, "collaborative"))
        call = self.calls()[0]
        self.assertEqual(call["cwd"], st["worktree"])
        self.assertNotEqual(Path(st["worktree"]), self.repo)
        self.assertIn("--dangerously-skip-permissions", call["argv"])
        self.assertNotIn("--settings", call["argv"])
        self.assertIn("## Brief for task T1", call["argv"][-1])
        self.assertIn("Do not commit, push", call["argv"][-1])
        self.assertNotIn("File map", call["argv"][-1])
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

    def test_verify_failure_triggers_fixup(self):
        self.task("T3", risk="medium")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE}, {"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T3")
        st = self.state("T3")
        self.assertEqual((st["state"], st["attempts"], st["review_level"]), ("review", 2, "diff"))
        second = self.calls()[1]["argv"]
        self.assertEqual(second[second.index("--conversation") + 1], "conv-fake")
        self.assertIn("The senior's verification failed", second[-1])

    def test_verify_never_passes_then_fix(self):
        self.task("T4", extra="max_fixups = 1\n")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        out = self.cli("run", "T4", code=3)
        self.assertIn("FAILED (gates)", out)
        self.assertEqual(self.state("T4")["attempts"], 2)
        self.cli("accept", "T4", code=1)
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("fix", "T4", "use addition, not subtraction")
        st = self.state("T4")
        self.assertEqual((st["state"], st["attempts"]), ("review", 3))  # attempts accumulate across sessions
        self.assertLess(st["active_secs"], 60)  # work time, not wall-clock time since the first run
        rows = [json.loads(l) for l in (self.repo / ".agy" / "runs" / "usage.jsonl").read_text().splitlines()]
        self.assertEqual([(r["id"], r["input"]) for r in rows], [("T4", 200), ("T4", 100)])  # per session
        self.assertEqual(st["usage"]["input"], 300)
        prompt = self.calls()[0]["argv"][-1]
        self.assertIn("use addition, not subtraction", prompt)
        self.assertIn("It is an instruction", prompt)

    def test_blocked_then_fix(self):
        self.task("T5")
        self.plan({"so": dict(DONE, status="blocked", questions=["integers or floats?"])})
        out = self.cli("run", "T5", code=2)
        self.assertIn("integers or floats?", out)
        self.assertIn("BLOCKED (questions)", out)
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("fix", "T5", "integers")
        self.assertEqual(self.state("T5")["state"], "review")

    def test_missing_report_is_retried(self):
        self.task("T6")
        self.plan({"write": {"src/calc.py": GOOD}}, {"so": DONE})
        self.cli("run", "T6")
        self.assertEqual(self.state("T6")["attempts"], 2)
        self.assertIn("did not deliver the structured report", self.calls()[1]["argv"][-1])

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
        wt = Path(self.delivered("T9")["worktree"])
        self.cli("reject", "T9", "--reason", "not convinced")
        self.assertFalse(wt.exists())
        self.assertEqual(self.state("T9")["state"], "rejected")
        self.assertEqual(self.git("status", "--porcelain", "--", "src").strip(), "")

    def test_linked_dependencies_stay_out_of_the_diff(self):
        (self.repo / "deps").mkdir()
        (self.repo / "deps" / "lib.py").write_text("x = 1\n")
        (self.repo / ".gitignore").write_text("deps/\n")
        self.git("add", ".gitignore")
        self.git("commit", "-qm", "ignore")
        self.config(f"verify = ['''{VERIFY}''', 'test -f deps/lib.py']\nlink = ['deps']")
        st = self.delivered("T10")
        self.assertEqual(st["links"], ["deps"])
        self.assertEqual(all_notes(st), [])
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertIn("deps", self.calls()[0]["argv"][-1].split("Paths shared with the main project through symlinks")[1])

    def test_accept_conflict_leaves_project_intact(self):
        self.delivered("T11")
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    return 0  # local change\n")
        self.assertIn("could not integrate", self.cli("accept", "T11", code=3))
        self.assertIn("local change", (self.repo / "src" / "calc.py").read_text())
        self.assertEqual(self.state("T11")["state"], "review")

    def test_seed_files_reach_agy_but_stay_out_of_the_diff(self):
        seed = self.repo / "tests" / "test_add.py"
        seed.write_text("import sys; sys.path.insert(0, 'src')\nimport calc\nassert calc.add(2, 3) == 5\n")
        self.config("verify = ['python3 tests/test_add.py']")
        self.task("S1", extra='allowed = ["src/**"]\nseed = ["tests/test_add.py"]\n')
        self.plan({"write": {"src/calc.py": BAD, "tests/test_add.py": "assert True\n"}, "so": DONE},
                  {"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "S1")
        st = self.state("S1")
        self.assertEqual((st["state"], st["attempts"]), ("review", 2))
        self.assertEqual([(i["kind"], i["path"]) for i in st["incidents"]],
                         [("supervisor_file_modified", "tests/test_add.py")])
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertIn("were restored: tests/test_add.py", self.calls()[1]["argv"][-1])
        self.cli("accept", "S1", "--reviewed")
        self.assertEqual(self.git("diff", "--cached", "--name-only").split(), ["src/calc.py"])
        self.assertIn("calc.add(2, 3) == 5", seed.read_text())  # Claude's test is still intact

    def test_seed_must_exist(self):
        self.task("S2", extra='allowed = ["src/**"]\nseed = ["tests/nope.py"]\n')
        self.assertIn("is not an existing file", self.cli("check", "S2", code=1))

    def test_autofix_runs_before_gates(self):
        fixer = "python3 -c \"import pathlib; p = pathlib.Path('src/calc.py'); p.write_text(p.read_text().replace('a - b', 'a + b'))\""
        self.config(f"verify = [\'\'\'{VERIFY}\'\'\']\nautofix = [\'\'\'{fixer}\'\'\']")
        self.task("A1")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        self.cli("run", "A1")
        self.assertEqual((self.state("A1")["state"], self.state("A1")["attempts"]), ("review", 1))
        self.assertIn("return a + b", self.cli("diff", "A1"))

    def test_baseline(self):
        self.assertIn("BASELINE VERIFICATION FAILS", self.cli("baseline", code=3))  # add does not exist yet
        self.config("verify = ['test -f src/calc.py']")
        self.assertIn("baseline verification passed", self.cli("baseline"))
        self.assertEqual(self.git("worktree", "list").count("\n"), 1)  # leaves no worktrees behind

    def test_accept_several_tasks_in_a_row(self):
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

    def test_recommendations_reach_the_result(self):
        self.task("T13")
        self.plan({"write": {"src/calc.py": GOOD}, "so": dict(DONE, recommendations=["validate input types"])})
        out = self.cli("run", "T13")
        self.assertIn("agy recommendations:\n  - validate input types", out)


def all_notes(st):
    return st.get("incidents", []) + st.get("scope_notes", [])


class Collaborative(Base):
    """What changes when agy works freely: audit instead of revert, git coexistence, artifacts."""

    def test_work_outside_the_agreement_is_audited_not_reverted(self):
        self.task("C1")
        self.plan({"write": {"src/calc.py": GOOD, "README.md": "improved\n", "tests/test_calc.py": "# edited\n"},
                   "so": DONE})
        out = self.cli("run", "C1")
        st = self.state("C1")
        self.assertEqual(sorted(f["path"] for f in st["files"]), ["README.md", "src/calc.py", "tests/test_calc.py"])
        self.assertEqual(sorted((n["kind"], n["path"]) for n in st["scope_notes"]),
                         [("outside_agreed_area", "README.md"), ("protected_modified", "tests/test_calc.py")])
        self.assertIn("audit (2):", out)
        self.assertEqual(st["review_level"], "diff")
        self.assertIn("--reviewed", self.cli("accept", "C1", code=1))
        self.cli("accept", "C1", "--reviewed")
        self.assertEqual((self.repo / "README.md").read_text(), "improved\n")

    def test_audit_reflects_the_final_diff(self):
        self.task("C2")
        self.plan({"write": {"src/calc.py": BAD, "README.md": "draft\n"}, "so": DONE},
                  {"write": {"src/calc.py": GOOD, "README.md": "project\n"}, "so": DONE})
        self.cli("run", "C2")
        st = self.state("C2")
        self.assertEqual((st["state"], st["scope_notes"], st["review_level"]), ("review", [], "summary"))

    def test_executor_area_is_restored(self):
        self.task("C3")
        self.plan({"write": {"src/calc.py": GOOD, ".agy/tasks/X.md": "hijack\n"}, "so": DONE})
        self.cli("run", "C3")
        st = self.state("C3")
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertIn(("executor_area_restored", ".agy/tasks/X.md"),
                      [(n["kind"], n["path"]) for n in st["scope_notes"]])

    def test_build_artifacts_never_enter_the_diff(self):
        self.config(f"verify = ['''{VERIFY}''']\nartifacts = ['**/*.log']")
        self.task("C4")
        self.plan({"write": {"src/calc.py": GOOD, "src/__pycache__/calc.cpython-313.pyc": "x",
                             ".pytest_cache/v/cache": "x", "src/debug.log": "x"}, "so": DONE})
        self.cli("run", "C4")
        st = self.state("C4")
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertEqual(st["review_level"], "summary")

    def test_commits_made_by_agy_are_folded_back(self):
        self.task("C5")
        self.plan({"write": {"src/calc.py": GOOD},
                   "run": ["git add -A", "git -c user.name=a -c user.email=a@a commit -qm wip"], "so": DONE})
        out = self.cli("run", "C5")
        st = self.state("C5")
        self.assertEqual(st["state"], "review")
        self.assertIn("agy_committed", out)
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.cli("accept", "C5", "--reviewed")
        self.assertEqual((self.repo / "src" / "calc.py").read_text(), GOOD)

    def test_leaving_the_task_branch_fails(self):
        self.task("C6")
        self.plan({"write": {"src/calc.py": GOOD}, "run": ["git checkout -q -b elsewhere"], "so": DONE})
        out = self.cli("run", "C6", code=4)
        self.assertIn("FAILED (git)", out)
        self.assertIn("branch_changed", out)

    def test_no_containment_probe_is_needed(self):
        self.containment(ok=None)
        self.delivered("C7")
        self.assertEqual(len(self.calls()), 1)

    def test_recommend_declined_keeps_the_work(self):
        self.delivered("T1")
        self.plan({"so": dict(DONE, suggestion={"decision": "declined", "reason": "the API must stay stable"})})
        out = self.cli("recommend", "T1", "consider operator.add")
        self.assertIn("suggestion: declined — the API must stay stable", out)
        argv = self.calls()[0]["argv"]
        self.assertIn("It is not an order", argv[-1])
        self.assertEqual(argv[argv.index("--conversation") + 1], "conv-fake")
        self.assertEqual(self.state("T1")["state"], "review")
        self.assertIn("return a + b", self.cli("diff", "T1"))

    def test_recommend_adopted_changes_the_work(self):
        self.delivered("T1")
        adopted = "import operator\n\n\ndef add(a, b):\n    return operator.add(a, b)\n"
        self.plan({"write": {"src/calc.py": adopted},
                   "so": dict(DONE, suggestion={"decision": "adopted", "reason": "clearer"})})
        out = self.cli("recommend", "T1", "consider operator.add")
        self.assertIn("suggestion: adopted — clearer", out)
        self.assertIn("operator.add", self.cli("diff", "T1"))

    def test_recommend_only_applies_to_implement(self):
        self.task("E1", role="explore", body="## Goal\nWhere is add?\n")
        self.assertIn("use reply", self.cli("recommend", "E1", "x", code=1))


class Conversations(Base):
    """grill in both directions and reply."""

    OBJECTION = {"severity": "medium", "claim": "add is pure", "challenge": "it raises today",
                 "evidence": "src/calc.py:2 raises NotImplementedError", "path": "src/calc.py", "line": 2}

    def test_agy_grills_a_claim_and_the_senior_replies(self):
        self.plan({"so": report(verdict="concerns", objections=[self.OBJECTION])})
        out = self.cli("grill", "--text", "add is pure", "--focus", "side effects")
        self.assertIn("# G-001 · grill · DONE", out)
        self.assertIn("verdict: concerns", out)
        self.assertIn("[medium] add is pure — it raises today (src/calc.py:2)", out)
        self.assertIn("evidence: src/calc.py:2 raises NotImplementedError", out)
        self.assertIn("agy-task reply G-001", out)
        call = self.calls()[0]
        self.assertEqual(call["cwd"], str(self.repo))
        self.assertIn("--dangerously-skip-permissions", call["argv"])
        self.assertIn("## Material to challenge — a statement from the senior", call["argv"][-1])
        self.assertIn("side effects", call["argv"][-1])
        self.assertIn("gemini-4-argon-high", call["argv"])
        self.plan({"so": report(verdict="sound", objections=[], summary="dropped: it is a stub by design")})
        out = self.cli("reply", "G-001", "it is a stub until T1 lands")
        self.assertIn("verdict: sound", out)
        self.assertIn("no objections stood", out)
        argv = self.calls()[0]["argv"]
        self.assertEqual(argv[argv.index("--conversation") + 1], "conv-fake")
        self.assertIn("Keep only the objections that still stand", argv[-1])
        self.assertEqual(self.state("G-001")["attempts"], 2)

    def test_grill_a_plan_file_and_number_runs(self):
        plan = self.tmp / "plan.md"
        plan.write_text("1. Replace add with a lookup table.\n")
        self.plan({"so": report(verdict="unsound", objections=[dict(self.OBJECTION, severity="high")])})
        self.cli("grill", "--file", str(plan))
        self.assertIn("lookup table", self.calls()[0]["argv"][-1])
        self.cli("grill", "--file", str(plan))
        self.assertTrue((self.repo / ".agy" / "runs" / "G-002").is_dir())

    def test_grill_working_changes(self):
        self.assertIn("no uncommitted changes", self.cli("grill", "--working", code=1))
        (self.repo / "src" / "calc.py").write_text(GOOD)
        (self.repo / "src" / "new.py").write_text("x = 1\n")
        self.plan({"so": report(verdict="sound", objections=[])})
        self.cli("grill", "--working")
        prompt = self.calls()[0]["argv"][-1]
        self.assertIn("+    return a + b", prompt)
        self.assertIn("src/new.py", prompt)

    def test_grill_needs_exactly_one_source(self):
        self.assertIn("say what agy should challenge", self.cli("grill", code=1))
        self.assertIn("not both", self.cli("grill", "T1", "q", "--text", "x", code=1))

    def test_senior_grills_the_junior_about_a_task(self):
        st = self.delivered("T1")
        self.plan({"write": {"src/calc.py": BAD},  # it must not change anything: the executor restores it
                   "so": report(answers=[{"question": "why +?", "answer": "the spec says sum",
                                          "evidence": "brief, acceptance criteria"}])})
        out = self.cli("grill", "T1", "why +?")
        self.assertIn("# T1-q1 · answers · DONE", out)
        self.assertIn("  - Q: why +?\n    A: the spec says sum", out)
        self.assertIn("restored to the verified commit of T1", out)
        call = self.calls()[0]
        self.assertEqual(call["cwd"], st["worktree"])
        self.assertEqual(call["argv"][call["argv"].index("--conversation") + 1], "conv-fake")
        self.assertIn("do not modify any file", call["argv"][-1])
        self.assertEqual((Path(st["worktree"]) / "src" / "calc.py").read_text(), GOOD)
        self.assertEqual(self.state("T1")["state"], "review")
        self.assertIn("back to the task: agy-task accept|fix|recommend T1", out)
        self.plan({"so": report(answers=[])})
        self.cli("grill", "T1", "anything else?")
        self.assertTrue((self.repo / ".agy" / "runs" / "T1-q2").is_dir())

    def test_reply_rules(self):
        self.delivered("T1")
        self.assertIn("use fix", self.cli("reply", "T1", "x", code=1))
        self.assertIn("has not been run", self.cli("reply", "NOPE", "x", code=1))

    def test_explore_follow_up(self):
        self.task("E1", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"so": report(findings=[{"path": "src/calc.py", "line": 1, "note": "definition"}])})
        self.assertIn("agy-task reply E1", self.cli("run", "E1"))
        self.plan({"so": report(findings=[], summary="only one definition")})
        self.assertIn("only one definition", self.cli("reply", "E1", "any other definitions?"))


class TeamSkills(Base):
    """`skills`: the same skill files Claude follows reach agy at the start of every session."""

    SKILL = "---\nname: tidy\ndescription: x\n---\n\n# Tidy\nThe smallest complete change.\n"

    def user_config(self, text):
        (self.tmp / "home").mkdir(exist_ok=True)
        (self.tmp / "home" / "config.toml").write_text(text + "\n")

    def test_user_skills_reach_fresh_sessions_only(self):
        skill = self.tmp / "tidy.md"
        skill.write_text(self.SKILL)
        self.user_config(f"skills = ['{skill}']")
        self.delivered()
        prompt = self.calls()[0]["argv"][-1]
        self.assertIn("## Team skills", prompt)
        self.assertIn("The smallest complete change.", prompt)
        self.assertNotIn("description: x", prompt)
        self.plan({"so": DONE})
        self.cli("fix", "T1", "rename nothing")
        self.assertNotIn("## Team skills", self.calls()[0]["argv"][-1])
        self.plan({"so": report(verdict="sound", objections=[])})
        self.cli("grill", "--text", "add is pure")
        self.assertIn("The smallest complete change.", self.calls()[0]["argv"][-1])

    def test_named_skill_resolves_to_claude_skills_and_project_can_opt_out(self):
        home = self.tmp / "user"
        (home / ".claude" / "skills" / "tidy").mkdir(parents=True)
        (home / ".claude" / "skills" / "tidy" / "SKILL.md").write_text(self.SKILL)
        self.env["HOME"] = str(home)
        self.user_config("skills = ['tidy']")
        self.assertIn("team skill tidy:", self.cli("doctor"))
        self.delivered()
        self.assertIn("### Skill: tidy", self.calls()[0]["argv"][-1])
        self.config(f"verify = ['''{VERIFY}''']\nskills = []")
        self.delivered("T2")
        self.assertNotIn("## Team skills", self.calls()[0]["argv"][-1])

    def test_missing_skill_stops_before_agy(self):
        self.user_config("skills = ['nope.md']")
        self.task("T1")
        self.plan({"so": DONE})
        self.assertIn("skill 'nope.md' not found", self.cli("run", "T1", code=1))


class Strict(Base):
    """The strict mode: no terminal, everything outside scope reverted, containment probed."""
    MODE = "strict"

    def test_happy_path_uses_session_permissions(self):
        st = self.delivered()
        call = self.calls()[0]
        settings = settings_of(call)
        self.assertFalse(settings["allowNonWorkspaceAccess"])
        self.assertEqual(settings["permissions"]["allow"], [])
        self.assertIn("accept-edits", call["argv"])
        self.assertNotIn("--dangerously-skip-permissions", call["argv"])
        self.assertIn("src/calc.py", call["argv"][-1].split("## File map")[1])
        self.assertEqual((st["state"], st["review_level"]), ("review", "summary"))

    def test_out_of_scope_and_protected_are_reverted(self):
        self.task("T2")
        self.plan({"write": {"src/calc.py": GOOD, "README.md": "hacked\n", "tests/test_calc.py": "assert True\n",
                             "extra.txt": "x\n"}, "so": DONE})
        out = self.cli("run", "T2")
        st = self.state("T2")
        kinds = sorted((i["kind"], i["path"]) for i in st["incidents"])
        self.assertEqual(kinds, [("out_of_scope", "README.md"), ("out_of_scope", "extra.txt"),
                                 ("protected_modified", "tests/test_calc.py")])
        self.assertIn("incidents (3):", out)
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.cli("accept", "T2", "--reviewed")
        self.assertEqual((self.repo / "README.md").read_text(), "project\n")

    def test_denied_action_is_retried(self):
        self.task("T6")
        self.plan({"denied": [{"action": "command", "display_name": "Bash"}]}, {"write": {"src/calc.py": GOOD}},
                  {"so": DONE})
        self.cli("run", "T6")
        self.assertEqual((self.state("T6")["state"], self.state("T6")["attempts"]), ("review", 3))
        self.assertIn("action that is not allowed", self.calls()[1]["argv"][-1])

    def test_search_results_are_embedded(self):
        self.task("Q1", extra='allowed = ["src/**"]\nsearch = ["NotImplementedError", "does-not-exist-zzz"]\n')
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "Q1")
        prompt = self.calls()[0]["argv"][-1]
        self.assertIn("src/calc.py:2:    raise NotImplementedError", prompt)
        self.assertIn("`does-not-exist-zzz` — 0 match(es)", prompt)

    def test_file_map_omits_media(self):
        (self.repo / "photo.PNG").write_bytes(b"x")
        (self.repo / "src" / ".gitkeep").write_text("")
        self.git("add", "-A")
        self.git("commit", "-qm", "media")
        self.delivered("M1")
        fmap = self.calls()[0]["argv"][-1].split("## File map")[1]
        self.assertNotIn("photo.PNG", fmap)
        self.assertIn("2 media, binary or placeholder files omitted", fmap)

    def test_readonly_sessions_use_read_only_permissions(self):
        self.task("E1", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"so": report(findings=[])})
        self.cli("run", "E1")
        call = self.calls()[0]
        settings = settings_of(call)
        self.assertEqual(settings["permissions"]["ask"], ["write_file(*)", "command(*)"])
        self.assertEqual((settings["agentMode"], settings["toolPermission"]), ("", "request-review"))
        self.assertNotIn("--mode", call["argv"])
        self.assertIn("## File map", call["argv"][-1])

    def test_explore_new_file_is_flagged(self):
        self.task("E2", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"write": {"src/intruder.py": "x = 1\n"}, "so": report(findings=[])})
        self.assertIn("tree_modified_during_read_only", self.cli("run", "E2"))


class Containment(Base):
    MODE = "strict"
    PROBE_OK = {"write": {"inside.txt": "OK"}, "so": {"note": "hello"}}

    def test_unverified_agy_is_probed_once_and_then_trusted(self):
        record = self.containment(ok=None)
        self.task("C1")
        self.plan(*[self.PROBE_OK] * 8, {"write": {"src/calc.py": GOOD}, "so": DONE})
        out = self.cli("run", "C1")
        self.assertIn("probing", out)
        self.assertEqual(json.loads(record.read_text())["ok"], True)
        self.assertEqual(len(self.calls()), 9)  # 8 probes + the task
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.assertNotIn("probing", self.cli("run", "C1", "--restart"))
        self.assertEqual(len(self.calls()), 1)

    def test_broken_containment_blocks_delegation(self):
        record = self.containment(ok=None)
        self.task("C2")
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
        self.assertIn("strict-mode containment verified for agy 0.0.0-fake (", self.cli("doctor"))
        self.containment(ok=None)
        self.assertIn("containment not yet verified", self.cli("doctor"))
        self.plan(self.PROBE_OK)
        self.assertIn("strict-mode containment verified for agy 0.0.0-fake.", self.cli("doctor", "--probe"))


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
        self.config("verify = ['echo failure-reason-xyz; exit 7']")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        out = self.cli("run", "L2", code=3)
        self.assertIn("tail of the failed verification:", out)
        self.assertIn("| failure-reason-xyz", out)
        self.assertIn("M src/calc.py", out)
        self.assertIn("no passing baseline verification", out)
        self.assertEqual(out, self.cli("result", "L2"))  # result reproduces exactly the same text

    def test_accepted_task_cannot_be_rejected(self):
        self.delivered("L3")
        self.cli("accept", "L3")
        self.assertIn("was already accepted", self.cli("reject", "L3", code=1))
        self.assertEqual(self.state("L3")["state"], "accepted")
        self.assertIn("only a task in the review state", self.cli("accept", "L3", code=1))

    def test_accept_reports_missing_branch(self):
        self.delivered("L4")
        self.git("worktree", "remove", "--force", self.state("L4")["worktree"])
        self.git("branch", "-D", "agy/L4")
        self.assertIn("the work of L4 was not found", self.cli("accept", "L4", code=4))

    def test_setup_failure_is_reported_before_calling_agy(self):
        self.config(f"verify = ['''{VERIFY}''']\nsetup = ['exit 9']")
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
        self.plan({"so": report(status="blocked", questions=["which one?"], findings=[])})
        self.cli("run", "L7", code=2)
        self.plan({"so": report(verdict="sound", objections=[])})
        self.cli("grill", "--text", "x")
        out = self.cli("stats")
        self.assertIn("sessions: 3", out)
        self.assertRegex(out, r"implement\s+1 sessions · ready: 1 \(first try: 0\)")
        self.assertRegex(out, r"explore\s+1 sessions · ready: 0 .* blocked: 1")
        self.assertRegex(out, r"grill\s+1 sessions · ready: 1")
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
        self.check_fails("V7", "unknown keys", extra="commands = ['ls']\n")
        self.check_fails("V10", "missing the '## Goal' section", body="## Objective\nx\n\n## Acceptance criteria\n- x\n")
        self.config("")
        self.check_fails("V6", "without verification")

    def test_section_names_ignore_case(self):
        self.task("V11", body="## GOAL\nx\n\n## acceptance CRITERIA\n- x\n")
        self.assertIn("valid brief", self.cli("check", "V11"))

    def test_manual_tolerates_bom_and_leading_blank_lines(self):
        self.task("V8")
        path = self.repo / ".agy" / "tasks" / "V8.md"
        path.write_text("﻿\n\n" + path.read_text())
        self.assertIn("valid brief", self.cli("check", "V8"))

    def test_config_rejects_unknown_keys_and_modes(self):
        self.task("V9")
        (self.repo / ".agy" / "config.toml").write_text("verifi = ['x']\n")
        self.assertIn("unknown keys: verifi", self.cli("check", "V9", code=1))
        (self.repo / ".agy" / "config.toml").write_text("mode = 'free'\nverify = ['true']\n")
        self.assertIn("mode must be one of", self.cli("check", "V9", code=1))

    def test_new_template_is_rejected_until_filled(self):
        self.cli("new", "N1", "--title", "something")
        self.assertIn("placeholders", self.cli("check", "N1", code=1))


class ReadOnlyRoles(Base):
    def test_explore(self):
        self.task("E1", role="explore", body="## Goal\nWhere is add defined?\n", extra='search = ["add"]\n')
        self.plan({"so": report(findings=[{"path": "src/calc.py", "line": 1, "note": "definition"}])})
        out = self.cli("run", "E1")
        self.assertIn("src/calc.py:1 — definition", out)
        call = self.calls()[0]
        self.assertEqual(call["cwd"], str(self.repo))
        self.assertIn("--dangerously-skip-permissions", call["argv"])
        self.assertIn("Useful starting points", call["argv"][-1])
        self.assertIn("gemini-4-hydrogen-high", call["argv"])
        self.assertEqual(self.state("E1")["state"], "done")

    def test_explore_edit_is_flagged(self):
        self.task("E2", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"write": {"src/calc.py": GOOD}, "so": report(findings=[])})
        self.assertIn("tree_modified_during_read_only", self.cli("run", "E2"))

    def test_explore_test_artifacts_are_not_flagged(self):
        self.task("E3", role="explore", body="## Goal\nWhere is add defined?\n")
        self.plan({"write": {"src/__pycache__/calc.pyc": "x"}, "so": report(findings=[])})
        self.assertNotIn("tree_modified", self.cli("run", "E3"))

    def test_review_of_task(self):
        st = self.delivered("T1")
        self.task("R1", role="review", extra='target = "T1"\n', body="## Goal\nReview add.\n")
        self.plan({"write": {"src/calc.py": BAD},  # a reviewer must not change the task: it is restored
                   "so": report(verdict="request_changes",
                                issues=[{"severity": "medium", "path": "src/calc.py", "line": 2, "note": "no types"}])})
        out = self.cli("run", "R1")
        self.assertIn("verdict: request_changes", out)
        self.assertIn("[medium] src/calc.py:2", out)
        self.assertIn("return a + b", self.calls()[0]["argv"][-1])  # the diff travels in the prompt
        self.assertEqual((Path(st["worktree"]) / "src" / "calc.py").read_text(), GOOD)

    def test_review_of_uncommitted_changes(self):
        (self.repo / "src" / "calc.py").write_text(GOOD)
        self.task("R2", role="review", extra='target = "working"\n', body="## Goal\nReview add.\n")
        self.plan({"so": report(verdict="approve", issues=[])})
        out = self.cli("run", "R2")
        self.assertIn("verdict: approve", out)
        self.assertIn("+    return a + b", self.calls()[0]["argv"][-1])

    def test_review_needs_something_to_review(self):
        self.task("R3", role="review", extra='target = "working"\n', body="## Goal\nReview.\n")
        self.assertIn("there are no changes to review", self.cli("run", "R3", code=1))
        self.task("R4", role="review", extra='target = "NOPE"\n', body="## Goal\nReview.\n")
        self.assertIn("has no active worktree", self.cli("run", "R4", code=1))

    def test_status_lists_tasks(self):
        self.task("T1")
        self.assertIn("pending", self.cli("status"))


class ShippedManuals(Base):
    def test_examples_are_valid_manuals(self):
        self.config("verify = ['true']")
        for example in sorted((HERE.parent / "examples").glob("[a-z]*.md")):
            text = example.read_text()
            tid = text.split('id = "')[1].split('"')[0]
            (self.repo / ".agy" / "tasks" / f"{tid}.md").write_text(text)
            self.assertIn("valid brief", self.cli("check", tid), example.name)

    def test_every_role_has_template_and_rules(self):
        for role in ("implement", "explore", "review"):
            self.cli("new", f"N-{role}", "--role", role, "--title", "t", "--target", "T-001")
            for mode in ("collaborative", "strict"):
                self.assertTrue((HERE.parent / "rules" / mode / f"{role}.md").read_text().strip())
        self.assertTrue((HERE.parent / "rules" / "collaborative" / "grill.md").read_text().strip())

    def test_filled_templates_are_valid(self):
        self.config("verify = ['true']")
        for role in ("implement", "explore", "review"):
            tid = f"F-{role}"
            self.cli("new", tid, "--role", role, "--title", "t", "--target", "T-001")
            path = self.repo / ".agy" / "tasks" / f"{tid}.md"
            path.write_text(path.read_text().replace("«", "").replace("»", ""))
            self.assertIn("valid brief", self.cli("check", tid), role)


class Launcher(unittest.TestCase):
    def test_skips_an_old_python_first_in_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "python3"
            old.write_text("#!/bin/sh\nexit 1\n")
            old.chmod(0o755)
            real = Path(tmp) / "real"
            real.mkdir()
            (real / f"python3.{sys.version_info.minor}").symlink_to(sys.executable)
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
