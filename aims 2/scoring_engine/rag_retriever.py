"""RAG retriever for AI motive scoring.

Drop this file into your Colab notebook's working directory and import:
    from rag_retriever import RAGRetriever

Then use it inside the V11 notebook's main scoring loop:
    retriever = RAGRetriever(
        library_path='/content/drive/MyDrive/Joel\\'s Lab/RAG/achievement_rag_library.parquet',
        embeddings_path='/content/drive/MyDrive/Joel\\'s Lab/RAG/achievement_rag_embeddings.npy',
        openai_client=client,
    )
    retrieved = retriever.retrieve(test_story_text, test_picture, k=6)
    # `retrieved` is a list of dicts; pass to the prompt builder
"""

import numpy as np
import pandas as pd
from openai import OpenAI
from typing import List, Dict, Optional


class RAGRetriever:
    """Retrieves similar exemplars from a pre-embedded library."""

    def __init__(
        self,
        library_path: str,
        embeddings_path: str,
        openai_client: Optional[OpenAI] = None,
        embedding_model: str = 'text-embedding-3-large',
        picture_bonus: float = 0.15,
    ):
        """
        Args:
          library_path: parquet file with story_text, picture_number, scores, etc.
          embeddings_path: .npy file with shape (n_exemplars, embedding_dim)
          openai_client: OpenAI client instance. If None, creates a new one.
          embedding_model: which OpenAI embedding model to use for queries
          picture_bonus: how much to boost similarity for same-picture exemplars (0.0 = disabled)
        """
        self.library = pd.read_parquet(library_path).reset_index(drop=True)
        self.embeddings = np.load(embeddings_path).astype(np.float32)
        assert len(self.library) == self.embeddings.shape[0], (
            f"Library size {len(self.library)} != embeddings shape {self.embeddings.shape[0]}"
        )

        # Pre-normalize for cosine
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.embeddings_norm = self.embeddings / norms

        # Same-picture mask helpers
        self.picture_array = self.library['picture_number'].values

        self.client = openai_client or OpenAI()
        self.embedding_model = embedding_model
        self.picture_bonus = picture_bonus

    def _embed_query(self, text: str) -> np.ndarray:
        """Embed a single query story."""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=[text],
        )
        emb = np.array(response.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        return emb / (norm if norm > 0 else 1)

    def retrieve(
        self,
        story_text: str,
        picture: int,
        k: int = 6,
        exclude_ai_score: Optional[int] = None,
        diversity_mix: bool = True,
    ) -> List[Dict]:
        """
        Retrieve top-K most similar exemplars to (story_text, picture).

        Args:
          story_text: the test story to score
          picture: 1-6, the picture number for this story
          k: number of exemplars to return
          exclude_ai_score: if set, filter out exemplars with this ai_score (e.g., to force
                            both 0 and 1 to appear)
          diversity_mix: if True, ensure at least 1 AI=1 and 1 AI=0 exemplar in returned set

        Returns:
          List of dicts with keys: story_text, picture_number, ai_score, total,
          subcat_summary, scoring_rationale, source, similarity
        """
        query_emb = self._embed_query(story_text)

        # Cosine similarities to all library exemplars
        sims = self.embeddings_norm @ query_emb  # (N,)

        # Picture-match bonus
        if self.picture_bonus > 0:
            same_pic = (self.picture_array == picture).astype(np.float32)
            sims = sims + self.picture_bonus * same_pic

        # Optional exclude
        if exclude_ai_score is not None:
            mask = self.library['ai_score'].values != exclude_ai_score
            sims = np.where(mask, sims, -np.inf)

        if not diversity_mix:
            top_idx = np.argsort(-sims)[:k]
        else:
            # Get top exemplars but enforce at least 1 of each AI class
            top_idx = list(np.argsort(-sims)[:k])
            ai_classes = [self.library.iloc[i]['ai_score'] for i in top_idx]
            if 0 not in ai_classes:
                # Find best AI=0 exemplar not yet selected
                ai0_pool = np.where((self.library['ai_score'].values == 0))[0]
                ai0_sims = sims[ai0_pool]
                best_ai0 = ai0_pool[np.argmax(ai0_sims)]
                top_idx[-1] = best_ai0
            elif 1 not in ai_classes:
                ai1_pool = np.where((self.library['ai_score'].values == 1))[0]
                ai1_sims = sims[ai1_pool]
                best_ai1 = ai1_pool[np.argmax(ai1_sims)]
                top_idx[-1] = best_ai1

        # Build result list
        results = []
        for idx in top_idx:
            row = self.library.iloc[idx].to_dict()
            row['similarity'] = float(sims[idx])
            # Drop fields we don't need in the prompt
            row.pop('word_count', None)
            row.pop('story_id', None)
            results.append(row)
        return results


def build_stage_a_prompt_with_rag(
    base_instructions: str,
    test_story: str,
    test_picture: int,
    retrieved_exemplars: List[Dict],
) -> str:
    """
    Build a Stage A prompt that injects retrieved exemplars.
    Drop this in alongside the existing V9 prompt-builder.
    """
    exemplar_block = (
        "\n\n## RETRIEVED SIMILAR EXEMPLARS (Expert-Scored)\n\n"
        "Below are several stories from the McClelland scoring tradition (Smith 1992 plus calibrated cohort exemplars) that are most similar to the test story. Study how the experts handled them. Apply the same scoring logic to the test story below — but make your own judgment; do NOT simply copy a retrieved exemplar's verdict.\n\n"
    )
    for i, ex in enumerate(retrieved_exemplars, start=1):
        exemplar_block += f"--- EXEMPLAR {i} (Picture {ex['picture_number']}, source: {ex['source']}) ---\n"
        exemplar_block += f"STORY: {ex['story_text']}\n"
        exemplar_block += f"EXPERT SCORE: AI={ex['ai_score']}, Total={ex['total']}"
        if ex.get('subcat_summary') and ex['subcat_summary'] != 'none':
            exemplar_block += f", subcategories: {ex['subcat_summary']}"
        exemplar_block += "\n"
        if ex.get('scoring_rationale'):
            exemplar_block += f"RATIONALE: {ex['scoring_rationale']}\n"
        exemplar_block += "\n"

    test_block = f"\n## TEST STORY TO SCORE\n\nPicture {test_picture}:\n{test_story}\n"

    return base_instructions + exemplar_block + test_block
