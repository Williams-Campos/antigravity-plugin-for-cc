---
name: agy-bridge
description: Delegates work to Antigravity (agy / Gemini) as a strictly supervised worker through the `agy-task` command. Use it when the user asks to "use agy", "delegate to agy/Gemini" or "let agy do it", or when there is well-specified, verifiable implementation work, broad code exploration or a first-pass review that does not need Claude's judgment. Claude decides, writes the manual and accepts or rejects; agy works in isolation, without a terminal.
---

# agy-bridge — agy as a supervised worker

You (Claude) are the lead: you decide, specify and accept. agy is the worker: it carries out a manual inside an isolated worktree, without a terminal and unable to write outside its folder. `agy-task` applies automatic gates and returns a short result. **Your attention is the scarce resource: do not re-read what the gates already guarantee.**

## When to delegate

| Delegate to agy | Do it yourself |
|---|---|
| Implementation whose acceptance criteria a command can verify (tests, build, lint) | Architecture, design, ambiguous requirements |
| Exploration: "where and how is X done?" (`explore` role) | Small edits (< ~30 lines): the round trip costs more |
| Tests, mechanical migrations, boilerplate | Sensitive code: security, payments, data, database migrations |
| A first-pass review of a diff by a different model (`review` role) | Anything that cannot be verified automatically |

## Workflow

1. Once per project: `agy-task init`, then fill in `.agy/config.toml` with the project's verification command (`verify`), the paths git does not copy (`link`: dependencies, a local SDK) and the formatter (`autofix`). Then `agy-task baseline`: it checks, without spending agy quota, that verification passes in a clean worktree. If it fails, nothing you delegate can pass.
2. `agy-task new <ID> --role implement|explore|review --title "..."` and **fill in the manual** at `.agy/tasks/<ID>.md`.
3. `agy-task check <ID>` until it is valid.
4. `agy-task run <ID>`. If it may take more than 2 minutes, run it in the background (Bash with `run_in_background`) and move on to something else; do not poll.
5. Read **only the result** it prints (`agy-task result <ID>` shows it again) and act on the state.

## Writing a good manual (implement)

The manual is the only information agy has. Whatever you do not decide, agy decides.

- **Goal**: observable behaviour, not steps.
- **Context**: exact paths to read and the existing pattern to follow. agy has no search or listing: it receives a path map and the results for the terms you put in `search` (exact text, e.g. a class name).
- **Approach**: every design decision already made (signatures, names, allowed libraries).
- **Acceptance criteria**: verifiable, with concrete values. Ideally, write the tests yourself first and list them in `seed`: agy receives them even though they are not committed, cannot modify them, and they stay out of its diff. That makes the contract executable.
- If you are not sure of an expected value, say so in the manual and ask for `blocked` on any discrepancy, instead of letting agy "fix" it.
- **allowed** as narrow as possible; **risk** honest.
- One task = one coherent change. If you cannot write verifiable criteria, do not delegate it.

## What to do with each state

| State | Meaning | Action |
|---|---|---|
| `review` · review `summary` | Gates passed, low risk, no incidents | `agy-task accept <ID>` without reading the diff |
| `review` · review `diff` | Gates passed, but medium risk, incidents or a large diff | `agy-task diff <ID>`, read it, then `accept <ID> --reviewed` |
| `blocked` | agy has questions | Answer with `agy-task fix <ID> "..."` |
| `failed (gates)` | Did not pass verification after the fix-up rounds | `fix` with a concrete hint, `run --restart` with a better manual, or do it yourself |
| `failed (quota/auth/timeout)` | Executor failure | Tell the user; do not retry in a loop |
| `failed (setup)` | Preparing the worktree failed, before agy was called | Fix `setup`/`link` in `.agy/config.toml` and run `agy-task baseline` |
| `done` | `explore` or `review` report ready | Use it; verify yourself anything that will support an important decision |

`accept` leaves the changes **staged, not committed**, on the current branch. Committing follows the user's normal rules.

Each task is verified on its own, in its worktree. After accepting several tasks, run the project's verification once on the combined result before calling the work done.

## Patterns that pay off

- **Explore before specifying**: an `explore` run (20–60 s) gives you paths, lines and gaps to write a precise manual without reading the code yourself. Check two or three of its references before trusting it.
- **Parallel**: launch independent tasks at the same time (each in the background). Verification dominates the time, not agy.
- **Cross-review**: after an `implement`, a `review` with `target = "<ID>"` uses a different model and takes ~1 minute. If it finds something real, pass it to agy with `fix`.
- **Executable contract**: write the test yourself, put it in `seed` and let agy implement until it passes.

## Commands

```
agy-task init | baseline | status | stats | doctor [--probe]
agy-task new <ID> --role R --title "..." [--target <ID>|working]
agy-task check|run|result|cancel <ID>      run: --restart, --allow-overlap
agy-task fix <ID> "message for agy"
agy-task diff <ID> [--stat] [paths...]
agy-task accept <ID> [--reviewed] [--keep]   ·   agy-task reject <ID> [--reason "..."]
```

Exit codes of `run`/`fix`: 0 ready · 2 blocked · 3 gates failed · 4 executor failure · 10 quota · 11 authentication · 12 timeout.

A `failed (gates)` result already includes the tail of the failed verification and the files agy left: you usually do not need to open the logs. `agy-task stats` summarises attempts, time and usage: use it to decide, with data, whether delegating is paying off in this project.

## Non-negotiable rules

- Never accept a task that requires `--reviewed` without having read the diff.
- Never edit agy's worktree by hand to "help" it pass: correct it with `fix` or do it yourself from scratch.
- Incidents (out-of-scope changes, modified tests) are reverted automatically, but they count: two tasks in a row with incidents point to an ambiguous manual; rewrite it.
- Do not run `implement` tasks with overlapping `allowed` in parallel (the executor blocks it).
- Several independent tasks may run in parallel, each in the background.
- agy's containment is checked automatically once per agy version, before the first task (it takes ~20 s). If it fails, the executor refuses to delegate: tell the user, do not look for a workaround.
- The project's code is sent to Google when you delegate. Do not delegate files that contain secrets.
