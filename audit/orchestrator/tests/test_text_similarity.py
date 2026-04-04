"""Tests for bag-of-words cosine similarity (zero external deps)."""

import pytest
from audit.orchestrator.text_similarity import cosine_similarity, tokenize


class TestTokenize:
    def test_lowercases_and_splits(self):
        assert "hello" in tokenize("Hello World")
        assert "world" in tokenize("Hello World")

    def test_removes_stopwords(self):
        tokens = tokenize("the quick brown fox is a test")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "a" not in tokens
        assert "quick" in tokens

    def test_splits_on_punctuation(self):
        tokens = tokenize("fee-on-transfer, rebasing tokens")
        assert "fee" in tokens
        assert "transfer" in tokens
        assert "rebasing" in tokens

    def test_empty_string(self):
        assert tokenize("") == []

    def test_filters_short_tokens(self):
        tokens = tokenize("a I am so OK no")
        # tokens <= 2 chars should be removed
        assert "a" not in tokens
        assert "am" not in tokens
        assert "so" not in tokens
        assert "no" not in tokens


class TestCosineSimilarity:
    def test_identical_texts(self):
        sim = cosine_similarity("validateHandlerOrder overflow bug",
                                "validateHandlerOrder overflow bug")
        assert sim == pytest.approx(1.0)

    def test_completely_different_texts(self):
        sim = cosine_similarity("rounding error in fee calculation",
                                "reentrancy attack on proxy upgrade")
        assert sim < 0.2

    def test_similar_texts_above_threshold(self):
        sim = cosine_similarity(
            "validateHandlerOrder sqrtPriceX96==0 overflow in computeRatioX96",
            "overflow in validateHandlerOrder when sqrtPriceX96 is zero",
        )
        assert sim > 0.5

    def test_empty_text_returns_zero(self):
        assert cosine_similarity("", "some text") == 0.0
        assert cosine_similarity("some text", "") == 0.0

    def test_partial_overlap(self):
        sim = cosine_similarity(
            "double rounding in CLOBHelper inflates price",
            "CLOBHelper fee calculation has rounding issue",
        )
        assert 0.2 < sim < 0.8
