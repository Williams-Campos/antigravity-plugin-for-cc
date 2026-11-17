#!/usr/bin/env python3
"""Pruebas de agy-task con un agy simulado (no llaman al agy real ni gastan cuota).

Ejecutar con Python 3.11 o superior:  python3 tests/test_agy_task.py
"""
import json
import os
import shutil
import subprocess
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGY_TASK = HERE.parent / "lib" / "agy_task.py"
LAUNCHER = HERE.parent / "bin" / "agy-task"
FAKE = HERE / "fake_agy"

DONE = {"status": "done", "summary": "hecho", "files_changed": [], "decisions": [], "questions": []}
GOOD = "def add(a, b):\n    return a + b\n"
BAD = "def add(a, b):\n    return a - b\n"
# Identidad de git para las pruebas: las máquinas de CI no tienen una configurada.
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
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
                        FAKE_AGY_PLAN=str(self.tmp / "plan.json"), **IDENTITY)
        self.cli("init")
        (self.repo / ".agy" / "config.toml").write_text(f"verify = ['''{VERIFY}''']\n")
        self.containment(ok=True)

    def containment(self, ok=None):
        """Registro de contención de la versión del agy simulado (None = sin comprobar)."""
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
        st = self.state("T4")
        self.assertEqual(st["attempts"], 3)  # los intentos se acumulan entre run y fix
        self.assertLess(st["active_secs"], 60)  # tiempo de trabajo, no tiempo de reloj desde el primer run
        rows = [json.loads(l) for l in (self.repo / ".agy" / "runs" / "usage.jsonl").read_text().splitlines()]
        self.assertEqual([(r["id"], r["input"]) for r in rows], [("T4", 200), ("T4", 100)])  # por sesión, sin acumular
        self.assertEqual(st["usage"]["input"], 300)
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

    def test_linked_dependencies_stay_out_of_the_diff(self):
        # git no copia lo ignorado (dependencias, SDK): se enlaza y nunca entra en el diff de agy.
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
        self.assertEqual(st["review_level"], "resumen")

    def test_accept_conflict_leaves_project_intact(self):
        self.task("T11")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "T11")
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    return 0  # cambio local\n")
        self.cli("accept", "T11", code=3)
        self.assertIn("cambio local", (self.repo / "src" / "calc.py").read_text())
        self.assertEqual(self.state("T11")["state"], "review")

    def test_seed_files_reach_agy_but_stay_out_of_the_diff(self):
        # Claude escribe la prueba primero y no la confirma: agy debe verla, no puede cambiarla,
        # y no forma parte de lo que agy entrega.
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
                         [("archivo_del_supervisor_modificado", "tests/test_add.py")])
        self.assertEqual([f["path"] for f in st["files"]], ["src/calc.py"])
        self.assertIn("tests/test_add.py", self.calls()[0]["argv"][-1])
        self.cli("accept", "S1", "--reviewed")
        self.assertEqual(self.git("diff", "--cached", "--name-only").split(), ["src/calc.py"])
        self.assertIn("calc.add(2, 3) == 5", seed.read_text())  # la prueba de Claude sigue intacta

    def test_seed_must_exist(self):
        self.task("S2", extra='allowed = ["src/**"]\nseed = ["tests/nope.py"]\n')
        self.assertIn("no existe como archivo", self.cli("check", "S2", code=1))

    def test_autofix_runs_before_gates(self):
        # El "formateador" corrige lo que agy dejó mal; sin él la verificación fallaría.
        fixer = "python3 -c \"import pathlib; p = pathlib.Path('src/calc.py'); p.write_text(p.read_text().replace('a - b', 'a + b'))\""
        (self.repo / ".agy" / "config.toml").write_text(f"verify = [\'\'\'{VERIFY}\'\'\']\nautofix = [\'\'\'{fixer}\'\'\']\n")
        self.task("A1")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        self.cli("run", "A1")
        self.assertEqual((self.state("A1")["state"], self.state("A1")["attempts"]), ("review", 1))
        self.assertIn("return a + b", self.cli("diff", "A1"))

    def test_search_results_are_embedded(self):
        self.task("Q1", extra='allowed = ["src/**"]\nsearch = ["NotImplementedError", "no-existe-zzz"]\n')
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "Q1")
        prompt = self.calls()[0]["argv"][-1]
        self.assertIn("src/calc.py:2:    raise NotImplementedError", prompt)
        self.assertIn("`no-existe-zzz` — 0 coincidencia(s)", prompt)

    def test_baseline(self):
        self.assertIn("LA VERIFICACIÓN BASE FALLA", self.cli("baseline", code=3))  # add aún no existe
        (self.repo / ".agy" / "config.toml").write_text("verify = ['test -f src/calc.py']\n")
        self.assertIn("verificación base correcta", self.cli("baseline"))
        self.assertEqual(self.git("worktree", "list").count("\n"), 1)  # no deja worktrees

    def test_file_map_omits_media(self):
        (self.repo / "foto.PNG").write_bytes(b"x")
        (self.repo / "src" / ".gitkeep").write_text("")
        self.git("add", "-A")
        self.git("commit", "-qm", "media")
        self.task("M1")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "M1")
        fmap = self.calls()[0]["argv"][-1].split("## Mapa de archivos")[1]
        self.assertNotIn("foto.PNG", fmap)
        self.assertNotIn(".gitkeep", fmap)
        self.assertIn("se omiten 2 archivos", fmap)
        self.assertIn("README.md", fmap)

    def test_accept_several_tasks_in_a_row(self):
        # Flujo en paralelo: dos tareas independientes se aceptan una tras otra, con otros
        # cambios sin commit presentes en el proyecto.
        (self.repo / "README.md").write_text("edición local sin commit\n")
        self.task("P1", extra='allowed = ["src/calc.py"]\n')
        self.task("P2", extra='allowed = ["src/extra.py"]\nverify = ["test -f src/extra.py"]\n')
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "P1")
        self.plan({"write": {"src/extra.py": "y = 2\n"}, "so": DONE})
        self.cli("run", "P2")
        self.cli("accept", "P1")
        self.cli("accept", "P2")
        self.assertEqual(sorted(self.git("diff", "--cached", "--name-only").split()), ["src/calc.py", "src/extra.py"])
        self.assertEqual((self.repo / "README.md").read_text(), "edición local sin commit\n")
        self.assertEqual(self.git("worktree", "list").count("\n"), 1)

    def test_overlap_with_running_task(self):
        self.task("T12")
        other = self.repo / ".agy" / "runs" / "OTRA"
        other.mkdir(parents=True)
        (other / "state.json").write_text(json.dumps(
            {"id": "OTRA", "role": "implement", "state": "running", "pid": os.getpid(), "allowed": ["src/calc.py"]}))
        self.assertIn("choque de alcance", self.cli("run", "T12", code=1))


