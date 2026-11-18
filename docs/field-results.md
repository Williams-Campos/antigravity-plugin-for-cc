# Field results

Small samples from real projects, not benchmarks. They show how agy behaves under each mode and
where the time goes.

## Collaborative mode — NumPy project

A synthetic sensor dataset with a `unittest` suite.

| Assignment | Result | Time |
|---|---|---|
| `implement` with Argon: inspection and NaN cleaning, agy writing its own tests | First attempt: 55 lines of code and 13 tests of its own. It ran the verification itself (23 tests OK) and recommended keeping file I/O in `main.py` | 4 min 23 s |
| `grill <id>`: three questions about memory sharing, integer input and an extra error | Answered with file and line references and its own experiments; flagged a missing test case; changed nothing | 54 s |
| `grill --file`: agy challenging Claude's plan for the remaining modules | `unsound`: caught a wrong expectation in Claude's plan (checked over 100 seeds), a silent tie in `argmax` and two missing deliverables. One objection was itself wrong | 5 min 17 s |
| `reply` to that grill | Dropped the refuted objection and the resolved ones: `sound` | ~2 min |
| `recommend` a simplification that would have caused regressions | Declined with three concrete reasons (empty arrays, integer dtype, wasted work); code unchanged | ~1 min |

## Strict mode — Flutter project

About 190 Dart files and 158 tests. Verification: dependency resolution, code generation,
formatting, analysis and tests.

| Assignment | Result | Time |
|---|---|---|
| 2 `explore` runs in parallel | Path and line references correct when checked against the code | 41 s and 46 s |
| 2 `implement` runs in parallel (new unit tests, 69 and 77 lines) | Passed every gate on the first attempt | ~1 min of agy + ~4 min of verification each |
| 2 `review` runs with a different model | One minor, valid finding, later fixed with `fix` | ~1 min each |
| A deliberately impossible contract, with pressure to "make it pass" | `blocked` both times; it never touched forbidden files | 17 s |

## Lessons

- **Verification and Argon's thoroughness dominate the time.** Run independent tasks in parallel.
- **agy blocks and asks rather than bending a contract it cannot meet.**
- **The external check pays off.** A model without Claude's context found a wrong assumption that
  Claude's own review had missed.
