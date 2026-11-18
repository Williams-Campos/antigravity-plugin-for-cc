# Contributing

Issues and pull requests are welcome.

## Repository layout

```
bin/agy-task           launcher: finds a Python 3.11+ and runs the executor
lib/agy_task.py        the executor: a single file, standard library only
rules/                 the instructions agy receives, per mode and role
  collaborative/
  strict/
templates/             blank briefs and the project configuration
skill/SKILL.md         the Claude Code skill
examples/              complete example briefs, one per role
docs/                  user documentation
tests/                 the test suite and a fake agy
install.sh             symlinks agy-task and the skill into your home directory
```

## Running the tests

The suite never calls the real agy and spends no quota. `tests/fake_agy` stands in for it,
replaying a scripted plan of file writes, shell commands and structured reports.

```bash
python3 tests/test_agy_task.py
```

CI runs the same suite on Linux and macOS with Python 3.11 and 3.13.

## Guidelines

- **Keep the executor dependency-free.** Standard library only, Python 3.11+.
- **Add a test for any behaviour change.** Script agy's side with a fake-agy plan.
- **Update [`CHANGELOG.md`](CHANGELOG.md)** under a new version heading.
- **Keep the rules and the skill in sync.** A change to what agy is told in `rules/` usually needs
  a matching change in what Claude is told in `skill/SKILL.md`.
