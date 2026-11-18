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

Brief headers can override `model`, `verify`, `max_fixups`, `max_diff_lines` and `timeout_min`
per task.

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
