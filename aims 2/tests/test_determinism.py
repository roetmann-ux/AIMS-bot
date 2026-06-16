"""Determinism & cohort-versioning tests (Phase 5).

These cover the layers that can be verified without the live API. The API layer itself is made
reproducible by temperature=0 (asserted here); residual LLM nondeterminism at temp 0 is measured
on the live 9-call diagnostic, not unit-tested.
"""
from __future__ import annotations

import pytest

import config
from aggregate import aggregate_fixture_subject
from aggregate.norms import cohort_fingerprint, get_norms
from report.renderer import render_report
from scoring_engine.contract import load_fixture
from scoring_engine.providers.deepseek import DeepSeekProvider, _deterministic_mode
from core.motives import get_motive

# 7/9 see achievement imagery (gate mean .78 -> not borderline -> no Stage-B/API call).
_FIXED = [
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 1, "F+": 1, "TH": 0},
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 0, "F+": 1, "TH": 0},
    {"AI": 1, "Need": 0, "Act": "Act+", "GA+": 1, "F+": 0, "TH": 0},
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 1, "F+": 1, "TH": 0},
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 0, "F+": 0, "TH": 0},
    {"AI": 1, "Need": 0, "Act": "Act+", "GA+": 0, "F+": 1, "TH": 0},
    {"AI": 1, "Need": 1, "Act": "Act+", "GA+": 1, "F+": 1, "TH": 0},
    {"AI": 0}, {"AI": 0},
]


def test_temperature_is_zero_by_default():
    # The root-cause fix: scoring calls must not sample at temperature 1.0.
    assert config.DEEPSEEK_TEMPERATURE == 0.0


def test_fixture_pipeline_is_deterministic():
    a = aggregate_fixture_subject("P723")
    b = aggregate_fixture_subject("P723")
    for m in ("achievement", "affiliation", "influence"):
        ra, rb = a.motive(m), b.motive(m)
        assert (ra.raw_score, ra.percentile, ra.band) == (rb.raw_score, rb.percentile, rb.band)


def test_live_aggregation_deterministic_given_fixed_responses():
    spec = get_motive("achievement")
    prov = DeepSeekProvider.__new__(DeepSeekProvider)   # no key/client needed for _aggregate
    prov.n = 9

    class _S:
        story_id, subject_id, picture, text, word_count = "X_PIC1", "X", 1, "t", 1
    s1 = prov._aggregate(spec, _S(), [dict(r) for r in _FIXED], attempted=9)
    s2 = prov._aggregate(spec, _S(), [dict(r) for r in _FIXED], attempted=9)
    assert s1.total == s2.total
    assert {c: v.present for c, v in s1.categories.items()} == \
           {c: v.present for c, v in s2.categories.items()}


def test_act_tiebreak_is_deterministic():
    assert _deterministic_mode(["Act-", "Act+", "Act+", "Act-"]) == "Act+"   # tie -> lexicographic
    assert _deterministic_mode(["Act?", "Act-", "Act-"]) == "Act-"


def test_reference_cohort_is_versioned():
    nt = get_norms("achievement")
    assert nt.version and len(nt.version) == 12
    assert cohort_fingerprint() == cohort_fingerprint()      # stable
    html = render_report(aggregate_fixture_subject("P723"))
    assert cohort_fingerprint() in html                      # recorded in the report


def test_aims_reproduces_v12_ensemble_codings_on_p723():
    """AIMS' fixture engine replays the V12/V11/V2 ensemble codings with no transformation."""
    fx = load_fixture("achievement")
    aims_total = sum(s.total for s in fx.values() if s.subject_id == "P723")
    # read the same totals straight from the source CSV
    import csv
    path = config.FIXTURES_DIR / config.NORM_FIXTURES["achievement"]
    csv_total = 0
    for row in csv.DictReader(open(path, encoding="utf-8")):
        sid = row["StoryID"]
        if sid.startswith("P723_PIC"):
            csv_total += int(float(row["ensemble Total"] or 0))
    assert aims_total == csv_total


@pytest.mark.skip(reason="Percentile convergence to the human/V11-V12-V2 numbers (Ach=92/Pow=0/"
                         "Aff=49) needs same WAVE (target is W2; AIMS norms W1), same "
                         "standardisation (within-sample t vs AIMS parametric Phi(z)+length "
                         "correction), and the ported V12 RAG prompt for the live engine. Tracked "
                         "in diagnostics/aims_vs_v11_v12_v2_diff.md — not a plumbing fix.")
def test_aims_matches_v11_v12_v2_on_subject_723():
    ...
