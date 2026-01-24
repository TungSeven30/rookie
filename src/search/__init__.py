"""Search module for hybrid search using embeddings and full-text search."""

from src.search.embeddings import (
    EmbeddingClient,
    get_embedding_client,
    reset_embedding_client,
)
from src.search.hybrid import (
    RRF_K,
    SearchResult,
    compute_rrf_scores,
    hybrid_search,
    keyword_search,
    search_skills,
    semantic_search,
)

__all__ = [
    # Embeddings
    "EmbeddingClient",
    "get_embedding_client",
    "reset_embedding_client",
    # Hybrid search
    "RRF_K",
    "SearchResult",
    "compute_rrf_scores",
    "hybrid_search",
    "keyword_search",
    "search_skills",
    "semantic_search",
]
