"""Rebuild the RAG exemplar embeddings the notebooks expect (the .npy lives in the founder's
Google Drive and isn't in the repo). Normalises each source library's gate column to `ai_score`,
then embeds every exemplar story with text-embedding-3-large.

Run from the aims/ folder once an OpenAI key is set in Settings:
    python -m scripts.build_rag_embeddings                 # achievement + influence
    python -m scripts.build_rag_embeddings achievement     # one motive

Writes data/rag/{motive}_library.parquet + {motive}_embeddings.npy. Affiliation has no source
library, so it is skipped (Affiliation stays zero-shot until its library is built).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import config
from core.runtime import SETTINGS

_GATE_ALIASES = ["ai_score", "powim_score", "affim_score", "powim", "affim", "pow_score"]
_DEFAULTS = {"total": 0, "subcat_summary": "", "scoring_rationale": "", "source": "library",
             "picture_number": 0, "story_text": ""}


def build(motive: str) -> tuple[int, tuple]:
    base = config.DATA_DIR / "rag"
    src = base / f"{motive}_source.parquet"
    if not src.exists():
        print(f"  {motive}: no source library ({src.name}) — skipped (stays zero-shot).")
        return 0, ()
    df = pd.read_parquet(src).reset_index(drop=True)
    if "ai_score" not in df.columns:                       # unify the gate column name
        for g in _GATE_ALIASES:
            if g in df.columns:
                df["ai_score"] = df[g]
                break
    for col, default in _DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
    df.to_parquet(base / f"{motive}_library.parquet")

    from openai import OpenAI
    client = OpenAI(api_key=SETTINGS.openai_api_key)
    texts = df["story_text"].astype(str).tolist()
    embs: list = []
    for i in range(0, len(texts), 64):
        resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=texts[i:i + 64])
        embs.extend(d.embedding for d in resp.data)
    arr = np.asarray(embs, dtype=np.float32)
    np.save(base / f"{motive}_embeddings.npy", arr)
    return len(df), arr.shape


def main() -> None:
    if not SETTINGS.has_openai_key():
        raise SystemExit("No OpenAI key set. Add it on the Settings page first.")
    motives = sys.argv[1:] or ["achievement", "influence"]
    for m in motives:
        n, shape = build(m)
        if n:
            print(f"  {m}: embedded {n} exemplars -> {shape}")


if __name__ == "__main__":
    main()
