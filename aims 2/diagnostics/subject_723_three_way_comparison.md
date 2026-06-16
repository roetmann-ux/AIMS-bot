# Subject 723 — comparison (Phase 6)

P723 has **5** transcribed W1 stories (PIC 1,3,4,5,6). All runs below are real (live DeepSeek,
n=9, key from Settings). Raw tables: `aims_raw_call_table_run_{A_repro,B_patched,C_patched}.csv`.

| Source | Achievement | Power / Influence | Affiliation | Deterministic? |
|---|---|---|---|---|
| **Your Run A** — original (live, T=1.0) | 37 (moderate) | 65 | 93 | no |
| **Your Run B** — original (live, T=1.0) | 95 (sig high) | 18 | 93 | no |
| **My Run A repro** (live, **T=1.0**) | **93** (sig high) | 58 | 76 | no |
| **My Run B patched** (live, **T=0**) | **53** (moderate) | 21 | 95 | — |
| **My Run C patched** (live, **T=0**) | **53** (moderate) | 21 | 95 | **= Run B (identical)** |
| AIMS `fixture` (V12 codings, **W1**) | 42 | 21 | 70 | yes |
| V11/V12/V2 ensemble (**W2**) | 92 | 0 | 49 | — |
| Human ground truth (**W2** within-sample t) | 98 | 0 | 49 | — |

## Determinism — FIXED and verified live
| | mean ConsensusRate | mean CallToCallStdDev | run-to-run |
|---|---|---|---|
| **T = 1.0** (Run A repro) | 0.985 | 0.149 (per-story range up to **2**) | unstable |
| **T = 0** (Runs B, C) | **1.000** | **0.000** | **Run B ≡ Run C (byte-identical scores)** |

At T=0 every one of the 9 calls agrees on every story, and two independent runs produce identical
per-story totals and percentiles. The 37↔95 swing is reproduced at T=1.0 and **eliminated** at T=0.
Mechanism: story **PIC4** is borderline — its Achievement gate fires in some T=1.0 draws (this repro:
PIC4=6) and not others (T=0: PIC4=0); a single flipped story moves the subject total and percentile.

## Convergence to 92 / 0 / 49 — NOT achieved by the determinism fix (honest)
The patched-stable live result (**53 / 21 / 95**) and the V12-faithful `fixture` result (**42 / 21 /
70**) both differ from the W2 ensemble/human target. This is **expected and structural**, not a
determinism issue (see `aims_vs_v11_v12_v2_diff.md`):
1. **Wave** — target is **W2**; AIMS scores/norms **W1** (different stories). Biggest factor.
2. **Percentile method** — AIMS parametric `Φ(z)`+length-correction vs within-sample **t**/empirical
   rank (e.g. Influence raw 0 → AIMS 21 vs empirical 0).
3. **Live engine only** — condensed **zero-shot** prompt vs the **V12 RAG** prompt (this is why live
   53/95/21 ≠ fixture 42/70/21; affiliation in particular is over-detected zero-shot).

To land within 10 points of 92/0/49 (scoped follow-up, not plumbing): point norms/scoring at **W2**,
switch percentile to **empirical within-sample rank**, and for the live engine **port the V12 prompt
+ RAG**. Until then, use the **`fixture` engine** for V12-faithful codings and treat the live engine
as reproducible-but-not-yet-calibrated.

## Reproduce
```
python -m diagnostics.run_live_diagnostic P723 --label run_B_patched --temperature 0.0
python -m diagnostics.run_live_diagnostic P723 --label run_C_patched --temperature 0.0
# -> aims_per_story_aggregate_run_B_patched.csv ≡ _run_C_patched.csv on all score columns
```
