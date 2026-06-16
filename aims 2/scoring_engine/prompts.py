"""Prompt construction for the live engine.

Two modes (config.PROMPT_MODE / Settings):
  * "v12"       — the founder's VERBATIM V12/V11/V2 notebook rubric (scoring_engine/prompts_v12/).
                  This is the validated system; the live engine sends it exactly.
  * "condensed" — a short rubric generated from core/motives.py (fallback / cheap).

The user message uses the notebook's exact wrapper ("## TEST STORY TO SCORE ... Picture N:"), with
retrieved RAG exemplars prepended when available (see rag.py). Falls back to condensed if the
verbatim file is missing for a motive.
"""
from __future__ import annotations

import json

from core.motives import MotiveSpec

from . import prompts_v12

_PREAMBLE = (
    "You are a PhD psychologist expert in David McClelland's theory of implicit motives and in "
    "Charles P. Smith's *Motivation and Personality: Handbook of Thematic Content Analysis* "
    "(1992). You score a single Picture Story Exercise (PSE/TAT) story for the {name} motive "
    "using the standard content-analysis system. Be rigorous and conservative: score a category "
    "only on clear textual evidence.")


def _condensed_system(spec: MotiveSpec) -> str:
    gate = spec.by_code(spec.gate_code)
    lines = [_PREAMBLE.format(name=spec.display_name), ""]
    lines.append(f"STEP 1 — GATE. Decide {spec.gate_code} ({gate.label}): {gate.definition}. "
                 f"{spec.display_name} imagery is the gate — if it is absent, the story scores "
                 f"0 on every subcategory.")
    lines.append("")
    lines.append("STEP 2 — SUBCATEGORIES (score each 0/1 only if the gate is present):")
    for c in spec.categories:
        if c.kind == "gate":
            continue
        if c.is_act_enum:
            lines.append(f"  - {c.code} ({c.label}): {c.definition}. "
                         f"Return \"Act+\", \"Act-\", \"Act?\" if present, else null.")
        elif c.kind == "imagery":
            lines.append(f"  - {c.code} ({c.label}): {c.definition} (mutually exclusive with the gate).")
        else:
            lines.append(f"  - {c.code} ({c.label}): {c.definition}.")
    schema = {spec.gate_code: "0 or 1"}
    for c in spec.categories:
        if c.code == spec.gate_code:
            continue
        schema[c.code] = '"Act+"|"Act-"|"Act?"|null' if c.is_act_enum else "0 or 1"
    schema["explanation"] = {c.code: "one-sentence justification" for c in spec.categories
                             if c.code != "TI"}
    lines += ["", "Return ONLY a JSON object of exactly this shape:", json.dumps(schema, indent=2)]
    return "\n".join(lines)


def build_system_prompt(spec: MotiveSpec, mode: str | None = None) -> str:
    if mode is None:
        from core.runtime import SETTINGS
        mode = SETTINGS.prompt_mode
    if mode == "v12" and prompts_v12.has_v12(spec.key):
        return prompts_v12.load_stage_a(spec.key)
    return _condensed_system(spec)


def build_user_prompt(spec: MotiveSpec, story_text: str, picture: int, exemplars: str = "") -> str:
    """Notebook-faithful user message: optional RAG exemplar block + the test story block."""
    test_block = f"\n## TEST STORY TO SCORE\n\nPicture {picture}:\n{story_text.strip()}\n"
    return (exemplars or "") + test_block


def system_mode(spec: MotiveSpec, mode: str | None = None) -> str:
    """Short tag of which rubric was used, for provenance stamping."""
    if mode is None:
        from core.runtime import SETTINGS
        mode = SETTINGS.prompt_mode
    return "V12" if (mode == "v12" and prompts_v12.has_v12(spec.key)) else "AIMS-condensed"
