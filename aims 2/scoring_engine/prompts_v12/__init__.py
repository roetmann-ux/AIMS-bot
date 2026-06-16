"""Loader for the founder's VERBATIM V12/V11/V2 notebook prompts.

The .txt files in this folder are extracted character-for-character from
`Achievement_Inference_V12_W1W2.ipynb` (stage_a_instructions / stage_b_instructions) and the Power
V11 / Affiliation V2 notebooks. Loading them here means the live engine sends the *exact* validated
rubric — verifiable via the prompt hash stamped on every score.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache(maxsize=16)
def _read(name: str) -> str:
    p = _DIR / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def has_v12(motive: str) -> bool:
    return bool(_read(f"{motive}_stage_a.txt"))


def load_stage_a(motive: str) -> str:
    return _read(f"{motive}_stage_a.txt")


def load_stage_b(motive: str) -> str:
    return _read(f"{motive}_stage_b.txt")
