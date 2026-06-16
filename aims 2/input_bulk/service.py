"""Bulk batch orchestration: score -> persist -> aggregate -> render reports.

Both bulk and live input converge here on the same pipeline, so reports are identical.
Batch state is kept in-memory (fine for a single-operator pilot); scores/reports persist to SQLite.
"""
from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import config
from aggregate import aggregate_db_subject
from core.db import save_scored_batch, save_story, upsert_subject
from core.models import ScoredStory, Story
from report.renderer import save_report
from scoring_engine import estimate_cost, get_provider, score_batch


@dataclass
class BatchState:
    id: str
    status: str = "ready"            # ready | scoring | done | error
    columns: list[str] = field(default_factory=list)
    mapping: dict = field(default_factory=dict)
    preview: list[dict] = field(default_factory=list)
    stories: list[Story] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    progress: dict = field(default_factory=lambda: {"done": 0, "total": 0})
    subjects: list[dict] = field(default_factory=list)
    message: str = ""
    provider: str = ""                 # "" -> use the saved Settings engine
    motives: list | None = None        # None -> all enabled motives
    subject_name: str = ""             # friendly display name (single-subject evaluations)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def n_stories(self) -> int:
        return len(self.stories)

    @property
    def n_subjects(self) -> int:
        return len({s.subject_id for s in self.stories})

    @property
    def motive_list(self) -> list[str]:
        return self.motives or list(config.ENABLED_MOTIVES)

    def cost(self) -> dict:
        return estimate_cost(self.n_stories, provider=self.provider or None,
                             motives=len(self.motive_list))


REGISTRY: dict[str, BatchState] = {}


def new_batch(stories: list[Story], errors: list[str], columns: list[str],
              mapping: dict, preview: list[dict]) -> BatchState:
    bid = uuid.uuid4().hex[:10]
    st = BatchState(id=bid, columns=columns, mapping=mapping, preview=preview,
                    stories=stories, errors=errors)
    REGISTRY[bid] = st
    return st


def get_batch(bid: str) -> BatchState | None:
    return REGISTRY.get(bid)


def run_batch(bid: str) -> None:
    st = REGISTRY.get(bid)
    if not st or not st.stories:
        return
    try:
        st.status = "scoring"
        motives = st.motive_list
        st.progress = {"done": 0, "total": len(st.stories) * len(motives)}
        provider = get_provider(st.provider or None)

        for story in st.stories:
            save_story(story)
        subjects = sorted({s.subject_id for s in st.stories})
        single = len(subjects) == 1 and bool(st.subject_name)
        for subj in subjects:
            upsert_subject(subj, name=(st.subject_name if single else ""), source="bulk")

        for k, motive in enumerate(motives):
            base = k * len(st.stories)
            scored: list[ScoredStory] = score_batch(
                st.stories, motive, provider=provider,
                progress=lambda d, t, _b=base: st.progress.update(done=_b + d))
            save_scored_batch(scored)

        st.subjects = []
        for subj in subjects:
            profile = aggregate_db_subject(subj, name=(st.subject_name or subj))
            save_report(profile)
            st.subjects.append({
                "id": subj,
                "motives": {m: (profile.motive(m).percentile if profile.motive(m) else None)
                            for m in motives},
                "bands": {m: (profile.motive(m).band if profile.motive(m) else "")
                          for m in motives},
            })
        st.status = "done"
        st.message = f"Scored {st.n_stories} stories for {st.n_subjects} subjects."
    except Exception as exc:  # keep the batch inspectable on failure
        st.status = "error"
        st.message = f"{type(exc).__name__}: {exc}"


def summary_csv(bid: str) -> Path | None:
    st = REGISTRY.get(bid)
    if not st:
        return None
    out = config.REPORTS_DIR / f"batch_{bid}_summary.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["subject_id", "motive", "n_stories", "raw", "corrected",
                    "t_score", "percentile", "band"])
        for subj in sorted({s.subject_id for s in st.stories}):
            profile = aggregate_db_subject(subj, name=subj)
            for m, r in profile.motives.items():
                if r.enabled:
                    w.writerow([subj, m, r.n_stories, r.raw_score, r.corrected_score,
                                r.t_score, r.percentile, r.band])
    return out
