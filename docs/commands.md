# Command reference

All commands run from inside the project (any directory of the git repository). Inside Claude
Code the skill runs them for you; this page is for when you want to drive `agy-task` yourself or
understand what Claude is doing.

- [Setup](#setup)
- [Running tasks](#running-tasks)
- [Talking to agy](#talking-to-agy)
- [Inspecting and closing](#inspecting-and-closing)
- [Exit codes](#exit-codes)

## Setup

| Command | Description |
|---|---|
| `init` | Create `.agy/` with a configuration file and suggest a verification command |
| `baseline` | Run the verification on the last commit in a clean worktree, without agy and without spending quota |
| `doctor [--probe]` | Check the installation; with `--probe`, probe strict-mode containment live |

```bash
agy-task init
$EDITOR .agy/config.toml
agy-task baseline
```

## Running tasks

| Command | Description |
|---|---|
| `new <id> [--role …] --title "…" [--target …]` | Create a brief from the template (`--target` for reviews) |
| `check <id>` | Validate a brief without running it |
| `run <id> [--restart] [--allow-overlap]` | Run the task and apply the gates. `--restart` discards a previous attempt; `--allow-overlap` permits an agreed area that overlaps another running task |
| `recheck <id>` | Run the gates again on agy's last delivery, without calling agy: after fixing a configuration or executor problem, or correcting the worktree by hand. If the delivery still does not pass, the task fails and agy gets the correction through `fix` |

```bash
agy-task new T-001 --title "Add slugify to textutil"
agy-task check T-001
agy-task run T-001
```

## Talking to agy

| Command | Direction | Meaning |
|---|---|---|
| `fix <id> "…"` | Claude → agy | An instruction. agy applies it and the gates run again |
| `recommend <id> "…"` | Claude → agy | A suggestion, not an order. agy adopts it, and implements it, or declines it with a reason |
| `grill <id> "questions"` | Claude → agy | Claude questions agy about delivered work. agy answers with evidence and changes nothing |
| `grill --file F` · `--working` · `--text "…"` | agy → Claude | An external check: a different model, without Claude's context, challenges a plan, the uncommitted changes or a claim |
| `reply <id> "…"` | Claude → agy | Continue an explore, review, grill or answers session |

Every report also carries `recommendations`: risks, follow-up work or better approaches agy noticed
on its own.

### `fix` and `recommend`

```bash
agy-task fix T-001 "Return an empty string for empty input instead of raising."
agy-task recommend T-001 "Consider unicodedata.normalize instead of the manual accent table."
```

`fix` is binding. `recommend` is not: the result's `suggestion` field says whether agy adopted
it and why. A declined recommendation leaves the code unchanged.

### `grill`

Questioning agy about a task runs in the task's own conversation, so agy answers with full memory
of what it did. Runs are named `<id>-q1`, `<id>-q2`…

```bash
agy-task grill T-001 "Why a regex instead of str.translate? What happens with emoji?"
```

Asking agy to challenge Claude's own material starts a fresh session with no knowledge of Claude's
reasoning, which is the point. Runs are named `G-001`, `G-002`…

```bash
agy-task grill --file docs/plan.md --focus "edge cases and wrong assumptions"
agy-task grill --working
agy-task grill --text "The cache can be dropped: every caller already memoises."
```

The verdict is `sound`, `concerns` or `unsound`, with a list of objections. Each objection has a
severity, the claim it disputes, the challenge and its evidence, with path and line when it refers
to code.

### `reply`

```bash
agy-task reply G-001 "Objection 2 does not apply: the input is validated in parse()."
```

On a grill, agy re-evaluates and keeps only the objections that still stand, then issues a new
verdict.

## Inspecting and closing

| Command | Description |
|---|---|
| `result <id>` | Show the result, or the progress while it is still running |
| `diff <id> [--stat] [paths…]` | Show a task's diff |
| `accept <id> [--reviewed] [--keep]` | Integrate the work into the current branch, staged and not committed. `--keep` keeps the worktree and the branch |
| `reject <id> [--reason "…"]` | Discard the work: removes the worktree and the branch |
| `cancel <id>` | Cancel a running task or session, including verification in progress |
| `status` | List tasks and sessions with their states |
| `stats` | Summarise sessions, attempts, time and usage per role |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Ready: `review` or `done` |
| `1` | Usage error or invalid brief |
| `2` | Blocked: agy has questions |
| `3` | Verification gates failed |
| `4` | Executor failure |
| `10` | agy quota exhausted |
| `11` | agy authentication failed |
| `12` | agy timed out |
