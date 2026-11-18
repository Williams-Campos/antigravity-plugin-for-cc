# How it works

This page describes what happens between Claude writing a brief and the work landing on your
branch: the workflow, the life of a task, the guarantees that hold in every mode, and how the two
modes differ.

- [The workflow](#the-workflow)
- [Roles](#roles)
- [Life of a task](#life-of-a-task)
- [Guarantees](#guarantees)
- [Modes](#modes)
- [Review levels](#review-levels)
- [Task states](#task-states)
- [Audit notes](#audit-notes)

## The workflow

| Step | Who | What happens |
|---|---|---|
| 1 | You | Say what to work on next. |
| 2 | Claude | Analyses the code itself, or launches an `explore` when the ground is broad. |
| 3 | Claude | Splits the work and shows you the split: what it keeps (architecture, ambiguous or sensitive parts, integration) and what goes to agy (well-defined implementation). |
| 4 | Claude | Writes one brief per delegated task: goal, context, decisions, agreements, acceptance criteria. |
| 5 | agy | Implements with its full toolset, runs the tests and iterates. Independent tasks run in parallel. |
| 6 | Claude | Validates the result, the audit and the diff (in proportion to the risk), and follows up with `fix`, `recommend` or `grill` when needed. |
| 7 | Claude | Integrates with `accept`, runs the full verification and reports to you. |
| 8 | You | Decide the commit. |

Inside Claude Code you rarely type `agy-task` yourself: ask Claude to "work on this with agy" and
the bundled skill drives the workflow.

## Roles

| Role | What agy does | Where it runs | Default model |
|---|---|---|---|
| `implement` | Writes code, and its tests, according to the brief | Its own worktree | `gemini-4-argon-high` |
| `explore` | Answers a question about the code, citing path and line | The project, read-only | `gemini-4-hydrogen-high` |
| `review` | Reviews a task's diff, or the project's uncommitted changes | The task's worktree or the project, read-only | `gemini-4-hydrogen-high` |
| `grill` | Challenges Claude's plan, changes or claim | The project, read-only | `gemini-4-argon-high` |

The reviewer defaults to a different model than the implementer, so a review is a second opinion
rather than the same model grading itself.

## Life of a task

```
Claude writes .agy/tasks/T-001.md
        │
agy-task run T-001
        ├─ 1. create a worktree and a branch (agy/T-001) outside your working copy
        ├─ 2. run `setup`, symlink `link` paths, copy `seed` files
        ├─ 3. agy works there and runs the verification itself
        ├─ 4. fold back any commits agy made; leaving the task branch fails the task
        ├─ 5. run `autofix` formatters; keep build artifacts out of the diff
        ├─ 6. audit everything outside the agreed area (strict mode: revert it)
        ├─ 7. run the project's verification again, independently of agy's report
        ├─ 8. on failure, send the output back to agy, up to `max_fixups` times
        └─ 9. print a short result: state, gates, audit, files, summary, decisions, recommendations
        │
Claude validates ──▶ accept · fix · recommend · grill · reject
```

`accept` applies the task's diff to your index as a single atomic patch (`git apply --index`):
either all of it lands, staged and uncommitted, or none of it does. Several tasks can be accepted
in a row, and they coexist with your own uncommitted work.

## Guarantees

These hold however much freedom agy has:

| Guarantee | How it is enforced |
|---|---|
| Nothing lands on your branch without Claude's `accept` | agy works on another branch, in another directory |
| `accept` never commits and never breaks work in progress | It applies an atomic patch to the index: all of it or nothing |
| What Claude accepts passed your verification | The executor runs it after agy, outside agy's own report |
| Claude knows what agy did beyond the agreement | Every file outside the agreed area is listed in the audit |
| Risky work is not accepted blindly | Medium risk, audit notes or a large diff require `accept --reviewed` |
| The executor's own state is never altered | `.agy/` and `.git/` in the worktree are restored if agy touches them |

## Modes

| | `collaborative` (default) | `strict` |
|---|---|---|
| agy's tools | Full: terminal, search, tests, file reading and editing | File reading and editing only; no terminal |
| Who runs the tests | agy while it works, and the executor before Claude accepts | The executor only |
| Work outside the agreed area | Kept and listed in the audit for Claude to judge | Reverted and logged as an incident |
| Search and file listing | agy's own tools; `search` terms become hints | The executor attaches a file map and pre-run searches |
| Containment probes | Not needed | Run live once per agy version; nothing is delegated if they fail |

In collaborative mode agy runs with `--dangerously-skip-permissions`: it can do anything you could
do from a terminal in that worktree, exactly as when you run agy yourself. The agreements in the
brief and Claude's validation are what keep it on track.

Strict mode exists for sensitive projects where you want hard technical limits instead of
agreements. Enable it with `mode = "strict"` in `.agy/config.toml`.

## Review levels

Every `implement` result carries a review level that tells Claude how much it must read before
accepting:

| Level | When | What `accept` requires |
|---|---|---|
| `summary` | Low risk, no audit notes, diff under `max_diff_lines` | Nothing extra |
| `diff` | Medium risk, any audit note, or an oversized diff | `accept --reviewed`, after reading `diff` |

High-risk work is never delegated.

## Task states

| State | Meaning | Next step |
|---|---|---|
| `review` · `summary` | Verification passed; low risk and nothing to audit | `accept` |
| `review` · `diff` | Verification passed; the diff must be read | `diff`, then `accept --reviewed` |
| `blocked` | agy has questions | `fix "answer"` (implement) or `reply "answer"` (other sessions) |
| `failed (gates)` | Verification still failed after the extra rounds | `fix "hint"`, `run --restart`, or do it by hand |
| `failed (git)` | agy left its task branch | Inspect the worktree, then usually `run --restart` |
| `failed (setup)` | Preparing the worktree failed | Fix `setup` or `link`, then run `baseline` again |
| `failed (executor)` | The executor itself failed after agy delivered; the work is kept | Fix the cause in `detail`, then `recheck` (no agy call) |
| `failed (quota·auth·timeout)` | agy itself failed | Wait, sign in again, or raise `timeout_min` |
| `done` | An explore, review, grill or answers report is ready | Use it, or follow up with `reply` |
| `accepted` · `rejected` | Closed | — |

## Audit notes

In collaborative mode the executor records, rather than undoes, anything that falls outside the
brief's agreements. The notes are information for Claude, not failures, and any of them raises the
review level to `diff`.

| Note | Meaning |
|---|---|
| `outside_agreed_area` | A file outside `allowed` changed |
| `protected_modified` | A `protected` file changed |
| `off_limits_modified` | A `forbidden` file changed |
| `supervisor_file_modified` | A `seed` file changed; it was restored |
| `executor_area_restored` | `.agy/` or `.git/` changed; they were restored |
| `agy_committed` | agy committed; the commits were folded back into the index |
| `branch_changed` | agy switched branches |
| `tree_modified_during_read_only` | A read-only session changed files |
