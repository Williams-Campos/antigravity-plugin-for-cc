# Configuration

## Project configuration

Each project keeps its settings in `.agy/config.toml`, created by `agy-task init`. Every key is
optional, but implementation is never delegated without at least one `verify` command.

```toml
mode = "collaborative"
verify = ["python3 -m pytest -q"]
link = ["node_modules"]
setup = []
autofix = ["ruff format ."]
```

| Key | Default | Purpose |
|---|---|---|
| `mode` | `"collaborative"` | `collaborative` or `strict` (see [How it works](how-it-works.md#modes)) |
| `verify` | `[]` | Commands that define "correct". Run by agy while it works and by the executor before Claude accepts |
| `link` | `[]` | Paths git does not copy into the worktree, symlinked instead: installed dependencies, a local SDK |
| `setup` | `[]` | Commands that prepare the worktree before agy starts, such as `npm ci` |
| `autofix` | `[]` | Formatters the executor runs after every agy turn |
| `artifacts` | `[]` | Extra build artifacts kept out of the diff. Python and Node caches already are |
| `model_implement` | `gemini-4-argon-high` | Implementer |
| `model_explore`, `model_review` | `gemini-4-hydrogen-high` | Explorer and reviewer; the reviewer is ideally not the implementer |
| `model_grill` | `gemini-4-argon-high` | External check of Claude's work |
| `max_fixups` | `2` | Extra rounds when verification fails, before control goes back to Claude |
| `max_diff_lines` | `800` | Above this, the task requires reading the diff |
| `timeout_min` | `30` | Limit per agy turn, in minutes |
| `verify_timeout_min` | `15` | Limit per verification command, in minutes |
| `worktree_root` | `~/.agy-bridge/worktrees` | Where task worktrees are created |
| `skills` | `[]` | Team skills both agents follow (see [Team skills](#team-skills)) |

Brief headers can override `model`, `verify`, `max_fixups`, `max_diff_lines` and `timeout_min`
per task.

## User configuration

`~/.agy-bridge/config.toml` takes the same keys and sets defaults for every project. The order is:
built-in defaults, then the user file, then the project's `.agy/config.toml`. A key set in the
project replaces the user value entirely.

## Team skills

A team skill is a Claude Code skill that both agents follow, so code written by Claude and code
written by agy obey the same rules.

```toml
# ~/.agy-bridge/config.toml
skills = ["ponytail"]
```

- **Entries** are skill names, resolved to `~/.claude/skills/<name>/SKILL.md` (the same file
  Claude loads), or paths to a skill file.
- **agy** receives the text of every skill, without its front matter, at the start of each
  session: implement, explore, review, grill and answers. Follow-up turns in the same
  conversation (`fix`, `recommend`, `reply`) do not resend it. The brief and agy's rules take
  precedence over a skill.
- **Claude** is told by the bundled skill to run `agy-task doctor`, which lists the team skills,
  and to load each one before writing code, briefs or validations.
- **A missing skill stops the task** before agy is called, with the path that was expected.
- **To opt a project out**, set `skills = []` in its `.agy/config.toml`.

Install a skill for Claude by placing its folder in `~/.claude/skills/`, for example
`~/.claude/skills/ponytail/SKILL.md`.

## Choosing models

`agy models` lists the models your account can use. The suffix of a model name is its reasoning
effort (`-low`, `-medium`, `-high`, and `-xhigh` where available).

- **Argon** is thorough: the default for implementing and for challenging Claude's work. Expect
  minutes per task.
- **Hydrogen** is quick: the default for exploration and review.

## Project files

| Path | Contents | Tracked by git |
|---|---|---|
| `.agy/config.toml` | Project configuration | Your choice |
| `.agy/tasks/` | Briefs, one file per task | Your choice |
| `.agy/runs/` | State, logs, agy's reports and `usage.jsonl` | No (`.agy/.gitignore` excludes it) |

To keep `.agy/` out of the repository entirely without touching `.gitignore`, add it to
`.git/info/exclude`.

## Environment

| Variable | Purpose |
|---|---|
| `AGY_BRIDGE_PYTHON` | Pin the Python interpreter (3.11 or newer) used by `agy-task`. By default the launcher finds one even when the `python3` on your `PATH` is older |
