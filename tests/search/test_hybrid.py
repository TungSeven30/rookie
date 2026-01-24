"""Tests for hybrid search with RRF fusion."""

import pytest

from src.search.hybrid import (
    RRF_K,
    SearchResult,
    compute_rrf_scores,
)


class TestComputeRrfScores:
    """Tests for RRF score computation."""

    def test_semantic_only_results(self) -> None:
        """Results from semantic search only should have correct scores."""
        semantic = [(1, 1), (2, 2), (3, 3)]
        keyword: list[tuple[int, int]] = []

        scores = compute_rrf_scores(semantic, keyword)

        assert len(scores) == 3
        # Score for rank 1: 1/(60+1) = 0.01639...
        assert abs(scores[1][0] - 1 / (RRF_K + 1)) < 1e-10
        # Score for rank 2: 1/(60+2) = 0.01613...
        assert abs(scores[2][0] - 1 / (RRF_K + 2)) < 1e-10
        # Semantic rank recorded, keyword rank is None
        assert scores[1][1] == 1
        assert scores[1][2] is None

    def test_keyword_only_results(self) -> None:
        """Results from keyword search only should have correct scores."""
        semantic: list[tuple[int, int]] = []
        keyword = [(1, 1), (2, 2)]

        scores = compute_rrf_scores(semantic, keyword)

        assert len(scores) == 2
        assert abs(scores[1][0] - 1 / (RRF_K + 1)) < 1e-10
        # Keyword rank recorded, semantic rank is None
        assert scores[1][1] is None
        assert scores[1][2] == 1

    def test_combined_results_sum_scores(self) -> None:
        """Doc appearing in both should have summed RRF scores."""
        # Doc 2 appears in both: semantic rank 2, keyword rank 1
        semantic = [(1, 1), (2, 2)]
        keyword = [(2, 1), (3, 2)]

        scores = compute_rrf_scores(semantic, keyword)

        assert len(scores) == 3
        # Doc 2: 1/(60+2) + 1/(60+1) = combined score
        expected_score_2 = 1 / (RRF_K + 2) + 1 / (RRF_K + 1)
        assert abs(scores[2][0] - expected_score_2) < 1e-10
        # Doc 2 has both ranks
        assert scores[2][1] == 2  # semantic rank
        assert scores[2][2] == 1  # keyword rank

    def test_empty_inputs(self) -> None:
        """Empty inputs should return empty dict."""
        scores = compute_rrf_scores([], [])
        assert scores == {}

    def test_custom_k_value(self) -> None:
        """Custom k value should affect scores."""
        semantic = [(1, 1)]
        keyword: list[tuple[int, int]] = []

        scores_default = compute_rrf_scores(semantic, keyword, k=60)
        scores_custom = compute_rrf_scores(semantic, keyword, k=30)

        # With smaller k, rank has more impact
        assert scores_custom[1][0] > scores_default[1][0]

    def test_rrf_k_constant_is_60(self) -> None:
        """RRF_K should be 60 (standard value)."""
        assert RRF_K == 60

    def test_higher_rank_means_lower_score(self) -> None:
        """Higher rank numbers should produce lower RRF scores."""
        semantic = [(1, 1), (2, 5), (3, 10)]
        keyword: list[tuple[int, int]] = []

        scores = compute_rrf_scores(semantic, keyword)

        # Rank 1 > Rank 5 > Rank 10 in score
        assert scores[1][0] > scores[2][0] > scores[3][0]


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_source_info_semantic_only(self) -> None:
        """source_info should show semantic when only semantic rank exists."""
        result = SearchResult(
            id=1,
            skill_file_id=10,
            skill_name="test_skill",
            chunk_text="chunk content",
            semantic_rank=3,
            keyword_rank=None,
            hybrid_score=0.5,
        )
        assert result.source_info == "semantic:#3"

    def test_source_info_keyword_only(self) -> None:
        """source_info should show keyword when only keyword rank exists."""
        result = SearchResult(
            id=1,
            skill_file_id=10,
            skill_name="test_skill",
            chunk_text="chunk content",
            semantic_rank=None,
            keyword_rank=5,
            hybrid_score=0.3,
        )
        assert result.source_info == "keyword:#5"

    def test_source_info_both_ranks(self) -> None:
        """source_info should show both when both ranks exist."""
        result = SearchResult(
            id=1,
            skill_file_id=10,
            skill_name="test_skill",
            chunk_text="chunk content",
            semantic_rank=2,
            keyword_rank=4,
            hybrid_score=0.8,
        )
        assert result.source_info == "semantic:#2, keyword:#4"

    def test_source_info_no_ranks(self) -> None:
        """source_info should show 'unknown' when no ranks exist."""
        result = SearchResult(
            id=1,
            skill_file_id=10,
            skill_name="test_skill",
            chunk_text="chunk content",
            semantic_rank=None,
            keyword_rank=None,
            hybrid_score=0.0,
        )
        assert result.source_info == "unknown"

    def test_dataclass_fields(self) -> None:
        """SearchResult should have all expected fields."""
        result = SearchResult(
            id=123,
            skill_file_id=456,
            skill_name="my_skill",
            chunk_text="some text",
            semantic_rank=1,
            keyword_rank=2,
            hybrid_score=0.75,
        )
        assert result.id == 123
        assert result.skill_file_id == 456
        assert result.skill_name == "my_skill"
        assert result.chunk_text == "some text"
        assert result.semantic_rank == 1
        assert result.keyword_rank == 2
        assert result.hybrid_score == 0.75


class TestHybridSearch:
    """Tests for hybrid search behavior (unit tests without DB)."""

    def test_rrf_scores_sorted_descending(self) -> None:
        """Higher RRF scores should sort first."""
        # Simulate results and check sorting
        semantic = [(1, 1), (2, 5)]  # doc 1 rank 1, doc 2 rank 5
        keyword = [(3, 1), (2, 2)]   # doc 3 rank 1, doc 2 rank 2

        scores = compute_rrf_scores(semantic, keyword)

        # Sort by score descending
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x][0], reverse=True)

        # Doc 2 should be first (appears in both with combined score)
        # Doc 1 semantic-only rank 1
        # Doc 3 keyword-only rank 1
        assert sorted_ids[0] == 2  # Combined should win

    def test_combined_doc_beats_single_source(self) -> None:
        """A doc in both lists should score higher than either alone."""
        # Doc 1: semantic rank 1 only
        # Doc 2: semantic rank 10, keyword rank 10 (combined)
        semantic = [(1, 1), (2, 10)]
        keyword = [(2, 10)]

        scores = compute_rrf_scores(semantic, keyword)

        # Doc 2 combined score should beat doc 1 single score
        doc1_score = scores[1][0]
        doc2_score = scores[2][0]

        # 1/(60+1) = 0.0164 for doc 1
        # 1/(60+10) + 1/(60+10) = 0.0286 for doc 2
        assert doc2_score > doc1_score
