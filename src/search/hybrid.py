"""Hybrid search combining pgvector semantic search with BM25 full-text search.

Uses Reciprocal Rank Fusion (RRF) to combine results from both search methods.
"""

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.skill import SkillEmbedding, SkillFile
from src.search.embeddings import EmbeddingClient

# RRF constant (standard value from the literature)
RRF_K = 60


@dataclass
class SearchResult:
    """A result from hybrid search combining semantic and keyword scores.

    Attributes:
        id: SkillEmbedding record ID.
        skill_file_id: ID of the parent skill file.
        skill_name: Name of the skill file.
        chunk_text: The text chunk that matched.
        semantic_rank: Rank from semantic search (1-based, None if not found).
        keyword_rank: Rank from keyword search (1-based, None if not found).
        hybrid_score: Combined RRF score.
    """

    id: int
    skill_file_id: int
    skill_name: str
    chunk_text: str
    semantic_rank: int | None
    keyword_rank: int | None
    hybrid_score: float

    @property
    def source_info(self) -> str:
        """Return a string describing which search methods found this result."""
        sources = []
        if self.semantic_rank is not None:
            sources.append(f"semantic:#{self.semantic_rank}")
        if self.keyword_rank is not None:
            sources.append(f"keyword:#{self.keyword_rank}")
        return ", ".join(sources) if sources else "unknown"


async def semantic_search(
    session: AsyncSession,
    query_embedding: list[float],
    limit: int = 20,
) -> list[tuple[int, int]]:
    """Perform semantic search using pgvector cosine distance.

    Args:
        session: Database session.
        query_embedding: Query vector from embedding model.
        limit: Maximum number of results.

    Returns:
        List of (embedding_id, rank) tuples, ranked by similarity.
    """
    # Use pgvector's cosine distance operator <=>
    # Lower distance = more similar, so we order ascending
    stmt = (
        select(SkillEmbedding.id)
        .order_by(SkillEmbedding.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Return (id, 1-based rank)
    return [(row, idx + 1) for idx, row in enumerate(rows)]


async def keyword_search(
    session: AsyncSession,
    query_text: str,
    limit: int = 20,
) -> list[tuple[int, int]]:
    """Perform full-text search using PostgreSQL ts_rank.

    Args:
        session: Database session.
        query_text: Search query text.
        limit: Maximum number of results.

    Returns:
        List of (embedding_id, rank) tuples, ranked by text relevance.
    """
    # Convert query to tsquery (websearch_to_tsquery handles natural language)
    # ts_rank returns relevance score (higher = more relevant)
    stmt = text("""
        SELECT id
        FROM skill_embeddings
        WHERE to_tsvector('english', chunk_text) @@ websearch_to_tsquery('english', :query)
        ORDER BY ts_rank(to_tsvector('english', chunk_text), websearch_to_tsquery('english', :query)) DESC
        LIMIT :limit
    """)

    result = await session.execute(stmt, {"query": query_text, "limit": limit})
    rows = result.fetchall()

    # Return (id, 1-based rank)
    return [(row[0], idx + 1) for idx, row in enumerate(rows)]


def compute_rrf_scores(
    semantic_results: list[tuple[int, int]],
    keyword_results: list[tuple[int, int]],
    k: int = RRF_K,
) -> dict[int, tuple[float, int | None, int | None]]:
    """Compute Reciprocal Rank Fusion scores for combined results.

    RRF formula: score = sum(1 / (k + rank)) for each result set

    Args:
        semantic_results: List of (id, rank) from semantic search.
        keyword_results: List of (id, rank) from keyword search.
        k: RRF constant (default 60, standard value).

    Returns:
        Dict mapping id -> (rrf_score, semantic_rank, keyword_rank).
    """
    scores: dict[int, tuple[float, int | None, int | None]] = {}

    # Add semantic scores
    for doc_id, rank in semantic_results:
        rrf_score = 1.0 / (k + rank)
        scores[doc_id] = (rrf_score, rank, None)

    # Add or merge keyword scores
    for doc_id, rank in keyword_results:
        keyword_rrf = 1.0 / (k + rank)
        if doc_id in scores:
            # Merge: add keyword score to existing semantic score
            existing_score, sem_rank, _ = scores[doc_id]
            scores[doc_id] = (existing_score + keyword_rrf, sem_rank, rank)
        else:
            # New entry: keyword only
            scores[doc_id] = (keyword_rrf, None, rank)

    return scores


async def hybrid_search(
    session: AsyncSession,
    query_text: str,
    embedding_client: EmbeddingClient,
    limit: int = 10,
    semantic_limit: int = 20,
    keyword_limit: int = 20,
) -> list[SearchResult]:
    """Perform hybrid search combining semantic and keyword search.

    Uses RRF to fuse results from pgvector cosine similarity and
    PostgreSQL full-text search.

    Args:
        session: Database session.
        query_text: Search query text.
        embedding_client: Client for generating query embeddings.
        limit: Maximum number of final results to return.
        semantic_limit: Max results from semantic search (pre-fusion).
        keyword_limit: Max results from keyword search (pre-fusion).

    Returns:
        List of SearchResult objects sorted by hybrid score descending.
    """
    # Generate query embedding
    query_embedding = embedding_client.embed_query(query_text)

    # Run both searches
    semantic_results = await semantic_search(session, query_embedding, semantic_limit)
    keyword_results = await keyword_search(session, query_text, keyword_limit)

    # Compute RRF scores
    rrf_scores = compute_rrf_scores(semantic_results, keyword_results)

    if not rrf_scores:
        return []

    # Sort by RRF score descending and take top results
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x][0], reverse=True)
    top_ids = sorted_ids[:limit]

    # Fetch full records for top results
    stmt = (
        select(SkillEmbedding, SkillFile.name)
        .join(SkillFile, SkillEmbedding.skill_file_id == SkillFile.id)
        .where(SkillEmbedding.id.in_(top_ids))
    )
    result = await session.execute(stmt)
    rows = result.all()

    # Build result objects
    results_map = {
        embedding.id: SearchResult(
            id=embedding.id,
            skill_file_id=embedding.skill_file_id,
            skill_name=skill_name,
            chunk_text=embedding.chunk_text,
            semantic_rank=rrf_scores[embedding.id][1],
            keyword_rank=rrf_scores[embedding.id][2],
            hybrid_score=rrf_scores[embedding.id][0],
        )
        for embedding, skill_name in rows
    }

    # Return in RRF score order
    return [results_map[doc_id] for doc_id in top_ids if doc_id in results_map]


async def search_skills(
    session: AsyncSession,
    query: str,
    embedding_client: EmbeddingClient | None = None,
    limit: int = 10,
) -> list[SearchResult]:
    """Convenience wrapper for hybrid search on skills.

    Args:
        session: Database session.
        query: Search query text.
        embedding_client: Embedding client (uses singleton if None).
        limit: Maximum results to return.

    Returns:
        List of SearchResult objects.
    """
    from src.search.embeddings import get_embedding_client

    if embedding_client is None:
        embedding_client = get_embedding_client(use_mock=False)

    return await hybrid_search(session, query, embedding_client, limit=limit)
