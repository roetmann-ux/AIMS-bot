"""Build the 9-call diagnostic tables from per-call logs (Phase 2).

Two outputs, exactly as specified:
  * raw call table  — one row per (story × motive × call 1..N), with the verbatim API response.
  * per-story table — one row per (story × motive), pivoting Call1..N totals + consensus stats.

Input is a list of ScoredStory carrying `.call_logs` (populated by the live DeepSeek provider when
AIMS_DEEPSEEK_LOG_CALLS=1). The fixture engine has no per-call logs, so this only yields meaningful
variance on live runs — which is the point: it isolates API-layer vs aggregation-layer instability.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from core.models import ScoredStory
from core.motives import get_motive

MOTIVE_TAG = {"achievement": "Ach", "affiliation": "Aff", "influence": "Pow"}

RAW_COLS = ["SubjectID", "StoryID", "Picture#", "MotiveSystem", "CallIndex",
            "RawAPIResponse", "ParsedSubcategoryCodes", "StoryLevelTotal",
            "ModelTemperature", "ModelTopP", "ModelSeed", "RequestTimestamp",
            "ResponseHash", "Error"]
AGG_COLS = ["SubjectID", "StoryID", "MotiveSystem",
            "Call1Total", "Call2Total", "Call3Total", "Call4Total", "Call5Total",
            "Call6Total", "Call7Total", "Call8Total", "Call9Total",
            "MeanCallTotal", "MedianCallTotal", "ModeCallTotal",
            "MajorityVoteSubcategoryProfile", "FinalStoryScore",
            "CallToCallStdDev", "CallToCallRange", "ConsensusRate", "ValidCalls", "FailedCalls"]


def raw_rows(scored: list[ScoredStory]) -> list[dict]:
    rows = []
    for s in scored:
        tag = MOTIVE_TAG.get(s.motive, s.motive)
        for log in s.call_logs:
            rows.append({
                "SubjectID": s.subject_id, "StoryID": s.story_id, "Picture#": s.picture,
                "MotiveSystem": tag, "CallIndex": log.get("call_index"),
                "RawAPIResponse": log.get("raw_response", ""),
                "ParsedSubcategoryCodes": log.get("parsed_codes", ""),
                "StoryLevelTotal": log.get("story_total"),
                "ModelTemperature": log.get("temperature"), "ModelTopP": log.get("top_p"),
                "ModelSeed": log.get("seed"), "RequestTimestamp": log.get("timestamp"),
                "ResponseHash": log.get("response_hash", ""), "Error": log.get("error", "")})
    return rows


def _consensus_rate(s: ScoredStory) -> float:
    """Mean fraction of valid calls that agree with the final coding on each subcategory + gate."""
    spec = get_motive(s.motive)
    parsed = [json.loads(l["parsed_codes"]) for l in s.call_logs
              if l.get("parsed_codes")]
    if not parsed:
        return 0.0
    codes = [spec.gate_code] + spec.subcat_codes()
    agreements = []
    for code in codes:
        final = 1 if (s.categories.get(code) and s.categories[code].present) else 0
        votes = []
        for p in parsed:
            v = p.get(code)
            if isinstance(v, str):          # Act enum
                votes.append(1 if v not in ("", "null", "0", None) else 0)
            else:
                try:
                    votes.append(1 if int(v or 0) == 1 else 0)
                except (TypeError, ValueError):
                    votes.append(0)
        if votes:
            agreements.append(sum(1 for v in votes if v == final) / len(votes))
    return round(statistics.mean(agreements), 3) if agreements else 0.0


def agg_rows(scored: list[ScoredStory]) -> list[dict]:
    rows = []
    for s in scored:
        tag = MOTIVE_TAG.get(s.motive, s.motive)
        totals = [l.get("story_total") for l in s.call_logs if l.get("story_total") is not None]
        failed = sum(1 for l in s.call_logs if l.get("error"))
        row = {"SubjectID": s.subject_id, "StoryID": s.story_id, "MotiveSystem": tag,
               "FinalStoryScore": s.total, "ValidCalls": len(totals), "FailedCalls": failed,
               "MajorityVoteSubcategoryProfile": "+".join(s.present_codes()) or "(none)"}
        for i in range(9):
            row[f"Call{i + 1}Total"] = totals[i] if i < len(totals) else ""
        if totals:
            row["MeanCallTotal"] = round(statistics.mean(totals), 2)
            row["MedianCallTotal"] = statistics.median(totals)
            row["ModeCallTotal"] = statistics.mode(totals)
            row["CallToCallStdDev"] = round(statistics.pstdev(totals), 3) if len(totals) > 1 else 0.0
            row["CallToCallRange"] = max(totals) - min(totals)
        else:
            row.update({"MeanCallTotal": "", "MedianCallTotal": "", "ModeCallTotal": "",
                        "CallToCallStdDev": "", "CallToCallRange": ""})
        row["ConsensusRate"] = _consensus_rate(s)
        rows.append(row)
    return rows


def write_tables(scored: list[ScoredStory], raw_path: Path, agg_path: Path) -> tuple[int, int]:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    r = raw_rows(scored)
    a = agg_rows(scored)
    with open(raw_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RAW_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(r)
    with open(agg_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=AGG_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(a)
    return len(r), len(a)


def scored_from_db(subject_id: str) -> list[ScoredStory]:
    from core.db import scored_stories_for_subject
    from core.motives import all_motives
    out = []
    for m in all_motives():
        out.extend(scored_stories_for_subject(subject_id, m.key))
    return out
