+++
id = "E-001"
title = "Public functions of textutil and their test coverage"
role = "explore"
allowed = ["src/**", "tests/**"]
search = ["textutil"]
+++

## Goal
Which public functions does `src/textutil.py` expose, and which of them have tests? I need this to decide what is missing coverage before extending the module.

## What to report
- Each public function with its location and signature.
- Which test file covers it and what behaviour it checks, if any.
- Which behaviour has no test at all.
