"""Provider interface. A provider turns a ``Story`` into a ``ScoredStory`` for one motive."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

from core.models import ScoredStory, Story

ProgressCb = Optional[Callable[[int, int], None]]


class ScoringProvider(ABC):
    name: str = "base"

    @abstractmethod
    def score_story(self, story: Story, motive: str) -> ScoredStory:
        ...

    def score_batch(self, stories: list[Story], motive: str,
                    progress: ProgressCb = None) -> list[ScoredStory]:
        out: list[ScoredStory] = []
        n = len(stories)
        for i, story in enumerate(stories):
            try:
                out.append(self.score_story(story, motive))
            except Exception as exc:  # partial-failure handling: never abort a whole batch
                empty = ScoredStory.empty(story, motive)
                empty.stage_b_trigger = f"error: {type(exc).__name__}"
                out.append(empty)
            if progress:
                progress(i + 1, n)
        return out
