# AIMS — Scoring Engine Integration Contract

This file records exactly how the existing Colab scoring engine behaves, extracted from the
founder's notebooks, so the wrapped `scoring_engine/` reproduces it. **The notebooks are ground
truth.** Source notebooks (in the parent Downloads folder):
`Achievement_Inference_V12_W1W2.ipynb`, `Affiliation_Inference_V2_W1W2.ipynb`,
`Power_Inference_V11_W1W2.ipynb`.

## 1. The "ensemble"
- It is **N independent API calls**, each `n=1`, dispatched concurrently, then **averaged and
  thresholded at 0.5** — not one multi-sample call.
- `output_*_deepseek9.csv` = **DeepSeek sampled 9×** (`USE_DEEPSEEK_ONLY=True`). Full mode =
  4 providers × 3 calls = 12. The gate vote string `Provider Votes <gate>` looks like
  `deepseek=0/9` (Achievement gate=AI) / `...=k/9` for Affiliation (`AffIm`) and Power (`PowIm`).
- **Model ids in the notebooks are forward-dated/fictional** (`deepseek-v4-pro`,
  `claude-opus-4-7`, `gpt-5.4-mini`, `gemini-3.1-pro-preview`). The live provider remaps to real
  ids via `config.py` (`DEEPSEEK_MODEL`, default `deepseek-chat`).

## 2. Per-motive category schema (data-driven — see `core/motives.py`)
Story `Total = sum(all grading categories except TI and UI)`; the **gate** counts toward Total.

| Motive | Gate | Grading categories (column order) | Subcats scored only if gate fired |
|---|---|---|---|
| Achievement | `AI` | AI, TI, UI, Need, Act, GA+, GA-, BP, BW, Help, F+, F-, TH | Need, Act, GA+, GA-, BP, BW, Help, F+, F-, TH |
| Affiliation | `AffIm` | AffIm, N, Act, SA, Bw, F+, TH | N, Act, SA, Bw, F+, TH |
| Power/Influence | `PowIm` | PowIm, Pa+, Pa-, N, Act, Bw, SA, Fa, F+, F-, Eff, HopeFear | Pa+, Pa-, N, Act, Bw, SA, Fa, F+, F-, Eff |

Notes:
- **`TI` is a permanent 0** placeholder column in Achievement (kept for backward column-compat).
- **`Act` is a string enum** (`Act+`/`Act-`/`Act?`/null), counted as present(1)/absent(0) toward Total.
- Per-category soft-gate thresholds vary: Achievement `TH=0.7`, others `0.5`; Power
  `N/Act/SA/Eff=0.6`; Affiliation `SA=0.6`. Encoded per motive.
- `<CAT> Majority` duplicates `<CAT>` (legacy). `<CAT> Confidence` is the raw mean over gated
  responses (0.0 if gate=0).

## 3. Output column families (per story; reproduced by `scoring_engine/contract.py`)
`StoryID` then, for each grading cat: `ensemble <CAT>`, plus blocks
`ensemble Total`, `Expected Total`, `<CAT> Correct`, `Expected <CAT>`, `<CAT> Confidence`,
`<CAT> Explanation`, `<CAT> Majority`, `<CAT> Majority Explanation`, `<CAT> Dissenting
Explanation`, then `Provider Votes <gate>`, `Stage B Trigger`, `Stage B Override`, `Story`.
(Achievement=111 cols, Affiliation=63, Power=98.)

## 4. Two-stage logic
- **Stage A**: ensemble scoring; gate averaged@0.5; subcats soft-gated (averaged over only the
  responses whose own gate fired), equal weight per response.
- **Stage B**: a single **DeepSeek arbiter** re-decides only the gate for flagged stories.
  `Stage B Trigger` = reason label or `none`; `Stage B Override` = `yes`/`no`.
  Trigger differs per motive: Achievement & Power fire on the **first** of
  {borderline_confidence 0.30–0.70, provider_dissent, gate0_nonzero_dissent, hollow_gate1};
  **Affiliation requires ≥2** conditions and emits a `+`-joined label.

## 5. StoryID
`{subject_id}_PIC{n}` e.g. `P010_PIC1`. Notebooks parse only `PIC(\d+)`; subject is recovered
downstream. AIMS parses both (`core/ids.py`).

## 6. Aggregation / standardization — NOT in the notebooks (new in AIMS)
- The notebooks compute **one raw value per story** (`ensemble Total`). The founder's
  participant score = **plain sum of `ensemble Total` across the 6 stories** (no correction,
  no standardization). Human T-scores in the master file (`tach88`, `npow88`, `naff88`) are
  **external** (McClelland & Franz 1987–88), not produced here. Validity was assessed by
  correlating the **raw** AI sum against those (Achievement r≈.65).
- Therefore **word-count correction and percentile/T-scoring are new AIMS functionality**, not a
  port. `aggregate/` implements the standard length-correction (regress motive total on protocol
  word count, take residuals) and a within-sample T (50+10·z) / percentile (Φ(z)). Both corrected
  and uncorrected are stored; correction is config-toggled (`WORD_COUNT_CORRECTION`), default on.
  Percentiles are **sample-relative** and labeled as such until a real norm table is supplied.

## 7. Live scoring depends on RAG (optional in AIMS)
The notebooks build the user message via `rag_retriever.py` + a parquet/npy exemplar library +
OpenAI `text-embedding-3-large`. AIMS vendors a light retriever; if the library + `OPENAI_API_KEY`
are present it uses RAG, else the live provider runs **zero-shot** (rubric + story only). The
fixtures path (replaying the CSVs) needs no keys and reproduces the contract exactly.
