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
Read `src/textutil.py` (the module's style) and `tests/test_slugify.py` (it defines the exact behaviour).

## Approach
- Signature: `slugify(text: str, max_length: int | None = None) -> str`.
- Standard library only (`unicodedata`, `re`). No new dependencies.
- Strip accents, lowercase, and replace any run of characters that are not ASCII letters or digits with a single hyphen; no leading or trailing hyphens.
- With `max_length`, truncate without splitting words: keep only the whole words that fit.
- One-line docstring, like the rest of the module.

## Acceptance criteria
- Every test in `tests/test_slugify.py` passes without being modified.
- The module's existing functions do not change.

## Out of scope
- Do not create other files or touch the README.
