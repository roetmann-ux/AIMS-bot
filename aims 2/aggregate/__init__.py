"""Aggregation: scored stories -> per-subject motive profile (raw -> corrected -> percentile).

One pipeline for both live and bulk input. Public API:
    aggregate_subject(subject_id, scored_by_motive, ...) -> SubjectProfile
    aggregate_fixture_subject(subject_id) -> SubjectProfile     # demo/test convenience
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

import config
from core.models import MotiveResult, ScoredStory, SubjectProfile
from core.motives import MotiveSpec, all_motives, get_motive

from .expressions import dominant_expressions, evidence_quotes, rollup
from .norms import get_norms

__all__ = ["aggregate_subject", "aggregate_fixture_subject", "build_motive_result"]


def build_motive_result(spec: MotiveSpec, stories: list[ScoredStory]) -> MotiveResult:
    enabled = spec.key in config.ENABLED_MOTIVES and len(stories) > 0
    if not stories:
        return MotiveResult(motive=spec.key, display_name=spec.display_name,
                            report_label=spec.report_label, enabled=False)

    raw = float(sum(s.total for s in stories))
    words = int(sum(s.word_count for s in stories))
    gate_hits = sum(1 for s in stories if s.gate_present)
    norms = get_norms(spec.key)
    st = norms.standardize(raw, words)
    score_used = st["corrected"] if norms.correction != "none" else st["raw"]

    return MotiveResult(
        motive=spec.key, display_name=spec.display_name, report_label=spec.report_label,
        enabled=enabled, n_stories=len(stories), word_count_total=words, gate_hits=gate_hits,
        raw_score=st["raw"], corrected_score=st["corrected"], score_used=score_used,
        t_score=st["t_score"], percentile=st["percentile"], band=st["band"],
        sample_relative=norms.sample_relative, cohort_version=norms.version,
        expressions=rollup(spec, stories),
        evidence_quotes=evidence_quotes(spec, stories))


def aggregate_subject(subject_id: str, scored_by_motive: dict[str, list[ScoredStory]],
                      name: str = "", client: str = "", is_sample: bool = False) -> SubjectProfile:
    profile = SubjectProfile(subject_id=subject_id, name=name or subject_id, client=client,
                             is_sample=is_sample)
    n = 0
    for spec in all_motives():
        stories = scored_by_motive.get(spec.key, [])
        n = max(n, len(stories))
        profile.motives[spec.key] = build_motive_result(spec, stories)
    profile.n_stories = n
    # Record the engine that actually produced these scores (so the report can't misrepresent it).
    first = next((s for stories in scored_by_motive.values() for s in stories
                  if s.engine_version), None)
    if first:
        profile.engine_label = first.engine_version
    return profile


def aggregate_db_subject(subject_id: str, name: str = "", client: str = "",
                         is_sample: bool = False) -> SubjectProfile:
    """Build a profile from scored stories already persisted in SQLite (bulk/live path)."""
    from core.db import Subject, scored_stories_for_subject, session
    if not name or not client:
        with session() as s:
            sub = s.get(Subject, subject_id)
            if sub:
                name = name or sub.name
                client = client or sub.client
    scored_by_motive: dict[str, list[ScoredStory]] = {}
    for spec in all_motives():
        stories = scored_stories_for_subject(subject_id, spec.key)
        stories.sort(key=lambda s: s.picture)
        scored_by_motive[spec.key] = stories
    return aggregate_subject(subject_id, scored_by_motive, name=name, client=client,
                             is_sample=is_sample)


def aggregate_fixture_subject(subject_id: str, name: str = "", client: str = "",
                              is_sample: bool = False) -> SubjectProfile:
    """Build a profile straight from the fixture CSVs (no DB) — used by the demo & tests."""
    from scoring_engine.contract import load_fixture
    scored_by_motive: dict[str, list[ScoredStory]] = defaultdict(list)
    for spec in all_motives():
        fx = load_fixture(spec.key)
        for s in fx.values():
            if s.subject_id == subject_id:
                scored_by_motive[spec.key].append(s)
        scored_by_motive[spec.key].sort(key=lambda s: s.picture)
    return aggregate_subject(subject_id, scored_by_motive, name=name, client=client,
                             is_sample=is_sample)
