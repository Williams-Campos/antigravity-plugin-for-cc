# Antigravity plugin for Claude Code

[![CI](https://github.com/Williams-Campos/antigravity-plugin-for-cc/actions/workflows/ci.yml/badge.svg)](https://github.com/Williams-Campos/antigravity-plugin-for-cc/actions/workflows/ci.yml)
![version](https://img.shields.io/badge/version-0.4.0--beta-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
[![license: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Use Antigravity (`agy`, Gemini) as a strictly supervised worker from inside Claude Code.**

Claude stays in charge: it decides what to build, writes a short manual for each task, and
accepts or rejects the result. agy does the work in isolation — in its own git worktree, with
no terminal and no way to write outside that worktree. An executor, `agy-task`, enforces the
contract with automatic gates and hands Claude a compact result, so Claude does not have to
re-read everything agy did.

The goal is not to save tokens in general. It is to **reserve Claude for what needs judgment**
(design, decisions, acceptance) and let agy handle execution that can be specified and verified.

The project ships two pieces:

- **`agy-task`**, the executor: a single-file Python program with no external dependencies.
- **The `agy-bridge` skill** for Claude Code, which tells Claude when to delegate, how to write a
  manual, and what to do with each result.

> **Beta.** Tested on macOS with agy 1.5.8 to 1.5.10, including a real Flutter project. The
> automated test suite also runs on Linux.

## Contents

- [How it works](#how-it-works)
- [Guarantees](#guarantees)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Writing a task manual](#writing-a-task-manual)
- [Task states](#task-states)
- [Commands](#commands)
- [Project configuration](#project-configuration)
- [Security model](#security-model)
- [Field results](#field-results)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## How it works

```
Claude writes .agy/tasks/T-001.md   (manual: goal, scope, acceptance criteria, verification)
        │
agy-task run T-001
        ├─ creates a dedicated worktree and branch (agy/T-001), outside the project
        ├─ launches agy with no terminal and no write access outside that worktree
        ├─ runs the project's formatter (agy cannot)
        ├─ reverts and logs any change outside the allowed scope or to protected files
        ├─ runs verification (tests, build) itself — it never trusts agy's word
        ├─ on failure, sends the error back to agy, up to max_fixups times
        └─ writes a short result: state, gates, incidents, files, agy's summary
        │
Claude reads the result  →  accept (staged, not committed)  ·  fix  ·  reject
```

There are three roles:

| Role | What it does | Where it works | Permissions |
|---|---|---|---|
| `implement` | Writes code according to the manual | Its own worktree | Edits only inside the worktree; no terminal |
| `explore` | Answers a question about the code, citing path and line | The project | Read-only |
| `review` | Reviews a task's diff, or uncommitted changes, with a different model | The task's worktree or the project | Read-only |

## Guarantees

| Guarantee | How it is enforced |
|---|---|
| agy cannot write outside its worktree or use the terminal | Per-session agy permissions, verified live once per agy version before anything is delegated |
| Everything that reaches `review` is inside `allowed` and leaves `protected` untouched | The executor reverts any other change and logs it as an incident |
| Everything that reaches `review` passed verification | The executor runs it, outside agy, on the already filtered tree |
| Nothing lands on your branch without `accept` | agy works on a different branch, in a different directory |
| `accept` never commits and never breaks work in progress | It is applied as an atomic patch to the index: all of it or nothing |
| Risky tasks are not accepted blindly | Medium risk, incidents or a large diff require `accept --reviewed` |

## Requirements

- [Antigravity CLI](https://antigravity.google/) (`agy`), installed and signed in.
- `git` and Python 3.11 or newer (no third-party packages).
- macOS or Linux. On Windows, use WSL.
- The project you delegate in must be a git repository with at least one commit.

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
agy-task new T-001 --role implement --title "Add slugify to textutil"
$EDITOR .agy/tasks/T-001.md
agy-task check T-001
agy-task run T-001
agy-task diff T-001          # when the result asks for it
agy-task accept T-001        # or: fix "…" / reject
```

Inside Claude Code you usually do not type any of this. Ask Claude to "delegate this to agy" and
the `agy-bridge` skill guides it through choosing what to delegate, writing the manual, running the
task and acting on the result.

The first time a task runs with a given agy version, `agy-task` probes agy's containment live
(about 20 seconds, a small amount of quota). If any probe fails, it refuses to delegate.

## Writing a task manual

A manual is a Markdown file with a TOML header between `+++` lines. Complete examples for every
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
Read `src/textutil.py` (the module's style) and `tests/test_slugify.py` (it defines the behaviour).

## Approach
- Signature: `slugify(text: str, max_length: int | None = None) -> str`.
- Standard library only.

## Acceptance criteria
- Every test in `tests/test_slugify.py` passes without being modified.

## Out of scope
- Do not create other files.
```

| Field | Roles | Meaning |
|---|---|---|
| `id`, `title` | all | Identifier (must match the file name) and a short title |
| `role` | all | `implement`, `explore` or `review` |
| `risk` | implement | `low`: may be accepted on the summary · `medium`: the diff must be read · `high`: never delegated |
| `allowed` | implement, explore | The only files agy may touch. For `explore`, the areas of interest |
| `protected` | implement | Files that define what is correct (tests). agy cannot change them |
| `forbidden` | implement | Exclusions inside `allowed` |
| `seed` | implement | Your uncommitted files that agy must see, e.g. a test you just wrote. agy cannot change them and they stay out of its diff |
| `search` | all | Exact strings the executor searches for across the project and attaches to the prompt (up to 8) |
| `verify` | implement | Verification commands. Defaults to the ones in `config.toml` |
| `target` | review | Id of the task to review, or `"working"` for the project's uncommitted changes |
| `model`, `max_fixups`, `max_diff_lines`, `timeout_min` | all | Override the project defaults |

Required sections: `## Goal` always, plus `## Acceptance criteria` for `implement`. Templates
created by `agy-task new` mark every blank with `«…»`; a manual that still contains one is
rejected until it is filled in.

Paths in `allowed`, `protected`, `forbidden` and `seed` are relative to the repository root.
`**` matches across directories, `*` and `?` do not, and a directory covers everything below it.

## Task states

| State | Meaning | What to do |
|---|---|---|
| `review` · review `summary` | Passed the gates; low risk and no incidents | `accept` |
| `review` · review `diff` | Passed the gates; medium risk, incidents or a large diff | `diff`, read it, `accept --reviewed` |
| `blocked` | agy has questions, or the contract cannot be met | `fix "answer"` |
| `failed (gates)` | Did not pass verification after the fix-up rounds | `fix "hint"`, `run --restart`, or do it by hand |
| `failed (setup)` | Preparing the worktree failed | Fix `setup`/`link` and run `baseline` again |
| `failed (quota·auth·timeout)` | agy failed | Wait, sign in again, or raise `timeout_min` |
| `done` | `explore` or `review` report ready | Use it |
| `accepted`, `rejected` | Closed | — |

## Commands

| Command | Description |
|---|---|
| `init` | Set up `.agy/` in the project |
| `baseline` | Run verification on the last commit, without agy |
| `new <id> --role … --title …` | Create a manual from the template |
| `check <id>` | Validate a manual without running it |
| `run <id> [--restart] [--allow-overlap]` | Run the task and apply the gates |
| `fix <id> "message"` | Send a correction or answer to agy and run the gates again |
| `result <id>` | Show the result, or the progress while it is still running |
| `diff <id> [--stat] [paths…]` | Show a task's diff |
| `accept <id> [--reviewed] [--keep]` | Integrate the work into the current branch, staged and not committed |
| `reject <id> [--reason …]` | Discard the work: removes the worktree and the branch |
| `cancel <id>` | Cancel a running task, including any verification in progress |
| `status` | List tasks and their states |
| `stats` | Summarise sessions, attempts, time and usage |
| `doctor [--probe]` | Check the installation; with `--probe`, probe containment live |

Exit codes of `run` and `fix`: `0` ready · `1` usage error or invalid manual · `2` blocked ·
`3` gates failed · `4` executor failure · `10` quota · `11` authentication · `12` timeout.

## Project configuration

`.agy/config.toml`; every key is optional.

| Key | Default | Purpose |
|---|---|---|
| `verify` | `[]` | Commands that define "correct". Without at least one, implementation is never delegated |
| `link` | `[]` | Paths git does not copy into the worktree, symlinked instead: installed dependencies, a local SDK |
| `setup` | `[]` | Commands that prepare the worktree before verification, e.g. `npm ci` |
| `autofix` | `[]` | Formatters the executor runs after every agy turn |
| `model_implement`, `model_explore` | `gemini-4-hydrogen-high` | Model per role (see `agy models`) |
| `model_review` | `gemini-4-argon-high` | Ideally different from the implementing model |
| `max_fixups` | `2` | Automatic fix-up rounds before control goes back to Claude |
| `max_diff_lines` | `800` | Above this, the task requires reading the diff |
| `timeout_min` | `30` | Limit per agy turn |
| `verify_timeout_min` | `15` | Limit per verification command |
| `worktree_root` | `~/.agy-bridge/worktrees` | Where worktrees are created |

In each project, `agy-task` uses `.agy/tasks/` (manuals), `.agy/config.toml` and `.agy/runs/`
(state, logs and `usage.jsonl`; ignored by git).

## Security model

- **Containment is measured, not assumed.** Before the first task with a new agy version, eight
  live probes check that the implementer can write inside its workspace but not outside it, not
  through a symlink that leaves it, and not through the terminal; and that explore/review sessions
  can read but cannot create files, edit files or run commands. The record is kept in
  `~/.agy-bridge/containment.json`. If any probe fails, nothing is delegated.
- **agy never gets a terminal.** In agy, allowing a single command such as `command(ls)` also
  allows redirections, chaining and subshells — in practice, the whole terminal. Instead, the
  executor gives agy a file map and pre-run `search` results, and runs formatters and
  verification itself.
- **Scope is enforced after every turn**, regardless of what agy reports: out-of-scope,
  forbidden and protected changes are reverted and logged as incidents.
- **Read-only roles have a second barrier**: the executor fingerprints the working tree before
  and after the session and flags any change.

## Field results

First trial on a real Flutter project (about 190 Dart files and 158 tests), using
`bash scripts/check.sh` as verification: dependency resolution, code generation, formatting,
static analysis and tests.

| Assignment | Result | Time |
|---|---|---|
| 2 `explore` runs in parallel | Path and line references were correct when checked against the code | 41 s and 46 s |
| 2 `implement` runs in parallel (new unit tests, 69 and 77 lines) | Passed every gate on the first attempt | ~1 min of agy + ~4 min of verification each |
| 2 `review` runs with a different model | One minor, valid finding, later fixed with `fix` | ~1 min each |
| A deliberately impossible contract, with pressure to "make it pass" | `blocked` both times; it never tried to touch forbidden files | 17 s |

This is a small sample, not a benchmark. The practical lesson: the project's verification
dominates the total time, not agy, so independent tasks should run in parallel.

## Known limitations

- **No verification command, no delegated implementation.** This is deliberate.
- **agy has no terminal, directory listing or search.** It receives a path map and the
  `search` results instead.
- **The worktree starts from the last commit.** Uncommitted changes do not reach agy, except for
  the files listed in `seed`.
- **Verification runs on your machine, with your permissions**, and executes the code agy wrote.
  Keep `allowed` narrow and `risk` honest.
- **Your code is sent to Google** when you delegate. Do not delegate files that contain secrets.
- **Quota depends on your Google plan.** A quota failure ends the task with exit code 10.
- **The gates prove the work meets the contract, not that the design is good.** That is what
  `risk = "medium"`, reading the diff and the `review` role are for.
- **Every new worktree repeats the project's preparation** (installing, generating code), which
  lengthens verification.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `BASELINE VERIFICATION FAILS` | Verification does not pass even without changes: something is missing from `link` or `setup`, or the project was already broken. See `.agy/runs/_baseline.log` |
| `containment check failed for agy X` | That agy version does not enforce the expected permissions. Nothing is delegated; run `agy-task doctor --probe` again |
| Repeated `failed (gates)` on formatting or lint | The formatter is missing from `autofix`: agy cannot run it |
| `blocked` because agy cannot find a file | Give the exact path in the manual, or add the name to `search` |
| `could not integrate` on accept | The task's files changed in the project. Commit or discard those changes, or `run --restart` |
| `requires Python 3.11` | Set `AGY_BRIDGE_PYTHON` to the path of a recent Python |

## Development

```
bin/agy-task        launcher: finds a suitable Python
lib/agy_task.py     the executor, with no external dependencies
rules/              fixed rules agy receives for each role
templates/          manual and configuration templates
examples/           example manuals
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
