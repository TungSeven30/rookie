"""Voyage AI embedding client for generating text embeddings.

Provides embedding generation for semantic search using Voyage AI's API.
Supports mock mode for testing without an API key.
"""

import hashlib
import os
import random
from dataclasses import dataclass, field

import voyageai

# Singleton instance for the embedding client
_embedding_client: "EmbeddingClient | None" = None


@dataclass
class EmbeddingClient:
    """Client for generating embeddings using Voyage AI.

    Supports mock mode for testing without an API key.
    In mock mode, generates deterministic pseudo-random vectors based on input text.

    Args:
        api_key: Voyage AI API key. Required unless use_mock is True.
        model: Model name to use for embeddings.
        dimension: Embedding vector dimension.
        use_mock: If True, generates mock embeddings instead of calling API.
    """

    api_key: str | None = None
    model: str = "voyage-3-large"
    dimension: int = 1536
    use_mock: bool = False
    _client: voyageai.Client | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize the Voyage AI client if not in mock mode."""
        if not self.use_mock:
            if not self.api_key:
                raise ValueError("api_key is required when use_mock is False")
            self._client = voyageai.Client(api_key=self.api_key)

    def _mock_embedding(self, text: str) -> list[float]:
        """Generate a deterministic mock embedding based on text content.

        Uses the hash of the text as a seed for reproducible embeddings.

        Args:
            text: Input text to generate mock embedding for.

        Returns:
            List of floats representing the mock embedding vector.
        """
        # Use stable hash as seed for deterministic output across processes
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big", signed=False)
        rng = random.Random(seed)
        # Generate normalized random vector
        raw = [rng.gauss(0, 1) for _ in range(self.dimension)]
        norm = sum(x**2 for x in raw) ** 0.5
        return [x / norm for x in raw]

    def embed_texts(
        self,
        texts: list[str],
        input_type: str = "document",
    ) -> list[list[float]]:
        """Embed multiple texts with specified input type.

        Args:
            texts: List of texts to embed.
            input_type: Type of input ("document" or "query").

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            ValueError: If texts list is empty.
        """
        if not texts:
            raise ValueError("texts list cannot be empty")

        if self.use_mock:
            return [self._mock_embedding(text) for text in texts]

        result = self._client.embed(texts, model=self.model, input_type=input_type)
        return result.embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a query text for search.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector for the query.
        """
        embeddings = self.embed_texts([text], input_type="query")
        return embeddings[0]

    def embed_document(self, text: str) -> list[float]:
        """Embed a document text for indexing.

        Args:
            text: Document text to embed.

        Returns:
            Embedding vector for the document.
        """
        embeddings = self.embed_texts([text], input_type="document")
        return embeddings[0]

    def embed_documents(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Embed multiple documents with batching for large lists.

        Args:
            texts: List of document texts to embed.
            batch_size: Number of texts to embed per API call.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            ValueError: If texts list is empty or batch_size <= 0.
        """
        if not texts:
            raise ValueError("texts list cannot be empty")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self.embed_texts(batch, input_type="document")
            all_embeddings.extend(embeddings)

        return all_embeddings


def get_embedding_client(
    api_key: str | None = None,
    model: str = "voyage-3-large",
    dimension: int = 1536,
    use_mock: bool = False,
) -> EmbeddingClient:
    """Get or create the singleton embedding client.

    Args:
        api_key: Voyage AI API key (falls back to VOYAGE_API_KEY if omitted).
        model: Model name to use.
        dimension: Embedding dimension.
        use_mock: If True, use mock embeddings.

    Returns:
        The singleton EmbeddingClient instance.
    """
    global _embedding_client

    if _embedding_client is None:
        resolved_api_key = api_key
        if not use_mock and resolved_api_key is None:
            resolved_api_key = os.getenv("VOYAGE_API_KEY")
        _embedding_client = EmbeddingClient(
            api_key=resolved_api_key,
            model=model,
            dimension=dimension,
            use_mock=use_mock,
        )

    return _embedding_client


def reset_embedding_client() -> None:
    """Reset the singleton embedding client.

    Useful for testing to ensure clean state between tests.
    """
    global _embedding_client
    _embedding_client = None
