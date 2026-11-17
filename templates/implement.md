+++
id = "{{id}}"
title = "{{title}}"
role = "implement"
risk = "medium"            # low: accepted on the summary · medium: Claude reads the diff · high: not delegated
allowed = ["«src/module/**»"]          # the only files agy may create or modify
protected = ["«tests/**»"]             # agy may not touch them (tests that define "correct")
# forbidden = []                       # exclusions inside allowed
# seed = ["«tests/new_test»"]          # your uncommitted files agy must see (it cannot change them)
# search = ["«ClassName»"]             # exact text the executor searches for and attaches (agy has no search)
# verify = ["«test command»"]          # if omitted, uses verify from .agy/config.toml
# max_fixups = 2
# max_diff_lines = 800
# timeout_min = 30
+++

## Goal
«What must work when this is done, and why, in 2–4 lines. Observable behaviour, not steps.»

## Context
«Where this lives in the code: files and functions agy must read first, and the existing pattern it must follow.»

## Approach
«Decisions already made: approach, names, signatures, conventions. Everything you do not want agy to decide.»

## Acceptance criteria
- «Verifiable condition 1 (ideally a specific test that must pass)»
- «Verifiable condition 2»

## Out of scope
- «What agy must NOT do even if it looks related»
