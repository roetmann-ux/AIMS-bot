"""SQLite persistence (SQLModel). Single inspectable file; ready to move to Postgres later.

Stores subjects, stories, per-story scores, reports, and consent — with a hard data-deletion
path (delete a subject and everything attached to them).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine, delete, select

import config

from .models import ScoredStory, Story


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- tables
class Subject(SQLModel, table=True):
    subject_id: str = Field(primary_key=True)
    name: str = ""
    client: str = ""
    source: str = "bulk"
    is_sample: bool = False
    created_at: datetime = Field(default_factory=_now)


class Consent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subject_id: str = Field(index=True)
    granted: bool = True
    text_version: str = ""
    created_at: datetime = Field(default_factory=_now)


class StoryRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: str = Field(index=True)
    subject_id: str = Field(index=True)
    picture: int = 0
    text: str = ""
    word_count: int = 0
    source: str = "bulk"
    created_at: datetime = Field(default_factory=_now)


class ScoreRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: str = Field(index=True)
    subject_id: str = Field(index=True)
    picture: int = 0
    motive: str = Field(index=True)
    total: int = 0
    gate_present: bool = False
    engine_version: str = ""
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


class ReportRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subject_id: str = Field(index=True)
    html_path: str = ""
    is_sample: bool = False
    created_at: datetime = Field(default_factory=_now)


_engine = create_engine(config.DB_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(_engine)


def session() -> Session:
    return Session(_engine)


# --------------------------------------------------------------------------- writes
def upsert_subject(subject_id: str, name: str = "", client: str = "", source: str = "bulk",
                   is_sample: bool = False) -> None:
    with session() as s:
        sub = s.get(Subject, subject_id)
        if sub is None:
            sub = Subject(subject_id=subject_id)
        sub.name = name or sub.name
        sub.client = client or sub.client
        sub.source = source or sub.source
        sub.is_sample = is_sample or sub.is_sample
        s.add(sub)
        s.commit()


def save_story(story: Story) -> None:
    with session() as s:
        s.add(StoryRow(story_id=story.story_id, subject_id=story.subject_id, picture=story.picture,
                       text=story.text, word_count=story.word_count, source=story.source))
        s.commit()


def save_scored_story(scored: ScoredStory) -> None:
    with session() as s:
        s.add(ScoreRow(story_id=scored.story_id, subject_id=scored.subject_id, picture=scored.picture,
                       motive=scored.motive, total=scored.total, gate_present=scored.gate_present,
                       engine_version=scored.engine_version,
                       payload=scored.model_dump(mode="json")))
        s.commit()


def save_scored_batch(rows: Iterable[ScoredStory]) -> None:
    with session() as s:
        for scored in rows:
            s.add(ScoreRow(story_id=scored.story_id, subject_id=scored.subject_id,
                           picture=scored.picture, motive=scored.motive, total=scored.total,
                           gate_present=scored.gate_present, engine_version=scored.engine_version,
                           payload=scored.model_dump(mode="json")))
        s.commit()


def record_report(subject_id: str, html_path: str, is_sample: bool = False) -> None:
    with session() as s:
        s.add(ReportRow(subject_id=subject_id, html_path=html_path, is_sample=is_sample))
        s.commit()


def record_consent(subject_id: str, granted: bool = True, text_version: str = "v1") -> None:
    with session() as s:
        s.add(Consent(subject_id=subject_id, granted=granted, text_version=text_version))
        s.commit()


# --------------------------------------------------------------------------- reads
def scored_stories_for_subject(subject_id: str, motive: Optional[str] = None) -> list[ScoredStory]:
    with session() as s:
        q = select(ScoreRow).where(ScoreRow.subject_id == subject_id)
        if motive:
            q = q.where(ScoreRow.motive == motive)
        return [ScoredStory.model_validate(r.payload) for r in s.exec(q).all()]


def list_subjects() -> list[Subject]:
    with session() as s:
        return list(s.exec(select(Subject).order_by(Subject.created_at.desc())).all())


def subject_ids_with_scores() -> list[str]:
    with session() as s:
        rows = s.exec(select(ScoreRow.subject_id).distinct()).all()
        return list(rows)


def delete_subject(subject_id: str) -> dict[str, int]:
    """Hard-delete a subject and everything attached (data-deletion path)."""
    counts = {}
    with session() as s:
        for model in (StoryRow, ScoreRow, ReportRow, Consent):
            res = s.exec(select(model).where(model.subject_id == subject_id)).all()
            counts[model.__name__] = len(res)
            s.exec(delete(model).where(model.subject_id == subject_id))
        sub = s.get(Subject, subject_id)
        if sub:
            s.delete(sub)
            counts["Subject"] = 1
        s.commit()
    return counts
