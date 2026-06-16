"""Unit tests for the AIMS pipeline (run: .venv/bin/pytest -q)."""
from __future__ import annotations

import config
from aggregate import aggregate_fixture_subject
from aggregate.norms import NormTable, band_for_percentile
from core.ids import parse_story_id
from core.motives import all_motives, evidence_label, get_motive
from input_bulk.parsing import auto_map, to_stories
from scoring_engine.contract import load_fixture


# ---------------------------------------------------------------- contract
def test_contract_reproduces_canonical_w2_row():
    w2 = load_fixture("achievement", config.FIXTURES_DIR / "output_Achievement_V12_W2_deepseek9.csv")
    s = w2["P010_PIC1"]
    assert s.gate_present is False and s.total == 0
    assert s.provider_votes == "deepseek=0/9"
    assert s.story_text.startswith("A cruise ship")


def test_all_three_motives_parse_data_driven():
    for m in all_motives():
        fx = load_fixture(m.key)
        assert len(fx) > 100
        # every story carries the gate category for its motive
        any_story = next(iter(fx.values()))
        assert m.gate_code in any_story.categories


def test_storyid_parsing_folds_suffix():
    assert parse_story_id("P010_PIC1") == ("P010", 1)
    assert parse_story_id("P104_PIC1_b") == ("P104", 1)   # transcription variant folds back


# ---------------------------------------------------------------- aggregation
def test_percentiles_and_bands_in_range():
    p = aggregate_fixture_subject("P020")
    for r in p.motives.values():
        assert r.enabled
        assert 1 <= r.percentile <= 99
        assert r.band in {b for _, b in config.BANDS}


def test_word_count_correction_changes_scores():
    cohort = [(2, 80), (5, 200), (8, 300), (1, 60), (6, 240)]
    corrected = NormTable.build("achievement", cohort, "regression_residual")
    raw = NormTable.build("achievement", cohort, "none")
    assert corrected.correction == "regression_residual"
    assert raw.correction == "none"
    # a very long protocol with a middling raw should be pulled DOWN by length correction
    assert corrected.correct(6, 300) < 6


def test_band_cutpoints():
    assert band_for_percentile(5) == "significantly low"
    assert band_for_percentile(50) == "moderate"
    assert band_for_percentile(95) == "significantly high"


# ---------------------------------------------------------------- evidence
def test_evidence_labels():
    assert evidence_label(0) == "None"
    assert evidence_label(2) == "Some"
    assert evidence_label(3) == "Strong"
    assert evidence_label(5) == "Very Strong"


# ---------------------------------------------------------------- bulk parsing
def test_bulk_derives_subject_and_picture_from_storyid():
    rows = [{"StoryID": "P900_PIC3", "story_text": "A determined engineer refines the design."}]
    mapping = auto_map(list(rows[0].keys()))
    stories, errors = to_stories(rows, mapping)
    assert not errors
    assert stories[0].subject_id == "P900" and stories[0].picture == 3
    assert stories[0].word_count == 6


def test_bulk_flags_empty_story():
    rows = [{"subject_id": "P1", "picture": "1", "story_text": ""}]
    _, errors = to_stories(rows, auto_map(list(rows[0].keys())))
    assert errors and "empty" in errors[0].lower()


# ---------------------------------------------------------------- sample
def test_pat_sample_matches_deck():
    from report.sample_profile import pat_example_profile
    p = pat_example_profile()
    ach = p.motive("achievement")
    assert ach.percentile == 85 and ach.band == "significantly high"
    act = next(e for e in ach.expressions if e.code == "Act")
    assert act.evidence == "Very Strong"
    assert p.motive("affiliation").band == "significantly low"
