"""Bag-of-words cosine similarity — zero external dependencies.

Used for fuzzy matching of hints/findings against the FP registry.
Replaces brittle substring matching in hint_generator.py.
"""

import math
import re
from collections import Counter

_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "and", "or", "but", "not", "no", "nor", "so", "yet",
    "if", "then", "else", "when", "where", "how", "what", "which", "who",
    "that", "this", "these", "those", "it", "its",
})


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alpha, remove stopwords and short tokens."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def cosine_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts using bag-of-words TF vectors."""
    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0

    vec_a = Counter(tokens_a)
    vec_b = Counter(tokens_b)

    # Dot product
    all_terms = set(vec_a) | set(vec_b)
    dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in all_terms)

    # Magnitudes
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)
