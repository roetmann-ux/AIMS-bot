"""The contract boundary: convert between the engine's wide CSV rows and ``ScoredStory``.

Column families are derived from the motive spec, so Achievement (111 cols), Affiliation (63)
and Power/Influence (98) all parse with the same code. This module also *writes* the wide CSV
(for the combined-scores download and the round-trip reproduction test).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import config
from core.ids import parse_story_id
from core.models import CategoryScore, ScoredStory, count_words
from core.motives import MotiveSpec, get_motive

_BLANKS = {"", "none", "nan", "null", "na"}


def _present(raw, is_act_enum: bool) -> int:
    s = ("" if raw is None else str(raw)).strip()
    if s.lower() in _BLANKS or s in ("0", "0.0"):
        return 0
    if is_act_enum:
        return 1  # any non-blank, non-zero Act value (Act+/Act-/Act?) counts as present
    try:
        return 1 if float(s) >= 0.5 else 0
    except ValueError:
        return 0


def _to_float(raw) -> float:
    try:
        return round(float(raw), 4)
    except (TypeError, ValueError):
        return 0.0


def row_to_scored(row: dict, spec: MotiveSpec) -> ScoredStory:
    story_id = (row.get("StoryID") or "").strip()
    pid = parse_story_id(story_id)
    cats: dict[str, CategoryScore] = {}
    for cat in spec.categories:
        c = cat.code
        raw = row.get(f"ensemble {c}")
        present = _present(raw, cat.is_act_enum)
        value = (str(raw).strip() if cat.is_act_enum and present else
                 ("1" if present else "0"))
        cats[c] = CategoryScore(
            code=c, present=present, value=value,
            confidence=_to_float(row.get(f"ensemble {c} Confidence")),
            explanation=(row.get(f"ensemble {c} Explanation") or "").strip(),
            majority=(row.get(f"ensemble {c} Majority") or None),
            majority_explanation=(row.get(f"ensemble {c} Majority Explanation") or "").strip(),
            dissenting_explanation=(row.get(f"ensemble {c} Dissenting Explanation") or "").strip(),
        )
    gate = cats.get(spec.gate_code)
    try:
        total = int(float(row.get("ensemble Total") or 0))
    except (TypeError, ValueError):
        total = 0
    story_text = (row.get("Story") or "").strip()
    return ScoredStory(
        story_id=story_id, subject_id=pid.subject_id, picture=pid.picture, motive=spec.key,
        gate_present=bool(gate and gate.present), total=total,
        word_count=count_words(story_text), categories=cats,
        provider_votes=(row.get(spec.provider_votes_col) or "").strip(),
        stage_b_trigger=(row.get("Stage B Trigger") or "none").strip(),
        stage_b_override=(row.get("Stage B Override") or "no").strip(),
        story_text=story_text,
        engine_version=f"{config.PROMPT_VERSION}/{config.ENGINE_VERSION}",
        prompt_version=config.PROMPT_VERSION,
    )


def load_fixture(motive: str, path: Path | None = None) -> dict[str, ScoredStory]:
    """Load an engine output CSV into ``{story_id: ScoredStory}``."""
    spec = get_motive(motive)
    path = path or (config.FIXTURES_DIR / spec.fixture)
    out: dict[str, ScoredStory] = {}
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            scored = row_to_scored(row, spec)
            if scored.story_id:
                out[scored.story_id] = scored
    return out


# --------------------------------------------------------------------------- write
def output_columns(spec: MotiveSpec) -> list[str]:
    g = spec.grading_codes()
    cols = ["StoryID"]
    cols += [f"ensemble {c}" for c in g]
    cols += ["ensemble Total", "Expected Total"]
    cols += [f"ensemble {c} Correct" for c in g]
    cols += [f"Expected {c}" for c in g]
    cols += [f"ensemble {c} Confidence" for c in g]
    cols += [f"ensemble {c} Explanation" for c in g]
    cols += [f"ensemble {c} Majority" for c in g]
    cols += [f"ensemble {c} Majority Explanation" for c in g]
    cols += [f"ensemble {c} Dissenting Explanation" for c in g]
    cols += [spec.provider_votes_col, "Stage B Trigger", "Stage B Override", "Story"]
    return cols


def scored_to_row(scored: ScoredStory, spec: MotiveSpec) -> dict:
    row = {"StoryID": scored.story_id, "ensemble Total": scored.total, "Expected Total": "",
           spec.provider_votes_col: scored.provider_votes,
           "Stage B Trigger": scored.stage_b_trigger, "Stage B Override": scored.stage_b_override,
           "Story": scored.story_text}
    for c in spec.grading_codes():
        cs = scored.categories.get(c) or CategoryScore(code=c)
        row[f"ensemble {c}"] = cs.value
        row[f"ensemble {c} Correct"] = ""
        row[f"Expected {c}"] = ""
        row[f"ensemble {c} Confidence"] = cs.confidence
        row[f"ensemble {c} Explanation"] = cs.explanation
        row[f"ensemble {c} Majority"] = cs.majority if cs.majority is not None else cs.value
        row[f"ensemble {c} Majority Explanation"] = cs.majority_explanation
        row[f"ensemble {c} Dissenting Explanation"] = cs.dissenting_explanation
    return row


def write_scores_csv(scored: Iterable[ScoredStory], motive: str, path: Path) -> Path:
    spec = get_motive(motive)
    cols = output_columns(spec)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for s in scored:
            w.writerow(scored_to_row(s, spec))
    return path
