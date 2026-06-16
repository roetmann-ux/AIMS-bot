"""Live PSE administration (Feature A) — scaffolded for the next milestone.

The full flow (consent -> standardized instructions -> 6 pictures one at a time, each with a live
word counter + optional timer + soft MIN_WORDS nudge -> persist Story records -> enqueue scoring
-> route to report) shares the SAME downstream pipeline as bulk, so its output is identical.

This stub exposes the intake/consent surface and documents the tunables already wired in config.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

import config

router = APIRouter()


@router.get("/live", response_class=HTMLResponse)
def live_home() -> str:
    pics = config.PICTURE_ORDER
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Automated data collection — AIMS</title>
<link rel=stylesheet href=/static/aims.css>
<style>body{{padding:32px;max-width:760px;margin:auto;background:var(--paper-warm)}}
.card{{background:#fff;border-radius:8px;padding:22px 26px;box-shadow:0 4px 18px rgba(0,0,0,.08);margin-bottom:18px}}
h1,h3{{font-family:var(--font-display);color:var(--ink-charcoal)}}.mark{{font-family:var(--font-display);font-weight:800;color:var(--azure)}}
.muted{{color:var(--ink-gray)}}.pill{{display:inline-block;background:var(--azure-tint);color:var(--azure-deep);border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600}}</style></head>
<body><p><a href="/" class=muted style=text-decoration:none>&larr; AIMS</a></p>
<h1><span class=mark>Automated data collection for subjects</span> <span class=pill>coming soon</span></h1>
<div class=card><h3>Standardized administration</h3>
<p class=muted>Every candidate sees the same {len(pics.split(','))} pictures in a fixed order,
with identical instructions and timing — required for comparability and validity. One picture at
a time; no going back (preserves spontaneity).</p>
<ul class=muted>
<li>Soft minimum: a one-time, non-blocking nudge below <b>{config.MIN_WORDS}</b> words.</li>
<li>Per-picture timer: <b>{config.TIMER_SECONDS}s</b> ({'off' if not config.TIMER_SECONDS else 'on'}).</li>
<li>Picture order: <b>{pics}</b>. Place 6 images in <code>pictures/</code>.</li>
<li>Consent captured + timestamped before the first story (stored in SQLite).</li>
</ul>
<p class=muted>On completion the 6 Story records flow into the <b>same</b> scoring → aggregation →
report pipeline as bulk input, so the live report is identical to a bulk-generated one.</p></div>
</body></html>"""
