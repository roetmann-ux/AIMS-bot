"""AIMS web app (FastAPI). One pipeline, candidate-facing + operator-facing surfaces.

This module wires the shared core to HTTP. Bulk input (Feature B) lives in input_bulk/ and is
mounted below; the live PSE flow (Feature A) is stubbed for the next milestone.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import config
from aggregate import aggregate_db_subject, aggregate_fixture_subject
from core.db import delete_subject, init_db, subject_ids_with_scores
from core.models import SubjectProfile
from core.runtime import SETTINGS
from report.renderer import render_report

app = FastAPI(title="AIMS — AI-Powered Implicit Motive System")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "report" / "static")), name="static")

from input_bulk.routes import router as bulk_router  # noqa: E402
from input_live.routes import router as live_router  # noqa: E402
app.include_router(bulk_router)
app.include_router(live_router)

HERO_DEMO = "P617"   # rich, varied fixture profile used for the showcase

# ---------------------------------------------------------------- hosted/public gate
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402


@app.middleware("http")
async def _gate(request: Request, call_next):
    """When hosted behind a passphrase, redirect un-authenticated visitors to /unlock."""
    if config.HOSTED and config.ACCESS_PASSPHRASE:
        p = request.url.path
        if not (p in ("/unlock", "/healthz") or p.startswith("/static")) and not request.session.get("ok"):
            return RedirectResponse("/unlock", status_code=303)
    return await call_next(request)


# Outermost so request.session is available inside the gate above.
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=60 * 60 * 12)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


def _unlock_page(bad: bool) -> str:
    err = "<p style='color:#9b1c1c;font-size:13px'>Incorrect passphrase — try again.</p>" if bad else ""
    return f"""<!doctype html><html><head><meta charset=utf-8><title>AIMS</title>
