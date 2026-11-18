+++
id = "T-001"
title = "Add slugify to textutil"
role = "implement"
risk = "low"
allowed = ["src/textutil.py"]
protected = ["tests/**"]
+++

## Goal
Add a `slugify` function to `src/textutil.py` that turns titles into URL-safe identifiers.

## Context
`src/textutil.py` holds small text helpers in a consistent style; `tests/test_slugify.py` defines the exact behaviour expected.

## Decisions
- Signature: `slugify(text: str, max_length: int | None = None) -> str`.
- Output uses only `[a-z0-9]` separated by single hyphens; accents are stripped.
- With `max_length`, keep only the whole words that fit; never split a word.

## Agreements
- Standard library only; no new dependencies.
- The module's existing functions do not change.

## Acceptance criteria
- Every test in `tests/test_slugify.py` passes without being modified.

## Expected output
- List the edge cases you covered beyond the tests.
