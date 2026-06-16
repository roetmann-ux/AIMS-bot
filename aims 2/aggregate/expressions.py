"""Expression rollup: how often each content category fired across a subject's protocol.

This drives the report's "Expressions" page (which categories dominate) and the evidence table
(Very Strong / Strong / Some / None), straight from the per-story category presence.
"""
from __future__ import annotations

from core.models import ExpressionItem, ScoredStory
from core.motives import MotiveSpec, evidence_label


def rollup(spec: MotiveSpec, stories: list[ScoredStory]) -> list[ExpressionItem]:
    items: list[ExpressionItem] = []
    for cat in spec.expression_categories():
        count = sum(1 for s in stories
                    if (cs := s.categories.get(cat.code)) is not None and cs.present)
        items.append(ExpressionItem(
            code=cat.code, label=cat.label, definition=cat.definition,
            polarity=cat.polarity, count=count, evidence=evidence_label(count)))
    return items


def evidence_quotes(spec: MotiveSpec, stories: list[ScoredStory], limit: int = 6) -> list[str]:
    """Pull the engine's own explanations as supporting evidence for the appendix."""
    quotes: list[str] = []
    for s in stories:
        if not s.gate_present:
            continue
        gate = s.categories.get(spec.gate_code)
        expl = (gate.explanation if gate else "") or ""
        if expl:
            quotes.append(f"PIC{s.picture}: {expl}")
    return quotes[:limit]


def dominant_expressions(items: list[ExpressionItem]) -> list[ExpressionItem]:
    """Categories that fired meaningfully, strongest first — feeds the narrative."""
    fired = [i for i in items if i.count > 0]
    return sorted(fired, key=lambda i: i.count, reverse=True)
