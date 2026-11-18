# Antigravity plugin for Claude Code

[![CI](https://github.com/Williams-Campos/antigravity-plugin-for-cc/actions/workflows/ci.yml/badge.svg)](https://github.com/Williams-Campos/antigravity-plugin-for-cc/actions/workflows/ci.yml)
![version](https://img.shields.io/badge/version-0.5.0--beta-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
[![license: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Claude Code and Antigravity (`agy`, Gemini) working on your project as a team: Claude as the
senior engineer, agy as the experienced junior.**

Claude does the thinking: it analyses what you want, decides the architecture, splits the work,
and writes a precise brief for every piece it delegates. agy does the building: it implements each
brief with its full toolset — terminal, search, tests — in its own git worktree, tests its own
work and iterates. Claude then validates what agy delivered, without having to redo it, and you
decide what gets committed.

The two talk to each other through a small protocol: Claude can give agy an instruction (`fix`),
a non-binding suggestion (`recommend`) or a set of questions (`grill`); agy can push back,
recommend a better path, or act as an external check that challenges Claude's own plan.

The project ships two pieces:

- **`agy-task`**, the executor: a single-file Python program with no external dependencies.
- **The `agy-bridge` skill** for Claude Code, which teaches Claude the workflow: when to delegate,
  how to write a brief, how to validate and how to talk to agy.

> **Beta.** Tested on macOS with agy 1.5.8 to 1.5.10, on a real Flutter project and a NumPy
> project. The automated test suite also runs on Linux.

## Contents

- [The workflow](#the-workflow)
- [How a task runs](#how-a-task-runs)
- [Talking to agy](#talking-to-agy)
- [Modes](#modes)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Writing a brief](#writing-a-brief)
- [Task states](#task-states)
- [Commands](#commands)
- [Project configuration](#project-configuration)
- [Field results](#field-results)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## The workflow

1. **You** say what to work on next.
2. **Claude analyses** the code, or launches an `explore` when the ground is broad.
3. **Claude splits the work** and shows you the split: what it keeps (architecture, ambiguous or
   sensitive parts, integration) and what goes to agy (well-defined implementation).
4. **Claude writes a brief** per delegated task: goal, context, decisions, agreements, acceptance
   criteria.
5. **agy implements** with its full toolset, tests and iterates; independent tasks run in parallel.
6. **Claude validates**: the result, the audit, the diff in proportion to the risk, and if needed
   a `fix`, a `recommend` or a `grill`.
7. **Claude integrates** with `accept`, runs the full verification and reports to you.
8. **You** decide the commit.

Inside Claude Code you rarely type `agy-task` yourself: ask Claude to "work on this with agy" and
the skill drives the workflow.

## How a task runs

```
Claude writes .agy/tasks/T-001.md   (brief: goal, context, decisions, agreements, criteria)
        │
agy-task run T-001
        ├─ creates a dedicated worktree and branch (agy/T-001), outside your working copy
        ├─ agy works there with its full toolset and runs the verification itself
        ├─ commits agy made are folded back; leaving the task branch fails the task
        ├─ the formatter runs (autofix), build artifacts are kept out of the diff
        ├─ the audit records anything outside the agreed area, without undoing it
        ├─ the executor runs the project's verification again
        ├─ on failure, the output goes back to agy, up to max_fixups times
        └─ a short result: state, gates, audit, files, agy's summary, decisions, recommendations
        │
Claude validates  →  accept (staged, not committed)  ·  fix  ·  recommend  ·  grill  ·  reject
```

Roles:

| Role | What agy does | Where | Default model |
|---|---|---|---|
| `implement` | Writes code (and its tests) according to the brief | Its own worktree | `gemini-4-argon-high` |
| `explore` | Answers a question about the code, citing path and line | The project, read-only | `gemini-4-hydrogen-high` |
| `review` | Reviews a task's diff, or uncommitted changes | The task's worktree or the project, read-only | `gemini-4-hydrogen-high` |
| `grill` | Challenges Claude's plan, changes or claim | The project, read-only | `gemini-4-argon-high` |

What stays the same however free agy is:

| | How |
|---|---|
| Nothing lands on your branch without Claude's `accept` | agy works on another branch, in another directory |
| `accept` never commits and never breaks work in progress | It applies an atomic patch to the index: all of it or nothing |
| What Claude accepts passed your verification | The executor runs it after agy, outside agy's report |
| Claude knows what agy did beyond the agreement | Every file outside the agreed area is listed in the audit |
| Risky work is not accepted blindly | Medium risk, audit notes or a large diff require `accept --reviewed` |

## Talking to agy

| Command | Direction | Meaning |
|---|---|---|
| `fix <ID> "…"` | Claude → agy | An instruction. agy applies it and the gates run again. |
| `recommend <ID> "…"` | Claude → agy | A suggestion, not an order. agy adopts it (and implements it) or declines it with a reason. |
| `grill <ID> "questions"` | Claude → agy | Claude questions agy about its delivered work. agy answers with evidence and changes nothing. |
| `grill --file F` · `--working` · `--text "…"` | agy → Claude | An external check: a different model, without Claude's context, challenges Claude's plan, uncommitted changes or a claim. Verdict `sound`, `concerns` or `unsound`, with objections and evidence. |
| `reply <ID> "…"` | Claude → agy | Continues an explore, review, grill or answers session. On a grill, agy keeps only the objections that still stand. |
| `recommendations` | agy → Claude | Every report can carry risks, follow-up work or better approaches agy noticed. |

## Modes

| | `collaborative` (default) | `strict` |
|---|---|---|
| agy's tools | Full: terminal, search, tests, its own file reading | File reading and editing only; no terminal |
| Who runs the tests | agy while it works, and the executor before Claude accepts | The executor only |
| Work outside the agreed area | Kept and listed in the audit for Claude to judge | Reverted and logged as an incident |
| Search and file listing | agy's own tools; `search` terms become hints | The executor attaches a file map and pre-run searches |
| Containment probes | Not needed | Run live once per agy version; nothing is delegated if they fail |

Set it with `mode = "strict"` in `.agy/config.toml`. Strict mode exists for sensitive projects
where you want hard technical limits instead of agreements.

In collaborative mode agy runs with `--dangerously-skip-permissions`: it can do anything you could
do from a terminal in that worktree, exactly as when you run agy yourself. The agreements in the
brief and Claude's validation are what keep it on track.

## Requirements

- [Antigravity CLI](https://antigravity.google/) (`agy`), installed and signed in.
- `git` and Python 3.11 or newer (no third-party packages).
- macOS or Linux. On Windows, use WSL.
- The project must be a git repository with at least one commit.

## Installation

```bash
git clone https://github.com/Williams-Campos/antigravity-plugin-for-cc.git
```

```bash
cd antigravity-plugin-for-cc && ./install.sh
```

The installer creates two symlinks — `~/.local/bin/agy-task` and `~/.claude/skills/agy-bridge` — and
then runs `agy-task doctor`. It does not modify your Claude Code or agy configuration. To remove
them, run `./install.sh --uninstall`.

`agy-task` locates a suitable Python on its own, even when the `python3` on your `PATH` is older
(macOS ships 3.9). To pin one: `export AGY_BRIDGE_PYTHON=/path/to/python3`.

## Quick start

Once per project:

```bash
cd my-project
agy-task init        # creates .agy/ and suggests a verification command
$EDITOR .agy/config.toml
agy-task baseline    # checks, without spending quota, that verification passes in a clean worktree
```

For each task:

```bash
agy-task new T-001 --title "Add slugify to textutil"
$EDITOR .agy/tasks/T-001.md
agy-task check T-001
agy-task run T-001
agy-task grill T-001 "Why did you choose X over Y?"   # optional: validate without reading everything
agy-task accept T-001                                  # or --reviewed after reading the diff
```

An external check of your own plan:

```bash
agy-task grill --file docs/plan.md --focus "edge cases and wrong assumptions"
agy-task reply G-001 "Objection 2 does not apply because …"
```

## Writing a brief

A brief is a Markdown file with a TOML header between `+++` lines. Complete examples for every
role live in [`examples/`](examples/).

```markdown
+++
id = "T-001"
title = "Add slugify to textutil"
role = "implement"
risk = "low"
allowed = ["src/textutil.py"]
protected = ["tests/**"]
+++

## Goal
Add `slugify` to `src/textutil.py` to turn titles into URL-safe identifiers.

## Context
`tests/test_slugify.py` defines the exact behaviour expected.

## Decisions
- Signature: `slugify(text: str, max_length: int | None = None) -> str`.

## Agreements
- Standard library only.

## Acceptance criteria
- Every test in `tests/test_slugify.py` passes without being modified.
```

`Decisions` is what Claude settled; everything else is agy's call, and agy explains its non-obvious
choices in the report. Required sections: `## Goal` always, plus `## Acceptance criteria` for
`implement`. `## Context`, `## Decisions`, `## Agreements` and `## Expected output` are
recommended. Templates created by `agy-task new` mark every blank with `«…»`; a brief that still
contains one is rejected until it is filled in.

| Field | Roles | Meaning |
|---|---|---|
| `id`, `title` | all | Identifier (must match the file name) and a short title |
| `role` | all | `implement`, `explore` or `review` (grill sessions need no brief) |
| `risk` | implement | `low`: may be accepted on the summary · `medium`: the diff must be read · `high`: never delegated |
| `allowed` | implement, explore | The agreed area: the files the task is expected to touch. For `explore`, the areas of interest |
| `protected` | implement | Files that define what is correct (tests). agy must not change them |
| `forbidden` | implement | Off limits |
| `seed` | implement | Your uncommitted files that agy must see, e.g. a test you just wrote. Restored if agy changes them, and never part of its diff |
| `search` | all | Exact strings worth searching for (strict mode: the executor runs the search and attaches the results) |
| `verify` | implement | Verification commands. Defaults to the ones in `config.toml` |
| `target` | review | Id of the task to review, or `"working"` for the project's uncommitted changes |
| `model`, `max_fixups`, `max_diff_lines`, `timeout_min` | all | Override the project defaults |

Paths are relative to the repository root. `**` matches across directories, `*` and `?` do not,
and a directory covers everything below it.

## Task states

| State | Meaning | What to do |
|---|---|---|
| `review` · review `summary` | Verification passed; low risk and nothing to audit | `accept` |
| `review` · review `diff` | Verification passed; medium risk, audit notes or a large diff | `diff`, read it, `accept --reviewed` |
| `blocked` | agy has questions | `fix "answer"` (implement) or `reply "answer"` (other sessions) |
| `failed (gates)` | Verification still failed after the extra rounds | `fix "hint"`, `run --restart`, or do it by hand |
| `failed (git)` | agy left its task branch | Inspect the worktree, then usually `run --restart` |
| `failed (setup)` | Preparing the worktree failed | Fix `setup`/`link` and run `baseline` again |
| `failed (quota·auth·timeout)` | agy failed | Wait, sign in again, or raise `timeout_min` |
| `done` | explore, review, grill or answers report ready | Use it, or follow up with `reply` |
| `accepted`, `rejected` | Closed | — |

Audit notes (collaborative mode): `outside_agreed_area`, `protected_modified`,
`off_limits_modified`, `supervisor_file_modified` (a `seed` file, restored),
`executor_area_restored` (`.agy/` or `.git/`), `agy_committed` (folded back), `branch_changed`,
`tree_modified_during_read_only`. They are information for Claude, not failures.

## Commands

| Command | Description |
|---|---|
| `init` | Set up `.agy/` in the project |
| `baseline` | Run verification on the last commit, without agy |
| `new <id> [--role …] --title …` | Create a brief from the template |
| `check <id>` | Validate a brief without running it |
| `run <id> [--restart] [--allow-overlap]` | Run the task and apply the gates |
| `fix <id> "message"` | Send an instruction to agy and run the gates again |
| `recommend <id> "message"` | Send a non-binding suggestion; agy adopts or declines it |
| `grill <id> "questions"` | Question agy about a delivered task, without changing it |
| `grill --file F \| --working \| --text "…" [--focus …] [--name …]` | Have agy challenge Claude's plan, changes or claim |
| `reply <id> "message"` | Continue an explore, review, grill or answers session |
| `result <id>` | Show the result, or the progress while it is still running |
| `diff <id> [--stat] [paths…]` | Show a task's diff |
| `accept <id> [--reviewed] [--keep]` | Integrate the work into the current branch, staged and not committed |
| `reject <id> [--reason …]` | Discard the work: removes the worktree and the branch |
| `cancel <id>` | Cancel a running task or session, including verification in progress |
| `status` | List tasks and sessions with their states |
| `stats` | Summarise sessions, attempts, time and usage per role |
| `doctor [--probe]` | Check the installation; with `--probe`, probe strict-mode containment live |

Exit codes: `0` ready · `1` usage error or invalid brief · `2` blocked · `3` gates failed ·
`4` executor failure · `10` quota · `11` authentication · `12` timeout.

## Project configuration

`.agy/config.toml`; every key is optional.

| Key | Default | Purpose |
|---|---|---|
| `mode` | `"collaborative"` | `collaborative` or `strict` (see [Modes](#modes)) |
| `verify` | `[]` | Commands that define "correct". Without at least one, implementation is never delegated |
| `link` | `[]` | Paths git does not copy into the worktree, symlinked instead: installed dependencies, a local SDK |
| `setup` | `[]` | Commands that prepare the worktree before agy starts, e.g. `npm ci` |
| `autofix` | `[]` | Formatters the executor runs after every agy turn |
| `artifacts` | `[]` | Extra build artifacts kept out of the diff (Python and Node caches already are) |
| `model_implement` | `gemini-4-argon-high` | Implementer (see `agy models`; the suffix is the reasoning effort) |
| `model_explore`, `model_review` | `gemini-4-hydrogen-high` | Explorer and reviewer; the reviewer is ideally not the implementer |
| `model_grill` | `gemini-4-argon-high` | External check of Claude's work |
| `max_fixups` | `2` | Extra rounds when verification fails, before control goes back to Claude |
| `max_diff_lines` | `800` | Above this, the task requires reading the diff |
| `timeout_min` | `30` | Limit per agy turn |
| `verify_timeout_min` | `15` | Limit per verification command |
| `worktree_root` | `~/.agy-bridge/worktrees` | Where worktrees are created |

In each project, `agy-task` uses `.agy/tasks/` (briefs), `.agy/config.toml` and `.agy/runs/`
(state, logs and `usage.jsonl`; ignored by git).

## Field results

**Collaborative mode, NumPy project** (a synthetic sensor dataset with a `unittest` suite):

| Assignment | Result | Time |
|---|---|---|
| `implement` with Argon: inspection and NaN cleaning, agy writing its own tests | First attempt: 55 lines of code and 13 tests of its own; it ran the verification itself (23 tests OK) and recommended keeping file I/O in `main.py` | 4 min 23 s |
| `grill <ID>`: three questions about memory sharing, integer input and an extra error | Answered with file and line references and its own experiments; flagged a missing test case; changed nothing | 54 s |
| `grill --file`: agy challenging Claude's plan for the remaining modules | `unsound`: caught a wrong expectation in Claude's plan (checked over 100 seeds), a silent tie in `argmax` and two missing deliverables. One objection was itself wrong | 5 min 17 s |
| `reply` to that grill | Dropped the refuted objection and the resolved ones: `sound` | ~2 min |
| `recommend` a simplification that would have caused regressions | Declined with three concrete reasons (empty arrays, integer dtype, wasted work); code unchanged | ~1 min |

**Strict mode, Flutter project** (about 190 Dart files and 158 tests; verification =
dependency resolution, code generation, formatting, analysis and tests):

| Assignment | Result | Time |
|---|---|---|
| 2 `explore` runs in parallel | Path and line references correct when checked against the code | 41 s and 46 s |
| 2 `implement` runs in parallel (new unit tests, 69 and 77 lines) | Passed every gate on the first attempt | ~1 min of agy + ~4 min of verification each |
| 2 `review` runs with a different model | One minor, valid finding, later fixed with `fix` | ~1 min each |
| A deliberately impossible contract, with pressure to "make it pass" | `blocked` both times; it never touched forbidden files | 17 s |

Small samples, not benchmarks. The practical lessons: verification and Argon's thoroughness
dominate the time, so independent tasks should run in parallel; and agy blocks and asks rather
than bending a contract it cannot meet.

## Known limitations

- **No verification command, no delegated implementation.** Without it Claude cannot accept on
  a summary.
- **In collaborative mode agy can run anything** in its worktree, with your user's permissions,
  like agy used directly. The worktree keeps it off your working copy and branch, not off your
  machine. Use `mode = "strict"` where that is not acceptable.
- **Linked paths are shared.** Whatever is in `link` (e.g. `node_modules`) is the project's real
  folder; agy is told not to modify it.
- **The worktree starts from the last commit.** Uncommitted changes do not reach agy, except for
  the files listed in `seed`.
- **Your code is sent to Google** when you delegate. Do not delegate files that contain secrets.
- **Quota depends on your Google plan.** A quota failure ends the task with exit code 10.
- **Argon is thorough, not fast.** Expect minutes per implement task; use Hydrogen for quick
  exploration.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `BASELINE VERIFICATION FAILS` | Verification does not pass even without changes: something is missing from `link` or `setup`, or the project was already broken. See `.agy/runs/_baseline.log` |
| Build artifacts appear in a diff | Add their pattern to `artifacts` in `config.toml` |
| `failed (git)` | agy switched branches in its worktree. Inspect it with `git -C <worktree> status`, then `run --restart` |
| Repeated `failed (gates)` on formatting or lint | Add the formatter to `autofix` |
| `could not integrate` on accept | The task's files changed in the project. Commit or discard those changes, or `run --restart` |
| `containment check failed for agy X` | Strict mode only: that agy version does not enforce the expected permissions. Run `agy-task doctor --probe` again |
| `requires Python 3.11` | Set `AGY_BRIDGE_PYTHON` to the path of a recent Python |

## Development

```
bin/agy-task        launcher: finds a suitable Python
lib/agy_task.py     the executor, with no external dependencies
rules/              the rules agy receives, per mode and role
templates/          brief and configuration templates
examples/           example briefs
claude/skills/      the skill for Claude Code
tests/              tests against a fake agy
```

The test suite never calls the real agy and spends no quota:

```bash
python3 tests/test_agy_task.py
```

Issues and pull requests are welcome. Please keep the executor dependency-free, add a test for
any behaviour change, and update [`CHANGELOG.md`](CHANGELOG.md).

## License

[MIT](LICENSE). This is an independent project, not affiliated with or endorsed by Google or
Anthropic. "Antigravity", "Gemini", "Claude" and "Claude Code" are trademarks of their respective
owners. Use of agy and Claude is governed by each service's terms, and whatever you delegate is
sent to them.
