#!/usr/bin/env python3
"""Pruebas de agy-task con un agy simulado. Ejecutar: python3 tests/test_agy_task.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGY_TASK = HERE.parent / "bin" / "agy-task"
FAKE = HERE / "fake_agy"

DONE = {"status": "done", "summary": "hecho", "files_changed": [], "decisions": [], "questions": []}
GOOD = "def add(a, b):\n    return a + b\n"
BAD = "def add(a, b):\n    return a - b\n"
VERIFY = "python3 -c \"import sys; sys.path.insert(0, 'src'); import calc; assert calc.add(2, 3) == 5\""


def manual(tid, role="implement", risk="low", extra="", body=None):
    head = f'id = "{tid}"\ntitle = "tarea {tid}"\nrole = "{role}"\nrisk = "{risk}"\n{extra}'
    if role == "implement" and "allowed" not in extra:
        head += 'allowed = ["src/**"]\nprotected = ["tests/**"]\n'
    body = body or "## Objetivo\nImplementar add.\n\n## Criterios de aceptación\n- add(2, 3) == 5\n"
    return f"+++\n{head}+++\n\n{body}"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agytest-")).resolve()
        self.repo = self.tmp / "proj"
        (self.repo / "src").mkdir(parents=True)
        (self.repo / "tests").mkdir()
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    raise NotImplementedError\n")
        (self.repo / "tests" / "test_calc.py").write_text("# test protegido\n")
        (self.repo / "README.md").write_text("proyecto\n")
        self.git("init", "-q")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
        self.env = dict(os.environ, AGY_BIN=str(FAKE), AGY_BRIDGE_HOME=str(self.tmp / "home"),
                        FAKE_AGY_PLAN=str(self.tmp / "plan.json"),
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        self.cli("init")
        (self.repo / ".agy" / "config.toml").write_text(f"verify = ['''{VERIFY}''']\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a], capture_output=True, text=True, check=True).stdout

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
        self.assertEqual((st["state"], st["review_level"], st["attempts"]), ("review", "resumen", 1))
        call = self.calls()[0]
        self.assertEqual(call["cwd"], st["worktree"])
        self.assertNotEqual(Path(st["worktree"]), self.repo)
        settings = json.loads(call["argv"][call["argv"].index("--settings") + 1])
        self.assertFalse(settings["allowNonWorkspaceAccess"])
        self.assertEqual(settings["permissions"]["allow"], [])
        self.assertIn("accept-edits", call["argv"])
        self.assertIn("Mapa de archivos", call["argv"][-1])
        self.assertIn("src/calc.py", call["argv"][-1].split("## Mapa de archivos")[1])
        self.assertNotIn("command(", call["argv"][call["argv"].index("--settings") + 1])
        # el proyecto principal no cambia hasta aceptar
        self.assertIn("NotImplementedError", (self.repo / "src" / "calc.py").read_text())
        self.assertIn("return a + b", self.cli("diff", "T1"))
        out = self.cli("accept", "T1")
        self.assertIn("staged", out)
        self.assertEqual((self.repo / "src" / "calc.py").read_text(), GOOD)
        self.assertIn("src/calc.py", self.git("diff", "--cached", "--name-only"))
        self.assertEqual(self.git("log", "--oneline").count("\n"), 1)  # sin commit nuevo
        self.assertFalse(Path(st["worktree"]).exists())
        self.assertEqual(self.git("branch", "--list", "agy/T1").strip(), "")

    def test_out_of_scope_and_protected_are_reverted(self):
        self.task("T2")
        self.plan({"write": {"src/calc.py": GOOD, "README.md": "hackeado\n", "tests/test_calc.py": "assert True\n",
                             "extra.txt": "x\n"}, "so": DONE})
        self.cli("run", "T2")
        st = self.state("T2")
        kinds = sorted((i["kind"], i["path"]) for i in st["incidents"])
        self.assertEqual(kinds, [("fuera_de_alcance", "README.md"), ("fuera_de_alcance", "extra.txt"),
                                 ("protegido_modificado", "tests/test_calc.py")])
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertEqual(st["review_level"], "diff")
        self.assertIn("--reviewed", self.cli("accept", "T2", code=1))
        self.cli("accept", "T2", "--reviewed")
        self.assertEqual((self.repo / "README.md").read_text(), "proyecto\n")
        self.assertFalse((self.repo / "extra.txt").exists())

    def test_verify_failure_triggers_fixup(self):
        self.task("T3", risk="medium")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE}, {"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T3")
        st = self.state("T3")
        self.assertEqual((st["state"], st["attempts"], st["review_level"]), ("review", 2, "diff"))
        second = self.calls()[1]["argv"]
        self.assertEqual(second[second.index("--conversation") + 1], "conv-fake")
        self.assertIn("La verificación del supervisor falló", second[-1])

    def test_verify_never_passes(self):
        self.task("T4", extra="max_fixups = 1\n")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        out = self.cli("run", "T4", code=3)
        self.assertIn("FAILED (gates)", out)
        self.assertEqual(self.state("T4")["attempts"], 2)
        self.cli("accept", "T4", code=1)
        # Claude puede corregir con fix y la tarea se recupera
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("fix", "T4", "usa suma, no resta")
        self.assertEqual(self.state("T4")["state"], "review")
        self.assertIn("usa suma, no resta", self.calls()[0]["argv"][-1])

    def test_blocked_then_fix(self):
        self.task("T5")
        self.plan({"so": dict(DONE, status="blocked", questions=["¿enteros o decimales?"])})
        out = self.cli("run", "T5", code=2)
        self.assertIn("¿enteros o decimales?", out)
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("fix", "T5", "enteros")
        self.assertEqual(self.state("T5")["state"], "review")

    def test_denied_action_and_missing_report_retry(self):
        self.task("T6")
        self.plan({"denied": [{"action": "command", "display_name": "Bash"}]}, {"write": {"src/calc.py": GOOD}},
                  {"so": DONE})
        self.cli("run", "T6")
        st = self.state("T6")
        self.assertEqual((st["state"], st["attempts"]), ("review", 3))
        self.assertIn("acción no permitida", self.calls()[1]["argv"][-1])

    def test_no_changes_fails(self):
        self.task("T7", extra="max_fixups = 0\n")
        self.plan({"so": DONE})
        self.cli("run", "T7", code=3)

    def test_executor_errors(self):
        self.task("T8")
        self.plan({"status": "ERROR", "rc": 1, "stderr": "RESOURCE_EXHAUSTED: quota exceeded"})
        self.cli("run", "T8", code=10)
        self.assertEqual(len(self.calls()), 1)  # la cuota no se reintenta
        self.cli("run", "T8", code=1)  # hay trabajo previo: exige --restart
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T8", "--restart")

    def test_reject_cleans_up(self):
        self.task("T9")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T9")
        wt = Path(self.state("T9")["worktree"])
        self.cli("reject", "T9", "--reason", "no convence")
        self.assertFalse(wt.exists())
        self.assertEqual(self.state("T9")["state"], "rejected")
        self.assertEqual(self.git("status", "--porcelain", "--", "src").strip(), "")

    def test_links_and_tamper_detection(self):
        (self.repo / "deps").mkdir()
        (self.repo / "deps" / "lib.py").write_text("x = 1\n")
        (self.repo / ".gitignore").write_text("deps/\n")
        self.git("add", ".gitignore")
        self.git("commit", "-qm", "ignore")
        (self.repo / ".agy" / "config.toml").write_text(f"verify = ['''{VERIFY}''']\nlink = ['deps']\n")
        self.task("T10")
        self.plan({"write": {"src/calc.py": GOOD, "deps/lib.py": "x = 2\n"}, "so": DONE})
        self.cli("run", "T10")
        st = self.state("T10")
        self.assertEqual(st["links"], ["deps"])
        self.assertEqual([i["kind"] for i in st["incidents"]], ["dependencias_enlazadas_modificadas"])
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])  # el enlace no entra al diff
        self.assertEqual(st["review_level"], "diff")

    def test_accept_conflict_leaves_project_intact(self):
        self.task("T11")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T11")
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    return 0  # cambio local\n")
        self.cli("accept", "T11", code=3)
        self.assertIn("cambio local", (self.repo / "src" / "calc.py").read_text())
        self.assertEqual(self.state("T11")["state"], "review")

    def test_overlap_with_running_task(self):
        self.task("T12")
        other = self.repo / ".agy" / "runs" / "OTRA"
        other.mkdir(parents=True)
        (other / "state.json").write_text(json.dumps(
            {"id": "OTRA", "role": "implement", "state": "running", "pid": os.getpid(), "allowed": ["src/calc.py"]}))
        self.assertIn("choque de alcance", self.cli("run", "T12", code=1))


class Validation(Base):
    def check_fails(self, tid, needle, **kw):
        self.task(tid, **kw)
        self.assertIn(needle, self.cli("check", tid, code=1))

    def test_rejections(self):
        self.check_fails("V1", "risk = high", risk="high")
        self.check_fails("V2", "Criterios de aceptación", body="## Objetivo\nalgo\n")
        self.check_fails("V3", "marcadores", body="## Objetivo\n«rellenar»\n\n## Criterios de aceptación\n- x\n")
        self.check_fails("V4", "claves desconocidas", extra="alowed = ['x']\n")
        self.check_fails("V5", "ruta no permitida", extra="allowed = ['../fuera/**']\n")
        self.check_fails("V7", "claves desconocidas", extra="commands = ['ls']\n")  # nunca terminal
        (self.repo / ".agy" / "config.toml").write_text("")
        self.check_fails("V6", "sin verificación automática")

    def test_new_template_is_rejected_until_filled(self):
        self.cli("new", "N1", "--title", "algo")
        self.assertIn("marcadores", self.cli("check", "N1", code=1))


class ReadOnlyRoles(Base):
    def test_explore(self):
        self.task("E1", role="explore", body="## Objetivo\n¿Dónde se define add?\n")
        self.plan({"so": {"status": "done", "summary": "en calc", "questions": [],
                          "findings": [{"path": "src/calc.py", "line": 1, "note": "definición"}]}})
        out = self.cli("run", "E1")
        self.assertIn("src/calc.py:1 — definición", out)
        call = self.calls()[0]
        self.assertEqual(call["cwd"], str(self.repo))
        settings = json.loads(call["argv"][call["argv"].index("--settings") + 1])
        self.assertEqual(settings["permissions"]["ask"], ["write_file(*)", "command(*)"])
        self.assertNotIn("--mode", call["argv"])
        self.assertEqual((settings["agentMode"], settings["toolPermission"]), ("", "request-review"))
        self.assertEqual(self.state("E1")["state"], "done")

    def test_explore_write_is_flagged(self):
        self.task("E2", role="explore", body="## Objetivo\n¿Dónde se define add?\n")
        self.plan({"write": {"src/intruso.py": "x = 1\n"},
                   "so": {"status": "done", "summary": "s", "questions": [], "findings": []}})
        out = self.cli("run", "E2")
        self.assertIn("arbol_modificado_durante_solo_lectura", out)

    def test_review_of_task(self):
        self.task("T1")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T1")
        self.task("R1", role="review", extra='target = "T1"\n', body="## Objetivo\nRevisar add.\n")
        self.plan({"so": {"status": "done", "verdict": "request_changes", "summary": "falta validar", "questions": [],
                          "issues": [{"severity": "medium", "path": "src/calc.py", "line": 2, "note": "sin tipos"}]}})
        out = self.cli("run", "R1")
        self.assertIn("veredicto: request_changes", out)
        self.assertIn("[medium] src/calc.py:2", out)
        self.assertIn("return a + b", self.calls()[0]["argv"][-1])  # el diff viaja en el prompt

    def test_status_lists_tasks(self):
        self.task("T1")
        self.assertIn("pendiente", self.cli("status"))


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
