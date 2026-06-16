# AIMS vs. validated V11/V12/V2 ensemble (Phase 4)

**Key fact:** AIMS's default `fixture` engine *is* the V11/V12/V2 output — it replays
`output_Achievement_V12_W1_deepseek9.csv`, `output_Power_V11_W1_deepseek9.csv`,
`output_Affiliation_V2_W1.csv` verbatim. `test_aims_reproduces_v12_ensemble_codings_on_p723`
confirms the codings are identical with **no transformation**. So at the **coding** level there is
no divergence. The divergence the reports show comes from three layers *downstream of* (or *instead
of*) those codings:

## 1. Live engine ≠ the validated ensemble (prompt + RAG)
When you score through the **live DeepSeek engine** (not fixtures), AIMS does **not** use the V12
pipeline:

| | Validated V11/V12/V2 | AIMS live engine |
|---|---|---|
| Prompt | ~300-line tuned rubric per motive | **condensed, data-driven rubric** generated from `core/motives.py` (`scoring_engine/prompts.py`) |
| Few-shot | **RAG** exemplars (`rag_retriever.py` + parquet library + `text-embedding-3-large`) | **zero-shot** (RAG stubbed → `""`, `scoring_engine/rag.py`) |
| Sampling | 9 samples | 9 samples, but was `temperature=1.0` (now 0) |

→ Even after the determinism fix, **live AIMS codings will differ from V12** because the prompt is
shorter and there are no calibration exemplars. To converge, the live engine must use the **ported
V12 prompt + RAG retriever**. This is the documented prototype simplification, not a plumbing bug.
**Use the `fixture` engine to reproduce V12 exactly; use `deepseek` only for genuinely new stories.**

## 2. Wave mismatch (the biggest number gap)
The human/ensemble targets you cite (**Ach=92, Pow=0, Aff=49**) are **W2**. AIMS norms and scores
Achievement against **W1** (`config.NORM_FIXTURES["achievement"] = …_V12_W1_…`). P723's W1 stories
score raw Achievement = **4** (low); the "92" is W2. These are *different stories*. Comparing
AIMS-W1 to ensemble-W2 is apples-to-oranges. Fix to compare like-for-like: point the achievement
fixture/norm at the **W2** file (or add a wave selector).

## 3. Percentile method (cohort + standardisation)
Same raw score maps to different percentiles:

| | Human / V11-V12-V2 | AIMS |
|---|---|---|
| Standardisation | within-sample **t** (n=46), effectively empirical rank | **parametric** `Φ(z)` on length-**corrected** score |
| Length correction | (per published method) | regression-residual on word count (`config.WORD_COUNT_CORRECTION`) |
| Cohort | n=46 dissertation analytic sample | the 46-subject fixture (same sample here) but different formula |

Concrete effect on P723 Influence: raw = **0**. AIMS parametric `Φ(z)` ⇒ **21st pct**; the human
"0th" is an empirical floor (many subjects tie at 0). The 21-vs-0 gap is the parametric-vs-empirical
difference plus tie-handling. Aligning requires switching the percentile to empirical within-sample
rank (and the same wave as §2).

## Bottom line
- **Coding science is not divergent** — AIMS-fixture = V12 exactly.
- The report-level divergence is: (1) live engine uses a condensed zero-shot prompt, (2) **W1 vs
  W2**, (3) parametric `Φ(z)`+length-correction vs within-sample-t. None is a "scoring bug"; (1)–(3)
  are normalisation/engine choices. Closing them to within 10 percentile points is a scoped change
  (same wave + empirical percentile + ported V12 prompt/RAG), not a determinism fix.
