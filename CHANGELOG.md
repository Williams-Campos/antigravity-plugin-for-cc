# Changelog

All notable changes to this project are documented here. The project follows
[semantic versioning](https://semver.org/); while it is below 1.0, minor versions may contain
breaking changes.

## 0.7.0 — 2026-11-20

### Changed
- **Neon is the frontier model.** `model_implement` and `model_grill` default to
  `gemini-4-neon-high` (previously `gemini-4-argon-high`). Explore and review stay on Hydrogen.

### Added
- **Quota fallback** (`model_fallback`, default `gemini-4-argon-high`): when the model's quota is
  exhausted, the same turn is retried once on the fallback model, which has a separate quota, in
  the same conversation; the session stays on it and the result says so. `model_fallback = ""`
  turns it off.

## 0.6.1 — 2026-11-18

Fixes from a field report on a Flutter project with a gitignored SDK folder.

### Fixed
- **Gitignored `link` and `artifacts` paths no longer abort the delivery.** Staging used exclude
  pathspecs, and git refuses an exclude that names a path it already ignores (`.tooling/`,
  `node_modules`), so the task ended with exit 4 after agy had finished. Staging now adds
  everything and then unstages the excluded paths.
- **An executor failure no longer leaves a task as a dead `running`.** It ends as
  `failed (executor)`, with the command that failed in `detail` and agy's work kept in the
  worktree. Sessions whose process died for any other reason read the same way.

### Added
- `recheck <ID>`: runs the gates again on agy's last delivery without calling agy, after fixing a
  configuration or executor problem. No more `run --restart` throwing away minutes of agy's work.
- `baseline` also runs the delivery's staging step, so a `link` or `artifacts` problem shows up
  before any quota is spent.
- The result names the files that changed both in the task and in your uncommitted working copy,
  which `accept` would refuse, instead of a generic note about uncommitted changes.

## 0.6.0 — 2026-11-18

### Added
- **Team skills** (`skills` config key): Claude Code skills that both agents follow. agy receives
  the text of each one at the start of every session; the bundled skill tells Claude to load the
  same skills before writing code, briefs or validations. Entries are skill names
  (`~/.claude/skills/<name>/SKILL.md`) or file paths. `agy-task doctor` lists them, and a missing
  skill stops the task before agy is called.
- **User configuration** in `~/.agy-bridge/config.toml`: defaults for every project, overridden
  by each project's `.agy/config.toml`.

## 0.5.1 — 2026-11-17

### Changed
- Documentation reorganised: a shorter README, with the full guides in `docs/` (how it works,
  writing a brief, command reference, configuration, troubleshooting, field results) and a
  `CONTRIBUTING.md`.
- The Claude Code skill moved from `claude/skills/agy-bridge/` to `skill/`. **Existing installs:
  run `./install.sh` again** so the skill symlink points to the new location.
- The CLI and the strict-mode rules say "brief" instead of "manual", matching the documentation.

## 0.5.0 — 2026-11-17

Claude and agy now work as a senior and an experienced junior: Claude analyses, splits the work,
writes the briefs and validates; agy implements with its full toolset.

### Added
- **Collaborative mode**, the new default (`mode = "collaborative"`): agy runs with its full
  toolset — terminal, search, tests — in its own worktree, runs the verification itself and
  iterates. The executor audits what it delivered instead of reverting it, and still runs the
  project's verification before Claude accepts.
- `recommend <ID> "..."`: a non-binding suggestion. agy adopts it (and implements it) or declines
  it with a reason, reported as `suggestion` in the result.
- `grill`, in both directions: `grill --file`, `--working` or `--text` has agy challenge Claude's
  plan, uncommitted changes or a claim (an external check, verdict `sound`/`concerns`/`unsound`
  with objections and evidence); `grill <ID> "questions"` has agy answer the senior's questions
  about a delivered task, in its own conversation, without changing it.
- `reply <ID> "..."` continues an explore, review, grill or answers session; on a grill, agy keeps
  only the objections that still stand.
- Every report carries `recommendations`: risks, follow-up work or better approaches agy noticed.
- Brief v2 template: `Goal`, `Context`, `Decisions`, `Agreements`, `Acceptance criteria`,
  `Expected output`.
- `artifacts` config key; Python and Node caches never enter a task's diff.
- Git coexistence: commits agy makes are folded back into the index; leaving the task branch
  fails the task with `failed (git)`.

### Changed
- Default models: Argon high implements and grills; Hydrogen high explores and reviews (a
  different model than the implementer).
- Audit notes are recomputed on the final diff, so they describe what Claude would accept.
- Read-only sessions that change a task's worktree (review, answers) have it restored to the
  verified commit.
- The previous behaviour is kept as `mode = "strict"`: no terminal, file map and pre-run
  searches, out-of-scope changes reverted, containment probed once per agy version (only in this
  mode). Its rules moved to `rules/strict/`.

## 0.4.0 — 2026-11-17

The project is now public as **Antigravity plugin for Claude Code**
(`Williams-Campos/antigravity-plugin-for-cc`) and is written entirely in English.

### Changed (breaking)
- Everything is in English: CLI output, error messages, the rules agy receives, templates,
  examples, the Claude Code skill and the documentation.
- Manual sections are now `## Goal`, `## Context`, `## Approach`, `## Acceptance criteria`,
  `## Out of scope` and `## What to report`. Manuals written for 0.3 must rename `## Objetivo`
  and `## Criterios de aceptación`, which are required.
- The review levels are now `summary` and `diff` (previously `resumen` and `diff`).
- Incident kinds, gate names and the `blocked` reason are now English identifiers:
  `out_of_scope`, `protected_modified`, `forbidden`, `supervisor_file_modified`,
  `tree_modified_during_read_only`; gates `turn`, `changes`, `size`, `verify`, `autofix`;
  reason `questions`.

## 0.3.1 — 2026-11-17

### Added
- MIT license.

## 0.3.0 — 2026-11-16

### Added
- agy's containment is checked automatically once per installed version, before delegating. If
  it fails, the executor refuses to launch any task. The eight probes run in parallel.
- `bin/agy-task` launcher that finds a Python 3.11 or newer even when the `python3` on the
  `PATH` is older. `AGY_BRIDGE_PYTHON` pins a specific one.
- `stats` command: sessions, attempts, time and usage from `usage.jsonl`.
- `agy-task --version`.
- A `failed (gates)` result includes the tail of the failed verification and the files agy left.
- Continuous integration on Linux and macOS, example manuals and this changelog.

### Changed
- The executor was reorganised into `lib/agy_task.py`, with a single path for launching
  processes.
- `cancel` also stops verification commands in progress, not only agy.
- `accept` shows only the files of the accepted task.

### Fixed
- `reject` no longer allows marking an accepted task as rejected.
- `accept` reports clearly when the task's branch no longer exists.
- Manuals may start with a BOM or blank lines before the header.

## 0.2.0 — 2026-11-16

Adjustments after the first trial on a real (Flutter) project.

### Added
- `autofix`: the executor runs the formatter after every turn, because agy has no terminal.
- `seed`: uncommitted files (tests written by Claude) reach the worktree; agy cannot modify them
  and they stay out of its diff.
- `search`: the executor attaches exact-text searches, because agy has no search tool.
- `baseline`: checks verification in a clean worktree without spending quota.

### Changed
- `accept` integrates the task as an atomic patch: several tasks can be accepted in a row and
  coexist with uncommitted changes.
- The file map omits media and binary files.
- The result shows accumulated work time, and `usage.jsonl` records each session.

### Removed
- Detection of modified linked dependencies by modification time: it produced false incidents
  with parallel tasks, and agy already denies writes through symlinks that leave the workspace.

## 0.1.0 — 2026-11-16

First release: the `agy-task` executor with the `implement`, `explore` and `review` roles, a
worktree per task, scope and verification gates, a Claude Code skill and an installer.
