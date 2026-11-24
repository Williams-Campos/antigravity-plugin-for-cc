<h1 align="center">Antigravity plugin for Claude Code</h1>

<p align="center">
  <strong>Claude Code and Antigravity (<code>agy</code>, Gemini) working on your project as a team.</strong><br>
  Claude plans, briefs and validates. agy implements, with its full toolset, in its own git worktree.
</p>

<p align="center">
  <a href="https://github.com/Williams-Campos/antigravity-plugin-for-cc/actions/workflows/ci.yml"><img src="https://github.com/Williams-Campos/antigravity-plugin-for-cc/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/version-0.7.0--beta-blue" alt="version">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="python">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="license: MIT"></a>
</p>

---

## Overview

Two capable coding agents are more useful as a team than as alternatives. This plugin gives them
clear roles:

- **Claude is the senior engineer.** It analyses what you want, decides the architecture, splits
  the work, writes a precise brief for each piece it delegates, and validates what comes back.
- **agy is the experienced junior.** It implements each brief with its full toolset (terminal,
  search, tests) in an isolated git worktree, runs the verification itself and iterates.
- **You stay in charge.** Nothing reaches your branch until Claude accepts it, and nothing is
  committed until you decide.

The two agents talk through a small protocol. Claude can give agy an instruction, a non-binding
suggestion or a set of questions. agy can push back, recommend a better path, or act as an
external reviewer that challenges Claude's own plan.

## Highlights

- **Isolated by design.** Every task runs on its own branch in its own worktree, outside your
  working copy.
- **Verified independently.** Your project's tests run after agy finishes, separately from agy's
  own report.
- **Audited, not caged.** Work outside the agreed area is kept and reported to Claude, not
  silently reverted.
- **Atomic integration.** `accept` stages the whole change or none of it, and never commits.
- **Two-way review.** `grill` lets a second model, without Claude's context, challenge Claude's
  plans and changes.
- **Shared skills.** Team skills such as a coding style reach both agents, so Claude and agy
  write code by the same rules.
- **Zero dependencies.** A single Python file and a shell launcher.

## How it works

```
 You ──▶ Claude analyses and splits the work
              │
              ├─ keeps: architecture, ambiguous or sensitive parts, integration
              │
              └─ delegates: writes a brief ──▶ agy implements in its own worktree
                                                   │  runs the tests, iterates
                                                   ▼
                                          executor: audit + verification
                                                   │
              Claude validates ◀───────────────────┘
              │   accept · fix · recommend · grill · reject
              ▼
 You ◀── staged changes, ready for your commit
```

The full picture — roles, the life of a task, guarantees and modes — is in
[How it works](docs/how-it-works.md).

## Requirements

- [Antigravity CLI](https://antigravity.google/) (`agy`), installed and signed in
- [Claude Code](https://claude.com/claude-code)
- `git` and Python 3.11 or newer
- macOS or Linux (on Windows, use WSL)

## Installation

```bash
git clone https://github.com/Williams-Campos/antigravity-plugin-for-cc.git
```

```bash
cd antigravity-plugin-for-cc && ./install.sh
```

The installer creates two symlinks, `~/.local/bin/agy-task` and `~/.claude/skills/agy-bridge`,
and then runs `agy-task doctor`. It changes nothing in your Claude Code or agy configuration.
Run `./install.sh --uninstall` to remove them.

## Quick start

Set up a project once:

```bash
cd my-project
agy-task init       # creates .agy/ and suggests a verification command
agy-task baseline   # checks that verification passes, without spending quota
```

Then, in Claude Code, ask for the work as you normally would and say that agy should help:

> Add CSV export to the reports module. Work on it with agy.

Claude shows you how it is splitting the work, writes the briefs, runs agy, validates the
results and stages the changes for your review.

To drive it by hand instead:

```bash
agy-task new T-001 --title "Add slugify to textutil"   # then fill in .agy/tasks/T-001.md
agy-task run T-001
agy-task accept T-001
```

## Talking to agy

| Command | Direction | Purpose |
|---|---|---|
| `fix <id> "…"` | Claude → agy | An instruction; the gates run again |
| `recommend <id> "…"` | Claude → agy | A suggestion; agy adopts it or explains why not |
| `grill <id> "…"` | Claude → agy | Questions about delivered work, answered with evidence |
| `grill --file` · `--working` · `--text` | agy → Claude | An external check of Claude's plan, changes or claim |
| `reply <id> "…"` | Claude → agy | Continue an explore, review or grill session |

Every report from agy also carries its own `recommendations`.

## Documentation

| Guide | Contents |
|---|---|
| [How it works](docs/how-it-works.md) | Workflow, roles, the life of a task, guarantees, modes, states |
| [Writing a brief](docs/briefs.md) | Format, sections, header fields, tips |
| [Command reference](docs/commands.md) | Every command, with examples and exit codes |
| [Configuration](docs/configuration.md) | `.agy/config.toml`, user defaults, team skills, models |
| [Troubleshooting](docs/troubleshooting.md) | Common problems and known limitations |
| [Field results](docs/field-results.md) | How it behaved on real projects |

## Security and privacy

- In the default **collaborative** mode, agy can run any command in its worktree with your
  user's permissions, as when you run agy yourself. For hard technical limits instead, set
  `mode = "strict"`: no terminal, and out-of-scope changes are reverted.
- **Delegated code is sent to Google.** Do not delegate files that contain secrets.

## Status

Beta. Tested on macOS MacBook Air M1 8GB with agy (antigravity) 1.5.8 to 1.5.10, on a Flutter project and a NumPy project; the
test suite also runs on Linux. See the [changelog](CHANGELOG.md) for what changed in each release.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). This is an independent project, not affiliated with or endorsed by Google or
Anthropic. "Antigravity", "Gemini", "Claude" and "Claude Code" are trademarks of their respective
owners. Use of agy and Claude is governed by each service's terms.
