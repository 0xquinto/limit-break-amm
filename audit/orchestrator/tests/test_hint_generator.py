"""Tests for hint_generator.py — FP filtering and hint routing."""

import pytest
from audit.orchestrator.hint_generator import _is_rejected, _is_similar_to_known_fp


class TestKeywordRejection:
    def test_exact_keyword_rejected(self):
        assert _is_rejected("validateHandlerOrder sqrtPriceX96==0 overflow") is True

    def test_case_insensitive(self):
        assert _is_rejected("HOOK-001 stale transient storage") is True

    def test_unrelated_text_not_rejected(self):
        assert _is_rejected("novel reentrancy in flash loan callback") is False

    def test_partial_keyword_rejected(self):
        """Substring match: 'height-bucket' appears in text."""
        assert _is_rejected("the height-bucket quantization allows withdrawal") is True

    def test_empty_text_not_rejected(self):
        assert _is_rejected("") is False


class TestSimilarityRejection:
    def test_high_similarity_to_fp_rejected(self):
        """Text very similar to a known FP entry should be rejected."""
        fp_entries = [
            "validateHandlerOrder sqrtPriceX96==0 causes computeRatioX96 overflow",
        ]
        text = "overflow in validateHandlerOrder when sqrtPriceX96 is zero causes ratio computation failure"
        assert _is_similar_to_known_fp(text, fp_entries, threshold=0.4) is True

    def test_low_similarity_not_rejected(self):
        fp_entries = [
            "validateHandlerOrder sqrtPriceX96==0 causes computeRatioX96 overflow",
        ]
        text = "flash loan fee calculation rounding error in dynamic pool"
        assert _is_similar_to_known_fp(text, fp_entries, threshold=0.4) is False

    def test_empty_fp_list_not_rejected(self):
        assert _is_similar_to_known_fp("any text", [], threshold=0.4) is False
