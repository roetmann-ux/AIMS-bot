# AIMS — AI-Powered Implicit Motive System (prototype)

Measures a person's **implicit motives** — Achievement, Affiliation, Influence (McClelland's
Power, relabeled) — from short Picture Story Exercise (PSE/TAT) stories, and renders a
professional report. End users see **percentiles, plain-language narrative, and role-relevant
implications — never raw category scores.** That translation layer is the product.

## One pipeline, two front doors
```
[A] Live PSE  ─┐
               ├─►  Story[] ─► ScoringEngine ─► ScoredStory[] ─► Aggregator ─► SubjectProfile ─► Report (HTML/PDF)
[B] Bulk import ┘        (per story, per motive)        (group by subject, %ile)
```
Both inputs converge on identical `Story` records → identical pipeline → identical reports.

| Module | Role |
|---|---|
| `core/` | data models (`Story`, `ScoredStory`, `SubjectProfile`), the **data-driven motive registry** (`motives.py`), SQLite storage |
| `scoring_engine/` | **contract boundary.** `score_story` / `score_batch`; providers: `fixture` (replays the founder's CSVs) + `deepseek` (live ensemble); per-motive prompts; optional RAG |
| `aggregate/` | raw → word-count-corrected → within-sample T / percentile + 5 bands; expression rollup |
| `report/` | AIMS-style HTML report (all 3 motives), rules-based narrative, PDF export, the `PAT` deck reproduction |
| `input_bulk/` | Feature B: file upload (CSV/XLSX/JSONL) + paste, column mapping, batch scoring, downloads |
| `input_live/` | Feature A: live PSE administration (scaffolded for next milestone) |
| `app.py` | FastAPI wiring (operator + report surfaces) |

## Run
```bash
cd aims
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8765      # open http://localhost:8765
pytest -q                                  # tests
```
- **Sample report (matches the deck 1:1):** `/report/PAT?sample=1`
- **Real data example:** `/report/P617`
- **Bulk (try the demo):** `/bulk` → "Run demo batch"
- PDF export uses headless Chromium: `python -m playwright install chromium` (otherwise use the
  browser's Print → Save as PDF; the report has print CSS).

## Scoring providers
- `AIMS_SCORING_PROVIDER=fixture` (default) — replays `data/fixtures/output_*_deepseek9.csv`,
  zero cost, reproduces the engine contract exactly. Powers the demo and all three motives.
- `AIMS_SCORING_PROVIDER=deepseek` — live DeepSeek ensemble (set `DEEPSEEK_API_KEY`). N=9 calls
  per story, gate majority-voted @0.5, subcategories soft-gated, optional Stage-B arbiter, cost
  cap enforced. Runs zero-shot unless RAG assets + `OPENAI_API_KEY` are present.

All tunables live in `config.py` / `.env` (see `.env.example`): enabled motives, word-count
correction, `MIN_WORDS`, per-picture timer, cost cap, model + prompt version pins.

## Notes that shaped the build (see `docs/INTEGRATION_CONTRACT.md`)
- The notebooks compute **no word-count correction and no percentile** — participant scores are
  raw sums; human T-scores in the master file are external. AIMS adds the standard
  length-correction + within-sample T/percentile as **new, clearly-labelled** functionality
  (config-toggleable; default on). Percentiles are **sample-relative** until an external norm
  table is supplied.
- The "ensemble" is DeepSeek sampled 9×; notebook model ids are forward-dated/fictional and are
  remapped via `config.DEEPSEEK_MODEL`.
- Motive schema is **data-driven** (Achievement 13 cats / Affiliation 7 / Power 12, different
  gates and thresholds) so engines light up by config, not code changes.

## Status
**Done:** core + scoring engine (fixture + live) + aggregation + report (all 3 motives, PDF) +
Bulk input + operator subjects/data-deletion. **Next:** live PSE flow (Feature A), operator
auth + consent capture, external norms, RAG retrieval, native .pptx export.
