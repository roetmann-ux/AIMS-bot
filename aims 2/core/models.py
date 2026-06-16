"""Shared domain models (Pydantic) used across every module.

These are storage-agnostic. ``contract.py`` converts between these and the engine's CSV rows;
``db.py`` persists them to SQLite. The report and aggregation layers consume them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .ids import parse_story_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def count_words(text: str) -> int:
    return len((text or "").split())


# --------------------------------------------------------------------------- input
class Story(BaseModel):
    """A single PSE story before scoring. Produced identically by live and bulk adapters."""
    story_id: str
    subject_id: str
    picture: int
    text: str
    source: str = "bulk"            # "live" | "bulk"
    word_count: int = 0
    created_at: datetime = Field(default_factory=_now)

    @classmethod
    def make(cls, subject_id: str, picture: int, text: str, source: str = "bulk") -> "Story":
        from .ids import make_story_id
        return cls(story_id=make_story_id(subject_id, picture), subject_id=subject_id,
                   picture=picture, text=text or "", source=source,
                   word_count=count_words(text))


# --------------------------------------------------------------------------- scored
class CategoryScore(BaseModel):
    code: str
    present: int = 0                 # 0/1 after thresholding (Act: 1 if any Act+/-/?)
    value: Optional[str] = None      # raw value; for Act the enum string (Act+/Act-/Act?)
    confidence: float = 0.0
    explanation: str = ""
    majority: Optional[str] = None
    majority_explanation: str = ""
    dissenting_explanation: str = ""


class ScoredStory(BaseModel):
    story_id: str
    subject_id: str
    picture: int
    motive: str
    gate_present: bool = False
    total: int = 0
    word_count: int = 0
    categories: dict[str, CategoryScore] = Field(default_factory=dict)
    provider_votes: str = ""
    stage_b_trigger: str = "none"
    stage_b_override: str = "no"
    story_text: str = ""
    engine_version: str = ""
    prompt_version: str = ""
    call_logs: list[dict] = Field(default_factory=list)   # verbatim per-call diagnostics (live engine)
    created_at: datetime = Field(default_factory=_now)

    @classmethod
    def empty(cls, story: Story, motive: str) -> "ScoredStory":
        sid = parse_story_id(story.story_id)
        return cls(story_id=story.story_id, subject_id=story.subject_id or sid.subject_id,
                   picture=story.picture or sid.picture, motive=motive,
                   word_count=story.word_count or count_words(story.text),
                   story_text=story.text)

    def present_codes(self) -> list[str]:
        return [c for c, s in self.categories.items() if s.present]


# --------------------------------------------------------------------------- aggregated
class ExpressionItem(BaseModel):
    code: str
    label: str
    definition: str
    polarity: str = "neutral"
    count: int = 0                   # number of stories (of the protocol) the category fired in
    evidence: str = "None"           # None | Some | Strong | Very Strong


class MotiveResult(BaseModel):
    motive: str
    display_name: str
    report_label: str
    enabled: bool = True             # False -> render "[to be done]" placeholder
    n_stories: int = 0
    word_count_total: int = 0
    raw_score: float = 0.0           # sum of story Totals
    corrected_score: float = 0.0     # length-corrected (or == raw if correction off)
    score_used: float = 0.0          # whichever drives the percentile (per config)
    t_score: Optional[float] = None  # within-sample T (mean 50, sd 10)
    percentile: Optional[int] = None
    band: str = ""                   # significantly low ... significantly high
    sample_relative: bool = True
    cohort_version: str = ""         # versioned reference-cohort hash used for this percentile
    gate_hits: int = 0               # stories where imagery gate fired
    expressions: list[ExpressionItem] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)   # engine explanations for appendix


class SubjectProfile(BaseModel):
    subject_id: str
    name: str = ""
    client: str = ""
    n_stories: int = 0
    created_at: datetime = Field(default_factory=_now)
    motives: dict[str, MotiveResult] = Field(default_factory=dict)
    is_sample: bool = False          # SAMPLE watermark toggle
    engine_label: str = ""           # the engine that actually produced these scores

    def motive(self, key: str) -> Optional[MotiveResult]:
        return self.motives.get(key)
