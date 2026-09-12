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
import math
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

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

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
    "what", "when", "where", "which", "with",
}


def _tokens(text: str) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOP_WORDS]


def _tfidf(tokens: list[str], inverse_document_frequency: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokens)
    return {
        token: (1.0 + math.log(count)) * inverse_document_frequency[token]
        for token, count in counts.items()
        if token in inverse_document_frequency
    }


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(weight * right.get(token, 0.0) for token, weight in left.items())
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


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
        tokenized_passages = [_tokens(text) for text in self._texts]
        document_frequency = Counter(
            token for passage_tokens in tokenized_passages for token in set(passage_tokens)
        )
        passage_count = len(tokenized_passages)
        self._inverse_document_frequency = {
            token: math.log((1 + passage_count) / (1 + frequency)) + 1
            for token, frequency in document_frequency.items()
        }
        self._matrix = [
            _tfidf(passage_tokens, self._inverse_document_frequency)
            for passage_tokens in tokenized_passages
        ]

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

        query_vec = _tfidf(_tokens(expanded_query), self._inverse_document_frequency)
        scores = [_cosine(query_vec, passage_vec) for passage_vec in self._matrix]

        ranked_indices = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)[:top_k]
        results = []
        for idx in ranked_indices:
            score = float(scores[idx])
            if score < min_score:
                continue
            passage = self._passages[idx]
            results.append(RetrievedPassage(score=score, **passage))
        return results

    def source_references(self, passage_ids: set[str]) -> list[dict]:
        """Resolve claim citation IDs to their curated source records."""
        return [
            {key: value for key, value in passage.items() if key in {"id", "title", "section", "url", "text"}}
            for passage in self._passages
            if passage["id"] in passage_ids
        ]


_retriever_singleton: Optional[FDARetriever] = None


def get_retriever() -> FDARetriever:
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = FDARetriever()
    return _retriever_singleton
