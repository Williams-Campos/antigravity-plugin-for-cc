+++
id = "{{id}}"
title = "{{title}}"
role = "implement"
risk = "medium"            # low: accepted on the summary · medium: Claude reads the diff · high: not delegated
allowed = ["«src/module/**»"]          # agreed area: the files this task is expected to create or modify
protected = ["«tests/**»"]             # files agy must not modify (they define what is correct)
# forbidden = []                       # off limits inside or outside the agreed area
# seed = ["«tests/new_test»"]          # your uncommitted files agy must see (restored if it changes them)
# search = ["«ClassName»"]             # starting points: exact text worth searching for
# verify = ["«test command»"]          # if omitted, uses verify from .agy/config.toml
# max_fixups = 2
# max_diff_lines = 800
# timeout_min = 30
+++

## Goal
«What must work when this is done, and why, in 2–4 lines. Observable behaviour, not steps.»

## Context
«Where this lives: files and functions to read first, the existing pattern to follow, anything agy would otherwise lose time discovering.»

## Decisions
«What is already decided and not up for discussion: interfaces, names, signatures, libraries, architecture. Everything you leave out is agy's call.»

## Agreements
«Limits beyond the header, e.g. do not change the public API, no new dependencies, standard library only.»

## Acceptance criteria
- «Verifiable condition 1 (ideally a specific test that must pass)»
- «Verifiable condition 2»

## Expected output
«Anything you want in the report beyond the defaults, e.g. "list the edge cases you covered". Delete this section if the defaults are enough.»
