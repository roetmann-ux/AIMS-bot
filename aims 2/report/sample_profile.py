"""The canonical 'Pat Example' showcase — reproduces the AIMS sample deck 1:1.

Used for /report/PAT. Demonstrates the full evidence range (Very Strong / Strong / Some / None)
and the exact significantly-high Achievement / significantly-low Affiliation / moderate Influence
profile from "Sample AIMS Report June 14 2026.pptx". Real subjects render from scored data; this
is a fixed reference so the output can be eyeballed against the source deck.
"""
from __future__ import annotations

from core.models import ExpressionItem, MotiveResult, SubjectProfile
from core.motives import MotiveSpec, evidence_label, get_motive


def _exprs(spec: MotiveSpec, counts: dict[str, int]) -> list[ExpressionItem]:
    out = []
    for cat in spec.expression_categories():
        c = counts.get(cat.code, 0)
        out.append(ExpressionItem(code=cat.code, label=cat.label, definition=cat.definition,
                                  polarity=cat.polarity, count=c, evidence=evidence_label(c)))
    return out


def _result(key: str, pct: int, band: str, counts: dict[str, int],
            raw: float, gate_hits: int) -> MotiveResult:
    spec = get_motive(key)
    return MotiveResult(
        motive=key, display_name=spec.display_name, report_label=spec.report_label,
        enabled=True, n_stories=6, word_count_total=520, gate_hits=gate_hits,
        raw_score=raw, corrected_score=raw, score_used=raw,
        t_score=round(50 + (pct - 50) / 10 * 2.5, 1), percentile=pct, band=band,
        sample_relative=True, expressions=_exprs(spec, counts))


def pat_example_profile() -> SubjectProfile:
    p = SubjectProfile(subject_id="PAT", name="Pat Example", client="", n_stories=6, is_sample=True)
    p.motives["achievement"] = _result(
        "achievement", 85, "significantly high",
        {"Need": 4, "Act": 6, "GA+": 2, "F+": 3}, raw=11, gate_hits=5)
    p.motives["affiliation"] = _result(
        "affiliation", 10, "significantly low", {}, raw=1, gate_hits=1)
    p.motives["influence"] = _result(
        "influence", 42, "moderate",
        {"N": 2, "Act": 2, "Pa+": 1, "SA": 1}, raw=4, gate_hits=3)
    return p
