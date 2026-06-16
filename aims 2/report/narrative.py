"""Rules-based narrative layer.

Turns a MotiveResult (percentile band + expression rollup) into the report's prose. Every claim
is keyed off the scores — consistent and defensible, never invented. An optional LLM polish pass
could rewrite these strings, but the factual content originates here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.models import MotiveResult
from core.motives import MotiveSpec

# band -> framing words
_ADJ = {"significantly high": "Strong", "high": "Clear", "moderate": "Meaningful",
        "low": "Low or limited", "significantly low": "Little or no"}
_HEADLINE = {"significantly high": "significantly above average", "high": "above average",
             "moderate": "around the average", "low": "below average",
             "significantly low": "significantly below average"}
_ENERGY = {"significantly high": "strongly energized", "high": "energized",
           "moderate": "meaningfully engaged", "low": "not strongly energized",
           "significantly low": "largely not energized"}

# three facets per motive (read as "<Adj> <facet>")
_FACETS = {
    "achievement": ["desire to improve how things are done, through efficiency or innovation",
                    "drive to measure performance and to set, meet, and beat goals",
                    "investment in longer-term learning and mastery"],
    "affiliation": ["interest in maintaining warm, friendly, personal relationships",
                    "energy around group membership and belonging to a larger whole",
                    "concern for protecting personal relationships, even at a cost to performance"],
    "influence":   ["engagement in having an impact on individuals, groups, or the world",
                    "energy around influencing the behaviour of others",
                    "ambition regarding reputation, standing, or position"],
}
_ESSENCE = {"achievement": "the desire to make things better, through greater efficiency or innovation",
            "affiliation": "the desire to build and maintain warm, personal relationships",
            "influence": "the desire to have an impact on, and influence over, others"}

# per content-category implication (intensity prefix is added from the evidence level)
_IMPLICATION = {
    "Need": "an explicit, conscious commitment to specific goals",
    "Act": "an action-oriented approach — a readiness to jump in and act",
    "GA+": "an optimistic outlook that anticipates success",
    "SA": "an optimistic outlook that anticipates a positive outcome",
    "GA-": "a watchfulness about the possibility of failure",
    "BP": "an awareness of personal obstacles, which may be internalised",
    "BW": "an awareness of external obstacles and likely resistance",
    "Bw": "an awareness of external obstacles and likely resistance",
    "Help": "a recognition of the enablers and support needed to reach the goal",
    "F+": "strong positive emotion tied to success — an emotional commitment to it",
    "F-": "strong negative emotion around the prospect of failure",
    "Pa+": "a concern with prestige and standing",
    "Pa-": "a sensitivity to loss of standing or to being made to feel weak",
    "Fa": "some conflict or ambivalence about exercising influence",
    "Eff": "a focus on producing a tangible effect or impact on others",
    "TH": "a motive that dominates the imaginative content of the stories",
}
_EV_PREFIX = {"Very Strong": "Very strong, repeated evidence of",
              "Strong": "Strong, clear evidence of", "Some": "Some evidence of"}


@dataclass
class Narrative:
    summary_lead: str
    summary_bullets: list[str] = field(default_factory=list)
    overall_headline: str = ""
    overall_lead: str = ""
    overall_positives: list[str] = field(default_factory=list)
    overall_challenges: list[str] = field(default_factory=list)
    expressions_lead: str = ""
    expressions_points: list[str] = field(default_factory=list)
    similar_people: list[str] = field(default_factory=list)


def _first_name(name: str) -> str:
    return (name or "This person").split()[0]


def build_narrative(name: str, spec: MotiveSpec, result: MotiveResult) -> Narrative:
    who = _first_name(name)
    band = result.band or "moderate"
    adj = _ADJ.get(band, "Meaningful")
    facets = _FACETS[spec.key]

    nar = Narrative(summary_lead=f"{who} shows {band} levels of {spec.display_name}, indicating:")
    nar.summary_bullets = [f"{adj} {f}" for f in facets]

    nar.overall_headline = _HEADLINE.get(band, "around the average")
    nar.overall_lead = (f"{spec.display_name} motive is {nar.overall_headline}. {who}’s score "
                        f"indicates a person who is {_ENERGY.get(band, 'engaged')} by "
                        f"{_ESSENCE[spec.key]}.")

    # Overall positives / challenges from fired expressions, strongest first.
    fired = sorted([e for e in result.expressions if e.count > 0],
                   key=lambda e: e.count, reverse=True)
    for e in fired:
        impl = _IMPLICATION.get(e.code)
        if not impl:
            continue
        prefix = _EV_PREFIX.get(e.evidence, "Some evidence of")
        line = f"{prefix} {impl}."
        (nar.overall_challenges if e.polarity == "negative" else nar.overall_positives).append(line)

    if not fired:
        nar.expressions_lead = (f"{who} produced limited scoreable {spec.display_name} content, "
                                f"so expression patterns are minimal.")
    else:
        top = [e.label.lower() for e in fired[:3]]
        nar.expressions_lead = (f"{who}’s stories primarily express "
                                f"{_join(top)}.")
        nar.expressions_points = [
            f"{_EV_PREFIX.get(e.evidence, 'Some evidence of')} {_IMPLICATION.get(e.code, e.label.lower())}."
            for e in fired]

    # "People with similar categories" — pattern read from dominant polarity.
    pos = sum(1 for e in fired if e.polarity != "negative")
    neg = sum(1 for e in fired if e.polarity == "negative")
    if fired:
        if pos >= max(1, neg):
            nar.similar_people = [
                "People with similar profiles tend to take an energetic, forward-leaning approach.",
                "They may underestimate obstacles, or overlook the enablers who could help them.",
                "They can favour a “ready, fire, aim” style — acting before fully scoping the situation."]
        else:
            nar.similar_people = [
                "People with similar profiles tend to be cautious and obstacle-aware.",
                "They weigh risks before committing, which can slow decisive action.",
                "They benefit from encouragement to act despite uncertainty."]
    return nar


_PRIMARY = {
    "achievement": "meeting and beating goals, and making improvements in systems — for example "
                   "in sales, finance, engineering, entrepreneurship, or systems improvement",
    "affiliation": "building, maintaining, and protecting warm personal relationships, and by "
                   "collaboration and a sense of belonging",
    "influence": "having an impact on people and outcomes — leading, persuading, and shaping "
                 "decisions and reputation",
}
_SECONDARY = {
    "achievement": "a drive to raise the standard and measure whether things are getting better",
    "affiliation": "more awareness of, and care for, the people affected by their decisions",
    "influence": "more willingness to engage others and exert influence to make things happen",
}


def profile_implications(name: str, profile) -> list[str]:
    """One synthesised 'what this profile suggests' block, keyed off the motive ranking."""
    who = _first_name(name)
    enabled = [(k, r) for k, r in profile.motives.items()
               if r.enabled and r.percentile is not None]
    if not enabled:
        return []
    ranked = sorted(enabled, key=lambda kr: kr[1].percentile, reverse=True)
    primary_key, primary = ranked[0]
    out = [f"This profile suggests someone who is primarily energized by {_PRIMARY[primary_key]}."]
    for key, r in ranked[1:]:
        if r.band in ("high", "significantly high"):
            out.append(f"Their {r.band} {profile.motives[key].display_name} also suggests "
                       f"{_SECONDARY[key]}.")
    return out[:3]


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f", and {items[-1]}"
