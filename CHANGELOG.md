# Changelog

All notable changes to this project are documented here. The project follows
[semantic versioning](https://semver.org/); while it is below 1.0, minor versions may contain
breaking changes.

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
