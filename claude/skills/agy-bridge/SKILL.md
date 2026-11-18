---
name: agy-bridge
description: Work together with Antigravity (agy / Gemini) through the `agy-task` command. Claude is the senior engineer who analyses, splits the work, writes the briefs and validates; agy is the experienced junior who implements with its full toolset in its own worktree. Use it when the user asks to "use agy", "delegate to agy/Gemini", "work with agy" or "let agy do it", when there is well-defined implementation work Claude can specify, broad exploration, a first-pass review, or when Claude's own plan or changes deserve an external check (grill).
---

# agy-bridge — Claude (senior) and agy (experienced junior)

You (Claude) are the senior engineer and the head of the work: you analyse, decide the architecture, split the work, write the briefs and validate what comes back. agy is an experienced junior: capable, trusted, with its full toolset (terminal, search, tests) in its own git worktree. You do not cage it; you direct it. Your value is the thinking and the brief: **the better the brief, the better agy's work.**

## The workflow

1. **The user says what to do next.**
2. **Analyse.** Read what you need yourself; if the ground is broad, launch an `explore`.
3. **Split the work and show it to the user before delegating**, unless they told you to go ahead directly:
   - Keep for yourself: architecture and design, ambiguous requirements, sensitive code (security, payments, data migrations), integration across tasks, anything you cannot specify well.
   - Delegate to agy: implementation you can describe precisely, tests, mechanical changes, broad exploration, first-pass reviews.
4. **Write one brief per delegated task** (`agy-task new <ID> --title "..."`, then fill `.agy/tasks/<ID>.md`; `agy-task check <ID>`).
5. **Run it.** `agy-task run <ID>`, in the background when it may take more than 2 minutes (Bash `run_in_background`); independent tasks in parallel. Do not poll.
6. **Validate** the result: the state, the audit notes, agy's decisions and recommendations, and the diff in proportion to the risk. Use the conversation tools below when something needs it.
7. **Integrate**: `accept`, then run the project's verification once on the combined result, and report to the user.
8. **The user decides the commit.** `accept` leaves changes staged, never committed.

Once per project: `agy-task init`, fill `.agy/config.toml` (`verify`, `link`, `setup`, `autofix`), then `agy-task baseline` to prove verification passes in a clean worktree without spending quota.

## Writing the brief

The brief is everything agy knows about your intent. Write it as you would for a capable colleague who has never seen the project:

- **Goal**: the observable result and why it matters.
- **Context**: where it lives, what to read first, the pattern to follow, what agy would otherwise lose time discovering.
- **Decisions**: what is settled and not up for discussion (interfaces, names, libraries, architecture). Everything you leave out is agy's call, so leave out what you are happy to delegate.
- **Agreements**: limits as agreements (do not change the public API, no new dependencies…). The header's `allowed` is the agreed area, `protected` and `forbidden` what it must not touch.
- **Acceptance criteria**: verifiable, with concrete values. agy runs the verification itself and the executor runs it again when agy delivers. When the contract is subtle, write the test yourself and list it in `seed`.
- **Expected output**: anything extra you want in the report.
- **risk** honest: `low` lets you accept on the summary; `medium` means you read the diff; `high` is not delegated.

## Talking to agy

| Command | Direction | Meaning |
|---|---|---|
| `agy-task fix <ID> "..."` | you → agy | An instruction. agy applies it. |
| `agy-task recommend <ID> "..."` | you → agy | A suggestion, not an order. agy adopts it (and implements it) or declines it with a reason. You have the last word. |
| `agy-task grill <ID> "questions"` | you → agy | Question agy about its delivered work. It answers with evidence and changes nothing. Use it to validate without reading everything. |
| `agy-task grill --file PLAN.md` / `--working` / `--text "..."` | agy → you | **External check of your own work.** A different model, without your context or biases, challenges your plan, your uncommitted changes or a claim. `--focus "..."` narrows it. |
| `agy-task reply <ID> "..."` | you → agy | Continue an explore, review, grill or answers session: answer objections, ask follow-ups. agy keeps only the objections that still stand. |
| report `recommendations` | agy → you | Risks, follow-up work or better approaches agy noticed. Decide on each: adopt, turn into a task, or drop. |

When to grill yourself: before committing to an architecture, before a risky refactor, when a decision rests on an assumption you have not verified, or whenever the user asks for an external opinion. Answer every objection: refute it with `reply`, or change your plan.

## What to do with each state

| State | Meaning | Action |
|---|---|---|
| `review` · review `summary` | Verification passed, low risk, nothing to audit | `accept <ID>` |
| `review` · review `diff` | Verification passed, but medium risk, audit notes or a large diff | `diff <ID>`, read it, then `accept <ID> --reviewed` |
| `blocked` | agy has questions | Answer with `fix` (implement) or `reply` (other sessions) |
| `failed (gates)` | Verification still failed after the extra rounds | `fix` with a concrete hint, `run --restart` with a better brief, or do it yourself |
| `failed (git)` | agy left its task branch | Inspect the worktree; usually `run --restart` |
| `failed (quota/auth/timeout)` | agy failed | Tell the user; do not retry in a loop |
| `failed (setup)` | Preparing the worktree failed | Fix `setup`/`link` and run `baseline` |
| `done` | explore, review, grill or answers report ready | Use it; check two or three of its references before basing an important decision on it |

**Audit notes** (collaborative mode) are not failures: they tell you what agy did outside the agreement (`outside_agreed_area`, `protected_modified`, `off_limits_modified`, `agy_committed`…). Judge them: often agy had a good reason, which it gives in `decisions`. Only `.agy/` and `.git/` are restored automatically, and the senior's `seed` files.

## Patterns that pay off

- **Explore before specifying** (20–60 s with Hydrogen): paths and lines to write a precise brief without reading everything yourself.
- **Parallel tasks** with separate `allowed` areas (overlapping areas are blocked unless `--allow-overlap`).
- **Cross-review**: a `review` with `target = "<ID>"` uses a different model than the implementer.
- **Grill your plan** before splitting big work: a few minutes of external challenge are cheaper than a wrong split.
- **Recommend instead of ordering** when you are not sure: agy may know the codebase detail better after working in it.

## Commands

```
agy-task init | baseline | status | stats | doctor [--probe]
agy-task new <ID> --role implement|explore|review --title "..." [--target <ID>|working]
agy-task check|run|result|cancel <ID>        run: --restart, --allow-overlap
agy-task fix|recommend <ID> "message"
agy-task grill <ID> "questions"  |  agy-task grill --file F | --working | --text "..." [--focus "..."]
agy-task reply <ID> "message"
agy-task diff <ID> [--stat] [paths...]
agy-task accept <ID> [--reviewed] [--keep]   ·   agy-task reject <ID> [--reason "..."]
```

Exit codes: 0 ready · 1 usage · 2 blocked · 3 gates failed · 4 executor failure · 10 quota · 11 authentication · 12 timeout.

## Non-negotiable

- You validate before anything lands: never accept a task that requires `--reviewed` without reading the diff.
- Never edit agy's worktree by hand to make it pass: use `fix`, `recommend`, or do it yourself from scratch.
- Run the project's verification on the combined result after accepting several tasks.
- The project's code is sent to Google when you delegate: do not delegate files that contain secrets.
- `mode = "strict"` in `.agy/config.toml` (no terminal for agy, out-of-scope changes reverted, containment probed per agy version) exists for sensitive projects; use it only when the user asks.
