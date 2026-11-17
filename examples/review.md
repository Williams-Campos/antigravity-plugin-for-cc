+++
id = "R-001"
title = "Review of slugify"
role = "review"
target = "T-001"
+++

## Goal
The change adds `slugify(text, max_length=None)` to `src/textutil.py`. It must strip accents, use only `[a-z0-9]` separated by single hyphens and, with `max_length`, never split words. Check these edge cases against the code: `max_length` shorter than the first word, `max_length = 0`, and empty text.
