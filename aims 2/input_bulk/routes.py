"""Operator HTTP surface: guided evaluation, settings, and bulk import.

All input paths converge on the same batch service -> scoring -> aggregation -> report pipeline.
"""
from __future__ import annotations

import html
import re
import uuid

from fastapi import APIRouter, BackgroundTasks, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

import config
from core import limits
from core.models import Story
from core.runtime import SETTINGS
from core.runtime import test_deepseek
from core.runtime import update as update_settings
from scoring_engine import estimate_cost

from .parsing import auto_map, parse_paste, parse_upload, to_stories
from .scoring_game import render_game
from .service import get_batch, new_batch, run_batch, summary_csv

router = APIRouter()


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "", name or "").upper()[:16]
    return s or "SUBJECT"


def _guard_live(request: Request, provider: str, n_stories: int, motives: int) -> str | None:
    """Hosted mode: rate-limit + spend-cap live runs on the central keys. Returns an error page or None."""
    if not config.HOSTED or (provider or SETTINGS.scoring_provider) != "deepseek":
        return None
    key = request.client.host if request.client else "anon"
    if not limits.rate_ok(key):
        return _page("Please wait", "<div class=card><h3>Hourly limit reached</h3><p class=muted>This "
                     "shared preview limits live evaluations per visitor. Try again later, or use the "
                     "Sample engine.</p><a class='btn ghost' href='/'>Back</a></div>")
    usd = estimate_cost(n_stories, "deepseek", motives).get("usd", 0.0)
    if not limits.charge(usd):
        return _page("Preview limit reached", "<div class=card><h3>Live scoring paused</h3><p class=muted>"
                     "This shared preview has reached its spending cap for live AI scoring. The Sample "
                     "engine still works.</p><a class='btn ghost' href='/'>Back</a></div>")
    return None


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{title} — AIMS</title>
<link rel=stylesheet href=/static/aims.css>
<style>body{{padding:32px;max-width:880px;margin:auto;background:var(--paper-warm)}}
.card{{background:#fff;border-radius:8px;padding:22px 26px;box-shadow:0 4px 18px rgba(0,0,0,.08);margin-bottom:18px}}
h1,h2,h3{{font-family:var(--font-display);color:var(--ink-charcoal)}} .mark{{font-family:var(--font-display);font-weight:800;color:var(--azure)}}
a.btn,button.btn{{display:inline-block;background:var(--maroon);color:#fff;border:none;text-decoration:none;padding:9px 16px;border-radius:5px;font-family:var(--font-display);font-weight:600;font-size:13px;cursor:pointer}}
button.btn.az,a.btn.az{{background:var(--azure-deep)}} button.btn.ghost{{background:#eee;color:var(--ink)}}
table{{width:100%;border-collapse:collapse;font-size:12px}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--rule)}}
th{{font-family:var(--font-display);font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-gray)}}
textarea,input,select{{font-family:var(--font-body);font-size:13px;border:1px solid var(--rule);border-radius:5px;padding:8px}}
.muted{{color:var(--ink-gray)}} .err{{color:var(--maroon-alt);font-size:12px}} .pill{{display:inline-block;background:var(--azure-tint);color:var(--azure-deep);border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600}}
.bar{{height:10px;background:var(--band-gray);border-radius:6px;overflow:hidden}} .bar>i{{display:block;height:100%;background:var(--azure)}}</style></head>
<body><p><a href="/" class=muted style="text-decoration:none">&larr; AIMS</a></p>{body}</body></html>"""


@router.get("/bulk", response_class=HTMLResponse)
def bulk_home() -> str:
    body = f"""<h1><span class=mark>Bulk input</span> — Feature B</h1>
<div class=card><h3>Upload a file</h3>
<p class=muted>CSV, XLSX, or JSONL. Columns <code>subject_id</code>, <code>picture</code>,
<code>story_text</code> — or a <code>StoryID</code> like <code>P010_PIC1</code> we derive both from.</p>
<form method=post action=/bulk/upload enctype=multipart/form-data>
<input type=file name=file accept=".csv,.tsv,.xlsx,.jsonl,.ndjson" required>
<button class=btn type=submit>Upload &amp; preview</button></form></div>

<div class=card><h3>Paste stories</h3>
<p class=muted>Group with <code># subject_id</code> headers (one story per line), or use
<code>subject | picture | story</code> per line.</p>
<form method=post action=/bulk/paste>
<textarea name=blocks rows=7 style=width:100%
placeholder="# P900&#10;A man stands at a drawing board, determined to perfect his design...&#10;Two friends reconnect after years apart...&#10;&#10;# P901&#10;P901 | 1 | The team rallies to beat their quarterly goal..."></textarea>
<div style=margin-top:10px><button class=btn type=submit>Add &amp; preview</button></div></form></div>

<div class=card><h3>Or try the demo</h3>
<p class=muted>Score the bundled W1 sample (63 subjects × 6 stories) through the full pipeline
using the <b>{config.SCORING_PROVIDER}</b> engine — produces a report for every subject.</p>
<form method=post action=/bulk/demo><label class=muted>Subjects:
<select name=limit><option value=5>first 5 (quick)</option><option value=15>first 15</option>
<option value=0>all 63</option></select></label>
<button class=btn az type=submit>Run demo batch</button></form></div>"""
    return _page("Bulk input", body)


@router.post("/bulk/upload")
async def bulk_upload(file: UploadFile) -> RedirectResponse:
    content = await file.read()
    rows, cols = parse_upload(file.filename or "upload.csv", content)
    mapping = auto_map(cols)
    stories, errors = to_stories(rows, mapping)
    st = new_batch(stories, errors, cols, mapping, rows[:5])
    return RedirectResponse(f"/bulk/{st.id}", status_code=303)


@router.post("/bulk/paste")
def bulk_paste(blocks: str = Form("")) -> RedirectResponse:
    stories, errors = parse_paste(blocks)
    st = new_batch(stories, errors, ["(pasted)"], {}, [])
    return RedirectResponse(f"/bulk/{st.id}", status_code=303)


@router.post("/bulk/demo")
def bulk_demo(limit: int = Form(5)) -> RedirectResponse:
    from scoring_engine.contract import load_fixture
    fx = load_fixture("achievement")
    subjects = sorted({s.subject_id for s in fx.values()})
    if limit:
        subjects = subjects[:limit]
    keep = set(subjects)
    stories = [Story.make(s.subject_id, s.picture, s.story_text, source="bulk")
               for s in sorted(fx.values(), key=lambda s: (s.subject_id, s.picture))
               if s.subject_id in keep and s.story_text]
    st = new_batch(stories, [], ["(demo: W1 sample)"], {}, [])
    return RedirectResponse(f"/bulk/{st.id}", status_code=303)


@router.post("/bulk/{bid}/run")
def bulk_run(bid: str, request: Request, background: BackgroundTasks):
    st = get_batch(bid)
    if st:
        blocked = _guard_live(request, st.provider, st.n_stories, len(st.motive_list))
        if blocked:
            return HTMLResponse(blocked)
    background.add_task(run_batch, bid)
    return RedirectResponse(f"/bulk/{bid}", status_code=303)


@router.get("/bulk/{bid}/progress")
def bulk_progress(bid: str) -> dict:
    st = get_batch(bid)
    if not st:
        return {"status": "missing"}
    return {"status": st.status, "progress": st.progress, "message": st.message}


@router.get("/bulk/{bid}/summary.csv")
def bulk_summary(bid: str):
    out = summary_csv(bid)
    if not out:
        return HTMLResponse("batch not found", status_code=404)
    return FileResponse(str(out), media_type="text/csv", filename=f"AIMS_batch_{bid}_summary.csv")


@router.get("/bulk/{bid}", response_class=HTMLResponse)
def bulk_detail(bid: str) -> str:
    st = get_batch(bid)
    if not st:
        return _page("Not found", "<div class=card>Batch not found.</div>")

    if st.status == "done":
        rows = ""
        for s in st.subjects:
            cells = "".join(
                f"<td>{('—' if s['motives'][m] is None else s['motives'][m])}"
                f"<span class=muted style='font-size:10px'> {html.escape(s['bands'][m] or '')}</span></td>"
                for m in config.ENABLED_MOTIVES)
            rows += (f"<tr><td><b>{html.escape(s['id'])}</b></td>{cells}"
                     f"<td><a href='/report/{html.escape(s['id'])}' target=_blank>report</a> · "
                     f"<a href='/report/{html.escape(s['id'])}.pdf'>pdf</a></td></tr>")
        mcols = "".join(f"<th>{m.title()}</th>" for m in config.ENABLED_MOTIVES)
        hero = ""
        if len(st.subjects) == 1:
            sid = st.subjects[0]["id"]
            hero = (f"<div class=card><h3 style='margin-top:0'>Report ready</h3>"
                    f"<a class=btn href='/report/{html.escape(sid)}' target=_blank>Open the report &rarr;</a> "
                    f"<a class=btn az href='/report/{html.escape(sid)}.pdf'>Download PDF</a></div>")
        body = f"""<h1>Result <span class=mark>{bid}</span></h1>
<div class=card><span class=pill>done</span> {html.escape(st.message)}
<p><a class=btn az href="/bulk/{bid}/summary.csv">Download combined scores CSV</a>
<a class=btn ghost href="/evaluate">New evaluation</a></p></div>
{hero}
<div class=card><h3>Subjects &amp; reports <span class=muted>(percentiles)</span></h3>
<table><thead><tr><th>Subject</th>{mcols}<th>Report</th></tr></thead><tbody>{rows}</tbody></table></div>"""
        return _page(f"Batch {bid}", body)

    if st.status == "scoring":
        return _page("Scoring…", render_game(bid, "live"))

    # ready: preview + mapping + cost, then run
    cost = st.cost()
    err = ""
    if st.errors:
        err = ("<div class=card><b class=err>" + str(len(st.errors)) + " row issue(s):</b><ul>"
               + "".join(f"<li class=err>{html.escape(e)}</li>" for e in st.errors[:12])
               + ("<li class=muted>…</li>" if len(st.errors) > 12 else "") + "</ul></div>")
    mapping_rows = "".join(
        f"<tr><td>{k}</td><td><code>{html.escape(str(v))}</code></td></tr>"
        for k, v in st.mapping.items() if v) if st.mapping else ""
    mapping_card = (f"<div class=card><h3>Detected column mapping</h3><table>{mapping_rows}</table>"
                    f"<p class=muted>StoryID is split into subject + picture automatically.</p></div>"
                    if mapping_rows else "")
    over = ("<p class=err>Estimated cost ${:.2f} exceeds the ${:.0f} cap — lower the batch or "
            "raise AIMS_COST_CAP_USD.</p>".format(cost.get("usd", 0), cost.get("cost_cap_usd", 0))
            if cost.get("over_cap") else "")
    run_btn = ("<button class=btn type=submit>Run scoring</button>" if not cost.get("over_cap")
               else "<button class=btn ghost disabled>Run scoring</button>")
    body = f"""<h1>Batch <span class=mark>{bid}</span> <span class=pill>ready</span></h1>
<div class=card><h3>Summary</h3>
<p><b>{st.n_stories}</b> stories · <b>{st.n_subjects}</b> subjects · engine
<b>{cost['provider']}</b> · est. cost <b>${cost.get('usd',0):.2f}</b>
<span class=muted>({html.escape(cost.get('note',''))})</span></p>{over}
<form method=post action="/bulk/{bid}/run">{run_btn}</form></div>
{mapping_card}{err}"""
    return _page(f"Batch {bid}", body)


# =================================================================== Guided evaluation
def _example_stories() -> list[str]:
    try:
        from scoring_engine.contract import load_fixture
        fx = load_fixture("achievement")
        rows = sorted((s for s in fx.values() if s.subject_id == "P020"), key=lambda s: s.picture)
        out = [s.story_text for s in rows][:6]
    except Exception:
        out = []
    while len(out) < 6:
        out.append("")
    return out


def _engine_banner() -> str:
    if config.HOSTED:
        return ("<span class=pill>Live AI scoring enabled</span> "
                f"<b>{SETTINGS.ensemble_n}</b> samples/story · powered centrally")
    if SETTINGS.has_live_key():
        return ("<span class=pill>Live engine ready</span> DeepSeek key "
                f"<b>{SETTINGS.key_hint()}</b> · model <b>{html.escape(SETTINGS.deepseek_model)}</b> · "
                f"<b>{SETTINGS.ensemble_n}</b> samples/story · <a href=/settings>change</a>")
    return ("<span class=pill style='background:var(--maroon-tint);color:var(--maroon-alt)'>"
            "No API key</span> Add your DeepSeek key in <a href=/settings>Settings</a> to score "
            "live — or use the Sample engine below.")


@router.get("/evaluate", response_class=HTMLResponse)
def evaluate_form() -> str:
    ex = _example_stories()
    boxes = "".join(
        f"<label class=muted>Picture {i + 1}</label>"
        f"<textarea name=story{i + 1} rows=3 style=width:100%>{html.escape(ex[i])}</textarea>"
        for i in range(6))
    live = SETTINGS.has_live_key()
    live_lbl = "Live — AI scoring" if config.HOSTED else "Live — DeepSeek (your API key)"
    live_opt = (f"<option value=deepseek {'selected' if live else 'disabled'}>"
                f"{live_lbl}{'' if live else ' — add key in Settings'}</option>")
    samp_opt = f"<option value=fixture {'selected' if not live else ''}>Sample engine (instant, no key)</option>"
    body = f"""<h1><span class=mark>New evaluation</span></h1>
<div class=card>{_engine_banner()}</div>
<form method=post action=/evaluate>
<div class=card><h3>Who is this?</h3>
<label class=muted>Name (or candidate ID)</label>
<input name=name style=width:60% placeholder="e.g. Jane Candidate" value="">
</div>
<div class=card><h3>Their stories</h3>
<p class=muted>Paste the person's Picture-Story responses — ideally 6, one per picture. The boxes
are pre-filled with an example so you can try it immediately; replace them with real stories.</p>
{boxes}</div>
<div class=card><h3>Run</h3>
<p><label class=muted>Engine</label><br><select name=engine>{live_opt}{samp_opt}</select>
&nbsp;&nbsp;<label class=muted>Motives</label><br>
<select name=scope><option value=all>All three motives</option>
<option value=achievement>Achievement only (fastest / cheapest)</option></select></p>
<p class=muted>Live scoring makes ~{SETTINGS.ensemble_n} API calls per story per motive and can take
a minute or two — so there's a game to play while the model works
(<a href=/play target=_blank>preview it</a>). You'll see live progress, then the report.</p>
<button class=btn type=submit>Score &amp; build report</button></div>
</form>"""
    return _page("New evaluation", body)


@router.post("/evaluate")
def evaluate_run(request: Request, background: BackgroundTasks, name: str = Form(""),
                 engine: str = Form("fixture"), scope: str = Form("all"), story1: str = Form(""),
                 story2: str = Form(""), story3: str = Form(""), story4: str = Form(""),
                 story5: str = Form(""), story6: str = Form("")):
    if engine == "deepseek" and not SETTINGS.has_live_key():
        return RedirectResponse("/settings?need_key=1", status_code=303)
    subject_id = f"{_slug(name)}_{uuid.uuid4().hex[:4]}"
    texts = [story1, story2, story3, story4, story5, story6]
    stories = [Story.make(subject_id, i, t, source="live")
               for i, t in enumerate(texts, 1) if t and t.strip()]
    if not stories:
        return RedirectResponse("/evaluate", status_code=303)
    motives_n = 1 if scope == "achievement" else len(config.ENABLED_MOTIVES)
    blocked = _guard_live(request, engine, len(stories), motives_n)
    if blocked:
        return HTMLResponse(blocked)
    st = new_batch(stories, [], ["(evaluation)"], {}, [])
    st.provider = engine
    st.motives = ["achievement"] if scope == "achievement" else None
    st.subject_name = name.strip() or subject_id
    background.add_task(run_batch, st.id)
    return RedirectResponse(f"/bulk/{st.id}", status_code=303)


@router.get("/play", response_class=HTMLResponse)
def play_game() -> str:
    """Preview the 'Pursuit of Scoring' waiting game without scoring anything (demo mode)."""
    return _page("Pursuit of Scoring", render_game("demo", "demo"))


# =================================================================== Settings
def _settings_page(msg: str = "", ok: bool | None = None, need_key: bool = False) -> str:
    note = ""
    if need_key:
        note = ("<div class=card><b class=err>Add your DeepSeek API key to score live.</b> "
                "It's stored locally on this machine only.</div>")
    if msg:
        color = "var(--azure-deep)" if ok else "var(--maroon-alt)"
        note += f"<div class=card><b style='color:{color}'>{html.escape(msg)}</b></div>"
    opts_n = "".join(f"<option value={n} {'selected' if SETTINGS.ensemble_n == n else ''}>"
                     f"{n} samples{' (fast/cheap)' if n == 3 else ' (most accurate)' if n == 9 else ''}"
                     f"</option>" for n in (3, 6, 9))
    eng = lambda v: "selected" if SETTINGS.scoring_provider == v else ""
    mode = lambda v: "selected" if SETTINGS.prompt_mode == v else ""
    body = f"""<h1><span class=mark>Settings</span></h1>{note}
<form method=post action=/settings>
<div class=card><h3>DeepSeek (live scoring)</h3>
<p class=muted>Get a key at <b>platform.deepseek.com</b>. Status: <b>{SETTINGS.key_hint()}</b>.
Stored locally in <code>data/settings.json</code> (gitignored), read before any environment variable.</p>
<label class=muted>API key</label><br>
<input type=password name=deepseek_api_key style=width:70% placeholder="paste to set or change — leave blank to keep current"><br><br>
<label class=muted>Model</label> <input name=deepseek_model value="{html.escape(SETTINGS.deepseek_model)}" style=width:30%>
&nbsp;&nbsp;<label class=muted>Samples per story</label> <select name=ensemble_n>{opts_n}</select>
</div>
<div class=card><h3>OpenAI (RAG calibration — optional)</h3>
<p class=muted>Needed only to run the validated engine <b>with</b> RAG exemplars
(<code>text-embedding-3-large</code>). Status: <b>{SETTINGS.openai_hint()}</b>.
Stored locally in <code>data/settings.json</code> (gitignored). Paste it here — not into chat.</p>
<label class=muted>API key</label><br>
<input type=password name=openai_api_key style=width:70% placeholder="paste to enable RAG — leave blank to keep current"></div>
<div class=card><h3>Scoring rubric</h3>
<select name=prompt_mode>
<option value=v12 {mode('v12')}>Full V12 / V11 / V2 — verbatim notebook prompts</option>
<option value=condensed {mode('condensed')}>Condensed — generated short rubric</option></select>
<p class=muted>“Full” sends your exact notebook prompts (and uses RAG exemplars when an OpenAI key is set).</p></div>
<div class=card><h3>Default engine</h3>
<select name=scoring_provider>
<option value=deepseek {eng('deepseek')}>Live — DeepSeek</option>
<option value=fixture {eng('fixture')}>Sample (replay bundled data)</option></select>
<p class=muted>Used when an evaluation doesn't pick one explicitly.</p></div>
<button class=btn type=submit>Save settings</button>
<button class=btn az type=submit formaction=/settings/test>Test DeepSeek connection</button>
</form>"""
    return _page("Settings", body)


@router.get("/settings", response_class=HTMLResponse)
def settings_form(saved: int = 0, need_key: int = 0):
    if config.HOSTED:                       # no key management on the public build
        return RedirectResponse("/", status_code=303)
    msg = "Settings saved." if saved else ""
    return _settings_page(msg=msg, ok=True if saved else None, need_key=bool(need_key))


@router.post("/settings")
def settings_save(deepseek_api_key: str = Form(""), deepseek_model: str = Form(""),
                  ensemble_n: int = Form(9), scoring_provider: str = Form(""),
                  openai_api_key: str = Form(""), prompt_mode: str = Form("")) -> RedirectResponse:
    if config.HOSTED:
        return RedirectResponse("/", status_code=303)
    fields = {"deepseek_model": deepseek_model or None, "ensemble_n": ensemble_n,
              "scoring_provider": scoring_provider or None, "prompt_mode": prompt_mode or None}
    if deepseek_api_key.strip():           # blank = keep current key
        fields["deepseek_api_key"] = deepseek_api_key.strip()
    if openai_api_key.strip():
        fields["openai_api_key"] = openai_api_key.strip()
    update_settings(**fields)
    return RedirectResponse("/settings?saved=1", status_code=303)


@router.post("/settings/test", response_class=HTMLResponse)
def settings_test(deepseek_api_key: str = Form(""), deepseek_model: str = Form(""),
                  ensemble_n: int = Form(9), scoring_provider: str = Form(""),
                  openai_api_key: str = Form(""), prompt_mode: str = Form("")):
    if config.HOSTED:
        return RedirectResponse("/", status_code=303)
    # persist any just-entered values first so nothing typed is lost when testing
    fields = {"deepseek_model": deepseek_model or None, "prompt_mode": prompt_mode or None}
    if deepseek_api_key.strip():
        fields["deepseek_api_key"] = deepseek_api_key.strip()
    if openai_api_key.strip():
        fields["openai_api_key"] = openai_api_key.strip()
    update_settings(**fields)
    ok, message = test_deepseek()
    return _settings_page(msg=message, ok=ok)
