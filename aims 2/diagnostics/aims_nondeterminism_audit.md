# AIMS Non-determinism Audit (Phase 3)

**Headline:** there is exactly one source of run-to-run non-determinism, and it is in the **live
DeepSeek engine only**. The default `fixture` engine (CSV replay) and the entire aggregation +
percentile stack are deterministic — proven by `test_fixture_pipeline_is_deterministic` (P723
gives identical output across reruns).

| # | Layer | Current behaviour (file:line) | Source of non-determinism? | Fix |
|---|---|---|---|---|
| 1 | **LLM sampling** | `temperature=1.0`, no `seed`, in the 9 calls — `scoring_engine/providers/deepseek.py:79` (pre-fix) | **YES — root cause.** 9 samples at T=1.0 disagree; on borderline stories the 0.5-thresholded gate flips between runs → story Total flips → subject total & percentile swing (your 37↔95). | **temperature → 0.0** (`config.DEEPSEEK_TEMPERATURE`), `top_p=1.0`, best-effort `seed` (`config.DEEPSEEK_SEED`). |
| 2 | **Prompt construction** | `build_system_prompt` / `build_user_prompt` are pure functions of the motive spec + story text; RAG returns `""` deterministically (`scoring_engine/rag.py`) | **No** (currently zero-shot & deterministic). | Guard for later: when RAG is enabled, top-k retrieval must be stable for identical query embeddings. |
| 3 | **Concurrency / batching** | 9 calls dispatched via `ThreadPoolExecutor`; results gathered as `[f.result() for f in futures]` (`deepseek.py` `score_story`) | **No.** That comprehension preserves **submission** order, not arrival order, so aggregation sees a stable ordering. | None needed; documented. |
| 4 | **Majority-vote aggregation** | Gate = `mean(votes) ≥ 0.5`; subcats = `mean ≥ threshold` (deterministic). `Act` mode used `Counter.most_common` (insertion-order tie-break) | **Maybe** (the Act tie-break depended on response order). | Replaced with `_deterministic_mode` — ties broken **lexicographically**, order-independent. |
| 5 | **Reference cohort / percentile** | `aggregate/norms.get_norms` builds from a **fixed fixture file**, `lru_cache`d; never recomputed from the live DB or "today's reports" | **No.** Cohort is stable; same raw → same percentile. | Added a **version hash** (`NormTable.version`, `cohort_fingerprint()`) stamped into every report so any future percentile move is traceable to a cohort change. |
| 6 | **Narrative band thresholds** | `config.BANDS` are fixed constants (0/10/30/70/90) | **No.** | None. |
| 7 | **Caching** | No LLM-response cache anywhere | **No** — and this answers "why did Run A and Run B differ?": there is no cache, so each run re-samples the API at T=1.0. The divergence is genuine sampling variance, not a cache-key bug. | None. |

## Root cause (one line)
`temperature=1.0` with no seed in the live ensemble: on borderline stories the 9-sample majority
vote flips between runs, propagating to subject totals and percentiles.

## Fixes applied (this session)
- `temperature=0.0` default + best-effort `seed` + `top_p=1.0` (`config.py`, `deepseek.py`).
- Deterministic `Act` tie-break (`_deterministic_mode`).
- **Per-call raw logging** (`ScoredStory.call_logs`) — verbatim response + hash + timestamp + params
  for all 9 calls, so the diagnostic table can separate API-layer from aggregation-layer variance.
  Failed calls are recorded, never defaulted to a score.
- **Versioned cohort** stamped into report metadata.

## Residual non-determinism (honest caveat)
Even at `temperature=0`, LLMs are not byte-deterministic (floating-point, MoE routing), and DeepSeek's
OpenAI-compatible endpoint may ignore `seed`. Expect the 9 calls to **agree** at T=0 (so story
scores are stable across reruns) but not be provably identical. The magnitude of any residual is
measured on the live 9-call table (`ConsensusRate`, `CallToCallStdDev`) via
`diagnostics/run_live_diagnostic.py`, not asserted in a unit test.
