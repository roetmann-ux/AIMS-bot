"""Fixture provider: replays the founder's existing engine output CSVs.

Zero cost, deterministic, and reproduces the scoring contract exactly. This powers the demo
and all tests, and seeds the all-three-motive report without spending API credits.
"""
from __future__ import annotations

from core.models import ScoredStory, Story

from ..contract import load_fixture
from .base import ScoringProvider


def _norm(text: str) -> str:
    return " ".join((text or "").split()).strip().lower()


class FixtureProvider(ScoringProvider):
    name = "fixture"

    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, ScoredStory]] = {}
        self._by_text: dict[str, dict[str, ScoredStory]] = {}

    def _load(self, motive: str) -> None:
        if motive in self._by_id:
            return
        fx = load_fixture(motive)
        self._by_id[motive] = fx
        self._by_text[motive] = {_norm(s.story_text): s for s in fx.values()}

    def score_story(self, story: Story, motive: str) -> ScoredStory:
        self._load(motive)
        hit = self._by_id[motive].get(story.story_id)
        if hit is None:
            hit = self._by_text[motive].get(_norm(story.text))
        if hit is None:
            return ScoredStory.empty(story, motive)
        # Preserve the incoming story's identity/source; keep the fixture's scores.
        out = hit.model_copy(deep=True)
        out.subject_id = story.subject_id or out.subject_id
        out.story_id = story.story_id or out.story_id
        out.picture = story.picture or out.picture
        return out
