"""RAG exemplar retrieval (Tier 2) — the validated calibration layer.

Uses the founder's vendored retriever (`rag_retriever.py`) over the normalised exemplar libraries
+ embeddings under data/rag/. ACTIVE only when: PROMPT_MODE=v12, USE_RAG=1, an OpenAI key is set,
and the motive's `{motive}_library.parquet` + `{motive}_embeddings.npy` exist (built by
`scripts/build_rag_embeddings.py`). Otherwise returns "" → zero-shot. Affiliation has no library.
"""
from __future__ import annotations

from functools import lru_cache

import config
from core.motives import MotiveSpec

# motives that have an exemplar library (Affiliation has none in the assets -> stays zero-shot)
RAG_MOTIVES = {"achievement", "influence"}


def _paths(motive: str):
    base = config.DATA_DIR / "rag"
    return base / f"{motive}_library.parquet", base / f"{motive}_embeddings.npy"


def rag_ready(motive: str) -> bool:
    from core.runtime import SETTINGS
    if not (config.USE_RAG and SETTINGS.has_openai_key() and motive in RAG_MOTIVES):
        return False
    lib, emb = _paths(motive)
    return lib.exists() and emb.exists()


@lru_cache(maxsize=8)
def _retriever(motive: str):
    from core.runtime import SETTINGS
    from openai import OpenAI

    from .rag_retriever import RAGRetriever
    lib, emb = _paths(motive)
    client = OpenAI(api_key=SETTINGS.openai_api_key)
    return RAGRetriever(str(lib), str(emb), openai_client=client,
                        embedding_model=config.EMBEDDING_MODEL)


def build_exemplars(spec: MotiveSpec, story_text: str, picture: int, k: int | None = None) -> str:
    """Return the formatted 'RETRIEVED SIMILAR EXEMPLARS' block, or '' for zero-shot."""
    if not rag_ready(spec.key):
        return ""
    try:
        from .rag_retriever import build_stage_a_prompt_with_rag
        ex = _retriever(spec.key).retrieve(story_text, picture, k=k or config.RAG_K)
        full = build_stage_a_prompt_with_rag("", "__TEST__", picture, ex)
        return full.split("## TEST STORY TO SCORE")[0]   # exemplar block only
    except Exception:
        return ""   # never let RAG failure abort scoring; degrade to zero-shot
