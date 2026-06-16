# AIMS diagnostics

Tooling and findings for the scoring-pipeline determinism investigation.

## Findings (read these)
- **`aims_nondeterminism_audit.md`** — every layer where randomness could enter, with verdicts.
  Root cause: `temperature=1.0` (live engine only). Fixed → temperature 0 + seed + deterministic
  tie-break + per-call logging + versioned cohort.
- **`aims_vs_v11_v12_v2_diff.md`** — why AIMS reports diverge from the validated ensemble: wave
  (W1 vs W2), percentile method (parametric vs within-sample t), and the live engine's condensed
  zero-shot prompt vs the V12 RAG prompt. (Coding science is *not* divergent — fixture = V12.)
- **`subject_723_three_way_comparison.md`** — Run A / Run B / patched / ensemble / human, side by side.

## Tools
- **`build_diagnostic_table.py`** — turns a scored run's per-call logs into the two CSVs
  (`*_raw_call_table_*` one row per story×motive×call; `*_per_story_aggregate_*` the 9-call pivot
  with consensus rate, std-dev, range).
- **`run_live_diagnostic.py`** — score one subject's 6 stories live and emit those CSVs. Spends
  DeepSeek credit. Example:
  ```
  python -m diagnostics.run_live_diagnostic P723 --label run_B_patched --temperature 0.0
  ```
- **`demo_synthetic.py`** — `*_DEMO.csv`: a SYNTHETIC (no-API) illustration so you can see the table
  shape and the consensus/std-dev columns populated without spending anything.

## How the table localises the bug
For each (story × motive), compare across the 9 calls:
- **High `CallToCallStdDev` / low `ConsensusRate`** → the **API layer** is unstable (temperature).
  This is what the original `temperature=1.0` runs show and what `temperature=0` should fix.
- Calls **agree** within a run but **two runs differ** → **aggregation** non-determinism
  (tie-breaks, ordering). Hardened via `_deterministic_mode` and submission-order gathering.
- Story scores **stable** but final **percentile** moves → **cohort/percentile layer**. The cohort
  is fixed + now version-stamped (`cohort_fingerprint()`), so this can't drift silently.
