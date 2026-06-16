"""Run the LIVE DeepSeek engine on one subject's 6 stories and emit the 9-call diagnostic tables.

Usage (uses the DeepSeek key saved in Settings / data/settings.json):
    python -m diagnostics.run_live_diagnostic P723 --label run_A --temperature 1.0
    python -m diagnostics.run_live_diagnostic P723 --label run_B --temperature 0.0

Writes diagnostics/aims_raw_call_table_<label>.csv and aims_per_story_aggregate_<label>.csv, and
prints per-motive subject totals + percentiles so two labels can be compared for determinism.
This SPENDS DeepSeek credit (N calls × 6 stories × motives). Stories are pulled from the fixtures.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import config
from aggregate import aggregate_subject
from core.models import Story
from core.motives import all_motives
from scoring_engine.contract import load_fixture

from .build_diagnostic_table import write_tables


def subject_stories(subject_id: str) -> list[Story]:
    fx = load_fixture("achievement")
    rows = sorted((s for s in fx.values() if s.subject_id == subject_id), key=lambda s: s.picture)
    return [Story.make(s.subject_id, s.picture, s.story_text, source="live") for s in rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("subject")
    ap.add_argument("--label", default="run")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--motives", default=",".join(config.ENABLED_MOTIVES))
    args = ap.parse_args()

    if args.temperature is not None:
        config.DEEPSEEK_TEMPERATURE = args.temperature   # override before provider construction
    config.DEEPSEEK_LOG_CALLS = True

    from scoring_engine import get_provider
    provider = get_provider("deepseek")
    motives = [m.strip() for m in args.motives.split(",") if m.strip()]
    stories = subject_stories(args.subject)
    if not stories:
        raise SystemExit(f"No fixture stories for subject {args.subject!r}.")
    print(f"Scoring {len(stories)} stories × {len(motives)} motives at temperature="
          f"{config.DEEPSEEK_TEMPERATURE}, n={provider.n} … (live DeepSeek)")

    scored_all = []
    by_motive = {}
    for motive in motives:
        scored = provider.score_batch(stories, motive)
        by_motive[motive] = scored
        scored_all.extend(scored)
        stamp = scored[0].prompt_version if scored else "(none)"
        print(f"  {motive}: provenance={stamp}  per-story totals = {[s.total for s in scored]}")

    out = Path(__file__).parent
    nr, na = write_tables(scored_all,
                          out / f"aims_raw_call_table_{args.label}.csv",
                          out / f"aims_per_story_aggregate_{args.label}.csv")
    profile = aggregate_subject(args.subject, by_motive, name=args.subject)
    print(f"\nWrote {nr} raw-call rows, {na} per-story rows (label={args.label}).")
    print("Subject-level result:")
    for m in all_motives():
        r = profile.motive(m.key)
        if r and r.enabled:
            print(f"  {m.display_name:12s} raw={r.raw_score:.0f} pct={r.percentile} ({r.band})")


if __name__ == "__main__":
    main()
