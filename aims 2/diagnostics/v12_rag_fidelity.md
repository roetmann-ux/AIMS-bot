# V12 + RAG fidelity check — P723 (live, temperature 0)

The live engine now runs the **verbatim V12/V11/V2 prompts** with **RAG** (Achievement + Power);
Affiliation has no exemplar library so it runs the V12 prompt zero-shot. Raw tables:
`diagnostics/aims_raw_call_table_run_v12_rag.csv` (+ per-story aggregate).

## 1. Provenance — proven, not asserted
| Motive | Provenance stamp | = hash of the verbatim prompt? |
|---|---|---|
| Achievement | `V12-rag:7edf542e7c44` | ✓ |
| Power/Influence | `V12-rag:a97c8a0decb1` | ✓ |
| Affiliation | `V12-zeroshot:f72db06d8c68` | ✓ (no RAG library) |
The stamp is a SHA-256 of the exact system prompt sent. It matches the hash of the extracted
notebook prompt → the engine demonstrably sends your validated rubric, plus retrieved exemplars.

## 2. Determinism with RAG (temperature 0)
Mean 9-call `ConsensusRate`: Influence **1.000**, Achievement **0.987**, Affiliation **0.987**.
Calls agree near-perfectly; residual <2% is expected LLM non-determinism at T=0 (documented).

## 3. Fidelity to the stored V12/V11/V2 codings (same W1 stories)
| Motive | Live V12+RAG (per story) | Stored V12 (per story) | Subject %ile | Verdict |
|---|---|---|---|---|
| Achievement | raw 4 `[0,3,0,1,0]` | raw 4 `[0,4,0,0,0]` | **42 = 42** | subject-level **exact**; per-story distribution differs |
| Power/Influence | raw 0 `[0,0,0,0,0]` | raw 0 `[0,0,0,0,0]` | **21 = 21** | **exact** |
| Affiliation (zero-shot) | raw 8 | raw 10 | 59 vs 70 | **close** — limited by missing RAG library |

The faithful engine **reproduces the V12/V11/V2 subject-level scores** on the same wave (Achievement
total 4 → 42, Power exact). Per-story Achievement isn't byte-identical because the *stored* output
was generated with the notebook's original Drive embeddings + sampling temperature; this run uses
temperature 0 + freshly rebuilt embeddings. Affiliation is closest-possible without its library.

## 4. Still ≠ the W2 ground truth (Ach 98/92, Pow 0, Aff 49) — and why
Unchanged from `aims_vs_v11_v12_v2_diff.md`: these are P723's **W1** stories (W1 Achievement is
genuinely low, raw 4); the 92/98 target is **W2**. The engine is faithful; the *wave* differs.
Influence/Affiliation are already in range. Percentile method (parametric Φ(z) vs within-sample t)
explains the Influence 21-vs-0.

## What this does and doesn't prove
- **Proves:** the engine genuinely runs your V12/V11/V2 prompts + RAG (hash-verified), is
  deterministic at T=0, and reproduces your stored V12 subject-level codings on matched stories.
- **Doesn't prove (yet):** population validity. One subject ≠ certification. The real test is
  **Tier 3** — re-score the n=46 human-coded set and confirm it recovers the expert correlations
  (r≈.65 Ach, etc.). That + building the Affiliation RAG library + a W2 option are the remaining work.
