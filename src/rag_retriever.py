"""
Step 7: FDA retrieval layer.

Deliberately local and deterministic: TF-IDF cosine similarity over a small
curated corpus, not a hosted vector database and not an embedding API call.
This keeps retrieval reproducible (the same query always returns the same
ranking), avoids a second network dependency during the demo, and matches
the roadmap's instruction to avoid a hosted vector DB during the prototype.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CORPUS_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "fda_sources" / "corpus.json"

# Keeps retrieval scoped to the selected goal so a sodium question doesn't
# pull back fiber guidance just because the vocabulary overlaps.
GOAL_KEYWORDS = {
    "lower_added_sugar": ["sugar", "sugars", "sweetener", "syrup", "honey"],
    "lower_sodium": ["sodium", "salt"],
    "higher_fibre": ["fiber", "fibre", "bowel"],
    "general_understanding": [],
    "product_comparison": [],
}


class RetrievedPassage(BaseModel):
    id: str
    title: str
    section: str
    url: str
    text: str
    score: float


class FDARetriever:
    def __init__(self, corpus_path: Path = CORPUS_PATH):
        self.corpus_path = corpus_path
        self._passages: list[dict] = json.loads(corpus_path.read_text())
        self._texts = [p["text"] for p in self._passages]
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = self._vectorizer.fit_transform(self._texts)

    def retrieve(
        self,
        query: str,
        goal: Optional[str] = None,
        top_k: int = 3,
        min_score: float = 0.05,
    ) -> list[RetrievedPassage]:
        expanded_query = query
        if goal and GOAL_KEYWORDS.get(goal):
            expanded_query = query + " " + " ".join(GOAL_KEYWORDS[goal])

        query_vec = self._vectorizer.transform([expanded_query])
        scores = cosine_similarity(query_vec, self._matrix).flatten()

        ranked_indices = scores.argsort()[::-1][:top_k]
        results = []
        for idx in ranked_indices:
            score = float(scores[idx])
            if score < min_score:
                continue
            passage = self._passages[idx]
            results.append(RetrievedPassage(score=score, **passage))
        return results


_retriever_singleton: Optional[FDARetriever] = None


def get_retriever() -> FDARetriever:
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = FDARetriever()
    return _retriever_singleton
