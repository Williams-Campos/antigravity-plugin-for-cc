# Writing a brief

A brief is everything agy knows about a task. Claude writes it; the quality of agy's work follows
directly from it. Complete examples for every role live in [`examples/`](../examples/).

## Format

A brief is a Markdown file in `.agy/tasks/`, named after its id, with a TOML header between `+++`
lines:

```markdown
+++
id = "T-001"
title = "Add slugify to textutil"
role = "implement"
risk = "low"
allowed = ["src/textutil.py"]
protected = ["tests/**"]
+++

## Goal
Add `slugify` to `src/textutil.py` to turn titles into URL-safe identifiers.

## Context
`tests/test_slugify.py` defines the exact behaviour expected.

## Decisions
- Signature: `slugify(text: str, max_length: int | None = None) -> str`.

## Agreements
- Standard library only.

## Acceptance criteria
- Every test in `tests/test_slugify.py` passes without being modified.
```

Create one from the template with `agy-task new T-001 --title "…"` and validate it with
`agy-task check T-001`. The template marks every blank with `«…»`; a brief that still contains one
is rejected until it is filled in.

## Sections

| Section | Required | What goes in it |
|---|---|---|
| `## Goal` | Always | What must work when the task is done, and why. Observable behaviour, not steps. |
| `## Context` | Recommended | Files and functions to read first, the pattern to follow, anything agy would otherwise spend time discovering. |
| `## Decisions` | Recommended | What Claude has settled: interfaces, names, signatures, libraries. Everything left out is agy's call. |
| `## Agreements` | Recommended | Limits beyond the header, such as "no new dependencies" or "do not change the public API". |
| `## Acceptance criteria` | `implement` | Verifiable conditions, ideally specific tests that must pass. |
| `## Expected output` | Optional | Anything wanted in the report beyond the defaults. |

agy explains its non-obvious choices in the report, so a short `Decisions` section is a feature:
it leaves room for agy's judgement while fixing what must not move.

## Header fields

| Field | Roles | Meaning |
|---|---|---|
| `id`, `title` | all | Identifier (must match the file name) and a short title |
| `role` | all | `implement`, `explore` or `review`. Grill sessions need no brief |
| `risk` | implement | `low`: may be accepted on the summary · `medium`: the diff must be read · `high`: never delegated |
| `allowed` | implement, explore | The agreed area: files the task is expected to touch. For `explore`, the areas of interest |
| `protected` | implement | Files that define what is correct, usually tests. agy must not change them |
| `forbidden` | implement | Off limits |
| `seed` | implement | Your uncommitted files that agy must see, such as a test you just wrote. Restored if agy changes them, and never part of its diff |
| `search` | all | Exact strings worth searching for. In strict mode the executor runs the search and attaches the results |
| `verify` | implement | Verification commands. Defaults to the ones in `config.toml` |
| `target` | review | Id of the task to review, or `"working"` for the project's uncommitted changes |
| `model`, `max_fixups`, `max_diff_lines`, `timeout_min` | all | Override the project defaults |

## Paths

Paths are relative to the repository root. `**` matches across directories; `*` and `?` do not.
A directory covers everything below it.

## Tips

- **Prefer tests over prose.** A failing test Claude writes and passes as `seed` is the most
  precise acceptance criterion there is.
- **Name the pattern to follow.** "Follow the structure of `src/parsers/csv.py`" saves agy a
  search and keeps the codebase consistent.
- **Keep one concern per task.** Independent tasks run in parallel; tangled ones block each other.
- **Mark the risk honestly.** `risk = "low"` lets Claude accept on the summary; use it only when a
  mistake would be caught by verification.