class Containment(Base):
    PROBE_OK = {"write": {"inside.txt": "OK"}, "so": {"note": "hola"}}

    def test_unverified_agy_is_probed_once_and_then_trusted(self):
        record = self.containment(ok=None)
        self.task("C1")
        self.plan(*[self.PROBE_OK] * 8, {"write": {"src/calc.py": GOOD}, "so": DONE})
        out = self.cli("run", "C1")
        self.assertIn("sondeando", out)
        self.assertEqual(json.loads(record.read_text())["ok"], True)
        self.assertEqual(len(self.calls()), 9)  # 8 sondeos + la tarea
        self.assertEqual(self.state("C1")["state"], "review")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.assertNotIn("sondeando", self.cli("run", "C1", "--restart"))
        self.assertEqual(len(self.calls()), 1)

    def test_broken_containment_blocks_delegation(self):
        record = self.containment(ok=None)
        self.task("C2")
        # Un agy que escribe donde no debe: fuera del workspace y en modo de solo lectura.
        self.plan({"write": {"inside.txt": "OK", "ro.txt": "OK", "../outside/escape.txt": "OK"}, "so": {"note": "hola"}})
        out = self.cli("run", "C2", code=4)
        self.assertIn("la contención de agy 0.0.0-fake falló", out)
        self.assertIn("escritura fuera del workspace denegada", out)
        self.assertIn("crear archivos denegado", out)
        self.assertEqual(json.loads(record.read_text())["ok"], False)
        self.assertEqual(self.git("worktree", "list").count("\n"), 1)  # no se llegó a delegar
        self.assertIn("pendiente", self.cli("status"))

    def test_failed_record_is_reprobed_on_explore_too(self):
        self.containment(ok=False)
        self.task("C3", role="explore", body="## Objetivo\n¿Dónde se define add?\n")
        self.plan({"so": {"note": "sin escribir nada"}})  # ni siquiera puede escribir dentro: sigue roto
        self.assertIn("puede escribir dentro del workspace", self.cli("run", "C3", code=4))

    def test_doctor(self):
        self.assertIn("contención comprobada para agy 0.0.0-fake", self.cli("doctor"))
        self.containment(ok=None)
        self.assertIn("contención sin comprobar", self.cli("doctor"))
        self.plan(self.PROBE_OK)
        self.assertIn("contención verificada para agy 0.0.0-fake", self.cli("doctor", "--probe"))
        self.assertIn("contención comprobada", self.cli("doctor"))


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
        self.assertTrue(calls.exists(), "agy nunca llegó a lanzarse")
        self.assertIn("en ejecución (activo)", self.cli("result", "L1"))
        self.assertIn("ya está en ejecución", self.cli("run", "L1", code=1))
        self.assertIn("señal de cancelación enviada", self.cli("cancel", "L1"))
        self.assertEqual(proc.wait(timeout=30), 4)
        proc.communicate()
        st = self.state("L1")
        self.assertEqual((st["state"], st["reason"]), ("failed", "cancelled"))
        self.assertIn("no está en ejecución", self.cli("cancel", "L1"))

    def test_failed_result_shows_why_and_changed_files(self):
        self.task("L2", extra="max_fixups = 0\n")
        (self.repo / ".agy" / "config.toml").write_text("verify = ['echo motivo-del-fallo-xyz; exit 7']\n")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE})
        out = self.cli("run", "L2", code=3)
        self.assertIn("final de la verificación fallida:", out)
        self.assertIn("| motivo-del-fallo-xyz", out)
        self.assertIn("M src/calc.py", out)
        self.assertIn("no hay verificación base correcta", out)
        self.assertEqual(out, self.cli("result", "L2"))  # result reproduce el mismo texto

    def test_accepted_task_cannot_be_rejected(self):
        self.task("L3")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "L3")
        self.cli("accept", "L3")
        self.assertIn("ya fue aceptada", self.cli("reject", "L3", code=1))
        self.assertEqual(self.state("L3")["state"], "accepted")
        self.assertIn("solo se acepta una tarea en estado review", self.cli("accept", "L3", code=1))

    def test_accept_reports_missing_branch(self):
        self.task("L4")
        self.plan({"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "L4")
        self.git("worktree", "remove", "--force", self.state("L4")["worktree"])
        self.git("branch", "-D", "agy/L4")
        self.assertIn("no se encontró el trabajo de L4", self.cli("accept", "L4", code=4))

    def test_setup_failure_is_reported_before_calling_agy(self):
        (self.repo / ".agy" / "config.toml").write_text(f"verify = ['''{VERIFY}''']\nsetup = ['exit 9']\n")
        self.task("L5")
        self.plan({"so": DONE})
        out = self.cli("run", "L5", code=4)
        self.assertIn("FAILED (setup)", out)
        self.assertFalse(Path(self.env["FAKE_AGY_PLAN"] + ".calls").exists())

    def test_stats_and_version(self):
        self.assertIn("sin ejecuciones registradas", self.cli("stats"))
        self.task("L6")
        self.plan({"write": {"src/calc.py": BAD}, "so": DONE}, {"write": {"src/calc.py": GOOD}, "so": DONE})
        self.cli("run", "L6")
        self.task("L7", role="explore", body="## Objetivo\n¿Dónde se define add?\n")
        self.plan({"so": {"status": "blocked", "summary": "no se puede", "questions": ["¿cuál?"], "findings": []}})
        self.cli("run", "L7", code=2)
        out = self.cli("stats")
        self.assertIn("sesiones: 2", out)
        self.assertRegex(out, r"implement\s+1 sesiones · listas: 1 \(a la primera: 0\)")
        self.assertRegex(out, r"explore\s+1 sesiones · listas: 0 .* bloqueadas: 1")
        self.assertRegex(self.cli("--version"), r"^agy-task \d+\.\d+\.\d+\n$")


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

    def test_manual_tolerates_bom_and_leading_blank_lines(self):
        self.task("V8")
        path = self.repo / ".agy" / "tasks" / "V8.md"
        path.write_text("\ufeff\n\n" + path.read_text())
        self.assertIn("manual válido", self.cli("check", "V8"))

    def test_config_rejects_unknown_keys(self):
        (self.repo / ".agy" / "config.toml").write_text("verifi = ['x']\n")
        self.task("V9")
        self.assertIn("claves desconocidas: verifi", self.cli("check", "V9", code=1))

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

    def test_review_of_uncommitted_changes(self):
        (self.repo / "src" / "calc.py").write_text(GOOD)
        self.task("R2", role="review", extra='target = "working"\n', body="## Objetivo\nRevisar add.\n")
        self.plan({"so": {"status": "done", "verdict": "approve", "summary": "bien", "questions": [], "issues": []}})
        out = self.cli("run", "R2")
        self.assertIn("veredicto: approve", out)
        call = self.calls()[0]
        self.assertEqual(call["cwd"], str(self.repo))
        self.assertIn("+    return a + b", call["argv"][-1])

    def test_review_needs_something_to_review(self):
        self.task("R3", role="review", extra='target = "working"\n', body="## Objetivo\nRevisar.\n")
        self.assertIn("no hay cambios que revisar", self.cli("run", "R3", code=1))
        self.task("R4", role="review", extra='target = "NOPE"\n', body="## Objetivo\nRevisar.\n")
        self.assertIn("no tiene un worktree activo", self.cli("run", "R4", code=1))

    def test_readonly_retries_after_denied_action(self):
        self.task("E3", role="explore", body="## Objetivo\n¿Dónde se define add?\n")
        self.plan({"denied": [{"action": "write_file", "display_name": "Edit"}]},
                  {"so": {"status": "done", "summary": "en calc", "questions": [], "findings": []}})
        self.cli("run", "E3")
        self.assertEqual((self.state("E3")["state"], self.state("E3")["attempts"]), ("done", 2))
        self.assertIn("solo lectura", self.calls()[1]["argv"][-1])

    def test_status_lists_tasks(self):
        self.task("T1")
        self.assertIn("pendiente", self.cli("status"))


class ShippedManuals(Base):
    def test_examples_are_valid_manuals(self):
        (self.repo / ".agy" / "config.toml").write_text("verify = ['true']\n")
        for example in sorted((HERE.parent / "examples").glob("[a-z]*.md")):
            text = example.read_text()
            tid = text.split('id = "')[1].split('"')[0]
            (self.repo / ".agy" / "tasks" / f"{tid}.md").write_text(text)
            self.assertIn("manual válido", self.cli("check", tid), example.name)

    def test_every_role_has_template_and_rules(self):
        for role in ("implement", "explore", "review"):
            self.cli("new", f"N-{role}", "--role", role, "--title", "t", "--target", "T-001")
            self.assertTrue((HERE.parent / "rules" / f"{role}.md").read_text().strip())


class Launcher(unittest.TestCase):
    def test_skips_an_old_python_first_in_path(self):
        # En macOS el python3 del sistema es 3.9 y suele ir primero en el PATH.
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
            link = Path(tmp) / "enlace"
            link.symlink_to(LAUNCHER)  # instalado como enlace simbólico, igual que hace install.sh
            p = subprocess.run([str(link), "--version"], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 0, p.stderr)

    def test_reports_when_no_suitable_python_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "AGY_BRIDGE_PYTHON": "/bin/sh"}
            p = subprocess.run([str(LAUNCHER), "--version"], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 1)
            self.assertIn("no es un Python >= 3.11", p.stderr)


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
