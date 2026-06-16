"""Render a SubjectProfile into the AIMS HTML report (identical for live or bulk input)."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
from core.models import SubjectProfile
from core.motives import all_motives

from .narrative import build_narrative, profile_implications

_TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                   autoescape=select_autoescape(["html", "j2"]),
                   trim_blocks=True, lstrip_blocks=True)


def _evi_class(label: str) -> str:
    return label.lower().replace(" ", "-")


_env.filters["evi"] = _evi_class


def _report_meta(profile: SubjectProfile) -> dict:
    """Reproducibility metadata stamped into every report (brief: traceable cohort + engine).

    `engine` reflects what ACTUALLY produced the scores (from the scored stories), so a live
    zero-shot run can never display itself as the validated 'V12' pipeline.
    """
    from aggregate.norms import cohort_fingerprint
    from core.runtime import SETTINGS
    return {
        "engine": profile.engine_label or f"{config.PROMPT_VERSION}/{config.ENGINE_VERSION} (sample)",
        "provider": SETTINGS.scoring_provider,
        "ensemble_n": SETTINGS.ensemble_n,
        "temperature": config.DEEPSEEK_TEMPERATURE,
        "seed": (config.DEEPSEEK_SEED or "—"),
        "wc_correction": config.WORD_COUNT_CORRECTION,
        "cohort": cohort_fingerprint(),
    }


def build_pages(profile: SubjectProfile, internal: bool) -> list[dict]:
    pages = [{"type": "title"}, {"type": "confidential"}, {"type": "exec"}]
    for spec in all_motives():
        r = profile.motives.get(spec.key)
        if r and r.enabled:
            pages.append({"type": "overall", "motive": spec.key})
            pages.append({"type": "expressions", "motive": spec.key})
    pages += [{"type": "appendix_divider"}, {"type": "appendix_defs"},
              {"type": "appendix_elements"}]
    if internal:
        pages.append({"type": "appendix_evidence"})
    return pages


_CSS_PATH = Path(__file__).parent / "static" / "aims.css"


def render_report(profile: SubjectProfile, *, subject_role: str = "", client: str = "",
                  date: Optional[str] = None, internal: bool = False,
                  inline_css: bool = False) -> str:
    specs = {m.key: m for m in all_motives()}
    narratives = {k: build_narrative(profile.name, specs[k], r)
                  for k, r in profile.motives.items() if r.enabled}
    date = date or _dt.date.today().strftime("%B %Y")
    ctx = {
        "profile": profile, "M": specs, "N": narratives,
        "motives": all_motives(), "pages": build_pages(profile, internal),
        "subject_role": subject_role, "client": client or profile.client or config.CLIENT_NAME_DEFAULT,
        "date": date, "internal": internal, "is_sample": profile.is_sample,
        "copyright": config.COPYRIGHT,
        "profile_implications": profile_implications(profile.name, profile),
        "sample_relative": any(r.sample_relative for r in profile.motives.values() if r.enabled),
        "meta": _report_meta(profile),
    }
    html = _env.get_template("report.html.j2").render(**ctx)
    if inline_css:
        css = _CSS_PATH.read_text(encoding="utf-8")
        html = html.replace('<link rel="stylesheet" href="/static/aims.css">',
                            f"<style>\n{css}\n</style>")
    return html


def save_report(profile: SubjectProfile, *, internal: bool = False, **kw) -> Path:
    html = render_report(profile, internal=internal, **kw)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "_internal" if internal else ""
    path = config.REPORTS_DIR / f"{profile.subject_id}{suffix}.html"
    path.write_text(html, encoding="utf-8")
    return path
