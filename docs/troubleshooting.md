# Troubleshooting and limitations

## Common problems

| Symptom | Cause and fix |
|---|---|
| `BASELINE VERIFICATION FAILS` | Verification does not pass even without agy's changes: something is missing from `link` or `setup`, or the project was already broken. See `.agy/runs/_baseline.log` |
| Build artifacts appear in a diff | Add their pattern to `artifacts` in `config.toml` |
| `failed (git)` | agy switched branches in its worktree. Inspect it with `git -C <worktree> status`, then `run --restart` |
| Repeated `failed (gates)` on formatting or lint | Add the formatter to `autofix` |
| `could not integrate` on accept | The task's files changed in the project since the task started. Commit or discard those changes, or `run --restart` |
| `containment check failed for agy X` | Strict mode only: that agy version does not enforce the expected permissions. Run `agy-task doctor --probe` again |
| `requires Python 3.11` | Set `AGY_BRIDGE_PYTHON` to the path of a recent Python |
| `agy-task: command not found` | `~/.local/bin` is not on your `PATH` |

`agy-task doctor` checks the whole installation and is the first thing to run when something
looks wrong.

## Known limitations

- **No verification command, no delegated implementation.** Without one Claude has nothing
  objective to accept on.
- **In collaborative mode agy can run anything** in its worktree, with your user's permissions,
  exactly like agy used directly. The worktree keeps it off your working copy and your branch,
  not off your machine. Use `mode = "strict"` where that is not acceptable.
- **Linked paths are shared.** Whatever is in `link` (such as `node_modules`) is the project's
  real folder; agy is told not to modify it.
- **The worktree starts from the last commit.** Uncommitted changes do not reach agy, except for
  the files listed in `seed`.
- **Your code is sent to Google** when you delegate. Do not delegate files that contain secrets.
- **Quota depends on your Google plan.** A quota failure ends the task with exit code `10`.
- **Argon is thorough, not fast.** Expect minutes per implement task; use Hydrogen for quick
  exploration.