<link rel=stylesheet href=/static/aims.css>
<style>body{{background:var(--paper-warm);font-family:var(--font-body);display:flex;min-height:92vh;align-items:center;justify-content:center}}
.box{{background:#fff;border-radius:12px;padding:30px 34px;box-shadow:0 10px 40px rgba(0,0,0,.12);max-width:360px;text-align:center}}
.mark{{font-family:var(--font-display);font-weight:800;color:var(--azure);font-size:26px}}
h2{{font-family:var(--font-display);color:var(--ink-charcoal);margin:8px 0 4px;font-size:19px}}
input{{width:100%;padding:11px;border:1px solid var(--rule);border-radius:6px;font-size:15px;margin:12px 0}}
button{{background:var(--maroon);color:#fff;border:none;border-radius:6px;padding:11px 18px;font-family:var(--font-display);font-weight:600;font-size:14px;cursor:pointer;width:100%}}
.muted{{color:var(--ink-gray);font-size:13px}}</style></head>
<body><form class=box method=post action=/unlock>
<div class=mark>AIMS</div><h2>Enter access passphrase</h2>
<p class=muted>Private preview of the AI-Powered Implicit Motive System.</p>{err}
<input type=password name=passphrase placeholder="passphrase" autofocus>
<button type=submit>Enter</button></form></body></html>"""


@app.get("/unlock", response_class=HTMLResponse)
def unlock_form(bad: int = 0) -> str:
    return _unlock_page(bool(bad))


@app.post("/unlock")
def unlock_submit(request: Request, passphrase: str = Form("")) -> RedirectResponse:
    if config.ACCESS_PASSPHRASE and passphrase == config.ACCESS_PASSPHRASE:
        request.session["ok"] = True
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/unlock?bad=1", status_code=303)


@app.on_event("startup")
def _startup() -> None:
    init_db()


def get_profile(subject_id: str, *, name: str = "", client: str = "",
                is_sample: bool = False) -> SubjectProfile:
    """DB first (real scored data); fall back to the fixtures for demo subjects."""
    if subject_id.upper() in ("PAT", "SAMPLE"):
        from report.sample_profile import pat_example_profile
        return pat_example_profile()
    if subject_id in set(subject_ids_with_scores()):
        return aggregate_db_subject(subject_id, name=name, client=client, is_sample=is_sample)
    return aggregate_fixture_subject(subject_id, name=name, client=client, is_sample=is_sample)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    if config.HOSTED:
        status = (f"<span class=pill>Live scoring enabled</span> {SETTINGS.ensemble_n} "
                  "samples/story · powered centrally.")
    elif SETTINGS.has_live_key():
        status = (f"<span class=pill>Live engine ready</span> DeepSeek key "
                  f"<b>{SETTINGS.key_hint()}</b>, {SETTINGS.ensemble_n} samples/story.")
    else:
        status = ("<span class=pill warn>No API key yet</span> Add your DeepSeek key in "
                  "<b>Settings</b> to score live — or use the Sample engine.")
    # In the hosted/public build, hide the Settings/API page and the shared Database list.
    settings_btn = "" if config.HOSTED else '<a class="btn ghost" href="/settings">Settings &amp; API key</a>'
    database_card = "" if config.HOSTED else (
        '<div class=card><h3 style="margin-top:0">Database</h3>'
        '<a class="btn ghost" href="/subjects">Prior reports</a></div>')
    return f"""<!doctype html><html><head><meta charset=utf-8>
<title>AIMS</title><link rel=stylesheet href=/static/aims.css>
<style>body{{padding:40px;max-width:780px;margin:auto;background:var(--paper-warm)}}
.card{{background:#fff;border-radius:8px;padding:22px 26px;box-shadow:0 4px 18px rgba(0,0,0,.08);margin-bottom:18px}}
a.btn{{display:inline-block;background:var(--maroon);color:#fff;text-decoration:none;padding:11px 18px;border-radius:6px;font-family:var(--font-display);font-weight:600;font-size:14px;margin:4px 8px 4px 0}}
a.btn.az{{background:var(--azure-deep)}}a.btn.ghost{{background:#eee;color:var(--ink)}}
h1,h2,h3{{font-family:var(--font-display);color:var(--ink-charcoal)}} .muted{{color:var(--ink-gray)}}
.mark{{font-family:var(--font-display);font-weight:800;color:var(--azure)}}
.pill{{display:inline-block;background:var(--azure-tint);color:var(--azure-deep);border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600;margin-right:6px}}
.pill.warn{{background:var(--maroon-tint);color:var(--maroon-alt)}}</style></head>
<body>
<h1><span class=mark>AIMS</span> — AI-Powered Implicit Motive System</h1>
<div class=card><h2 style="margin-top:0">Start an evaluation</h2>
<p class=muted>Run a person's short Picture-Story responses through the scoring engine and get an
HR-ready report: percentiles, plain-language narrative, and role-relevant implications.</p>
<a class=btn href="/evaluate">Single evaluation</a>
<a class="btn az" href="/bulk">Multiple entries</a>
{settings_btn}
<p class=muted style="margin-bottom:0">{status}</p></div>
<div class=card><h3 style="margin-top:0">Automated data collection for subjects
<span class="pill warn" style="vertical-align:middle">coming soon</span></h3>
<p class=muted>Administer the Picture Story Exercise directly to candidates — guided, standardized and
timed — and feed their responses straight into scoring. In development.</p>
<a class="btn ghost" href="/live">Preview the planned flow</a></div>
{database_card}
<div class=card><h3 style="margin-top:0">Example report</h3>
<p class=muted>No key needed — uses the bundled sample data.</p>
<a class="btn ghost" href="/report/PAT?sample=1&role=Former%20CEO%2C%20Firm">Sample report (Pat Example)</a></div>
</body></html>"""


@app.get("/report/{subject_id}", response_class=HTMLResponse)
def report(subject_id: str, request: Request, sample: int = 0, internal: int = 0,
           name: str = "", role: str = "", client: str = "") -> str:
    profile = get_profile(subject_id, name=name, client=client, is_sample=bool(sample))
    return render_report(profile, subject_role=role, client=client, internal=bool(internal))


@app.get("/report/{subject_id}.pdf")
def report_pdf(subject_id: str, request: Request, sample: int = 0, internal: int = 0):
    from report.pdf import url_to_pdf
    base = str(request.base_url).rstrip("/")
    url = f"{base}/report/{subject_id}?sample={sample}&internal={internal}"
    out = config.REPORTS_DIR / f"{subject_id}.pdf"
    res = url_to_pdf(url, out)
    if res is None:
        return HTMLResponse(
            "<p>PDF export needs Chromium. Run <code>python -m playwright install chromium</code>, "
            "or use your browser's Print → Save as PDF on the report page.</p>", status_code=501)
    return FileResponse(str(res), media_type="application/pdf", filename=f"AIMS_{subject_id}.pdf")


@app.get("/subjects", response_class=HTMLResponse)
def subjects() -> str:
    ids = sorted(set(subject_ids_with_scores()))
    rows = "".join(
        f"<tr><td><b>{i}</b></td>"
        f"<td><a href='/report/{i}' target=_blank>report</a> · "
        f"<a href='/report/{i}.pdf'>pdf</a></td>"
        f"<td><form method=post action='/subjects/{i}/delete' "
        f"onsubmit=\"return confirm('Delete {i} and all their stories, scores and reports?')\">"
        f"<button class='btn ghost'>delete</button></form></td></tr>" for i in ids)
    body = f"""<h1><span class=mark>Prior reports</span></h1>
<div class=card><p class=muted>{len(ids)} subject(s) with scored data. Deletion is a hard
cascade — stories, scores, reports and consent records are all removed.</p>
<table><thead><tr><th>Subject</th><th>Report</th><th>Data</th></tr></thead>
<tbody>{rows or '<tr><td colspan=3 class=muted>No reports yet — run an evaluation first.</td></tr>'}</tbody></table></div>"""
    return HTMLResponse(_OPERATOR_CSS + body)


@app.post("/subjects/{subject_id}/delete")
def subject_delete(subject_id: str) -> RedirectResponse:
    delete_subject(subject_id)
    return RedirectResponse("/subjects", status_code=303)


_OPERATOR_CSS = """<link rel=stylesheet href=/static/aims.css>
<style>body{padding:32px;max-width:760px;margin:auto;background:var(--paper-warm)}
.card{background:#fff;border-radius:8px;padding:22px 26px;box-shadow:0 4px 18px rgba(0,0,0,.08)}
h1{font-family:var(--font-display);color:var(--ink-charcoal)}.mark{font-family:var(--font-display);font-weight:800;color:var(--azure)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--rule)}
th{font-family:var(--font-display);font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-gray)}
.muted{color:var(--ink-gray)}form{display:inline}button.btn{background:#eee;color:var(--ink);border:none;border-radius:5px;padding:6px 12px;font-family:var(--font-display);font-weight:600;font-size:12px;cursor:pointer}
a{color:var(--azure-deep)}</style><p><a href="/" class=muted style=text-decoration:none>&larr; AIMS</a></p>"""
