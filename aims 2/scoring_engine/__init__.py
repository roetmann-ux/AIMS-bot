"""AIMS scoring engine — the contract boundary.

Public API (stable; the rest of the app depends only on this):
    score_story(story_text, motive, story_id) -> ScoredStory
    score_batch(stories, motive, provider=?, progress=?) -> list[ScoredStory]
    get_provider(name=?) -> ScoringProvider
    estimate_cost(n_stories) -> dict
"""
from __future__ import annotations

from typing import Optional

import config
from core.ids import parse_story_id
from core.models import ScoredStory, Story, count_words

from .providers.base import ProgressCb, ScoringProvider
from .providers.fixture import FixtureProvider


def get_provider(name: Optional[str] = None) -> ScoringProvider:
    from core.runtime import SETTINGS
    name = (name or SETTINGS.scoring_provider or "fixture").lower()
    if name == "fixture":
        return FixtureProvider()
    if name == "deepseek":
        from .providers.deepseek import DeepSeekProvider  # lazy: avoids needing keys for fixtures
        return DeepSeekProvider(api_key=SETTINGS.deepseek_api_key, model=SETTINGS.deepseek_model,
                                base_url=SETTINGS.deepseek_base_url, n=SETTINGS.ensemble_n)
    raise ValueError(f"Unknown scoring provider {name!r} (use 'fixture' or 'deepseek')")


def score_story(story_text: str, motive: str, story_id: str,
                provider: Optional[ScoringProvider] = None) -> ScoredStory:
    pid = parse_story_id(story_id)
    story = Story(story_id=story_id, subject_id=pid.subject_id, picture=pid.picture,
                  text=story_text or "", word_count=count_words(story_text))
    return (provider or get_provider()).score_story(story, motive)


def score_batch(stories: list[Story], motive: str,
                provider: Optional[ScoringProvider] = None,
                progress: ProgressCb = None) -> list[ScoredStory]:
    return (provider or get_provider()).score_batch(stories, motive, progress=progress)


def estimate_cost(n_stories: int, provider: Optional[str] = None, motives: int = 1) -> dict:
    """Up-front cost/time estimate for a run (brief §9)."""
    from core.runtime import SETTINGS
    name = (provider or SETTINGS.scoring_provider or "fixture").lower()
    units = n_stories * max(1, motives)
    if name == "fixture":
        return {"provider": "fixture", "n_stories": n_stories, "usd": 0.0,
                "calls": 0, "note": "Replaying existing CSV output — no API cost."}
    usd = round(units * config.APPROX_USD_PER_STORY, 2)
    return {"provider": name, "n_stories": n_stories,
            "calls": units * SETTINGS.ensemble_n, "usd": usd,
            "cost_cap_usd": config.COST_CAP_USD,
            "over_cap": bool(config.COST_CAP_USD and usd > config.COST_CAP_USD),
            "note": f"~${config.APPROX_USD_PER_STORY}/story × {units} story-motive(s) "
                    f"× {SETTINGS.ensemble_n} calls."}


__all__ = ["score_story", "score_batch", "get_provider", "estimate_cost",
           "ScoredStory", "Story"]
