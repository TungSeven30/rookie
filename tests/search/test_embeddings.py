"""Tests for the Voyage AI embedding client."""

import pytest

from src.search.embeddings import (
    EmbeddingClient,
    get_embedding_client,
    reset_embedding_client,
)


class TestEmbeddingClient:
    """Tests for EmbeddingClient class."""

    def test_mock_mode_does_not_require_api_key(self) -> None:
        """Mock mode should work without an API key."""
        client = EmbeddingClient(use_mock=True)
        assert client.api_key is None
        assert client.use_mock is True

    def test_real_mode_requires_api_key(self) -> None:
        """Real mode should raise error without API key."""
        with pytest.raises(ValueError, match="api_key is required"):
            EmbeddingClient(use_mock=False)

    def test_embed_query_returns_correct_dimension(self) -> None:
        """embed_query should return vector of correct dimension."""
        client = EmbeddingClient(use_mock=True, dimension=1536)
        embedding = client.embed_query("test query")
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_query_custom_dimension(self) -> None:
        """Custom dimension should be respected."""
        client = EmbeddingClient(use_mock=True, dimension=768)
        embedding = client.embed_query("test query")
        assert len(embedding) == 768

    def test_embed_query_is_normalized(self) -> None:
        """Mock embeddings should be normalized (unit length)."""
        client = EmbeddingClient(use_mock=True)
        embedding = client.embed_query("test query")
        norm = sum(x**2 for x in embedding) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_embed_query_is_deterministic(self) -> None:
        """Same input should produce same output in mock mode."""
        client = EmbeddingClient(use_mock=True)
        emb1 = client.embed_query("same text")
        emb2 = client.embed_query("same text")
        assert emb1 == emb2

    def test_embed_query_different_for_different_text(self) -> None:
        """Different inputs should produce different outputs."""
        client = EmbeddingClient(use_mock=True)
        emb1 = client.embed_query("text one")
        emb2 = client.embed_query("text two")
        assert emb1 != emb2

    def test_embed_document_returns_correct_dimension(self) -> None:
        """embed_document should return vector of correct dimension."""
        client = EmbeddingClient(use_mock=True, dimension=1536)
        embedding = client.embed_document("test document")
        assert len(embedding) == 1536

    def test_embed_texts_multiple_texts(self) -> None:
        """embed_texts should handle multiple texts."""
        client = EmbeddingClient(use_mock=True)
        texts = ["text 1", "text 2", "text 3"]
        embeddings = client.embed_texts(texts)
        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)

    def test_embed_texts_empty_list_raises(self) -> None:
        """embed_texts should raise on empty list."""
        client = EmbeddingClient(use_mock=True)
        with pytest.raises(ValueError, match="texts list cannot be empty"):
            client.embed_texts([])

    def test_embed_documents_batching(self) -> None:
        """embed_documents should handle batching correctly."""
        client = EmbeddingClient(use_mock=True)
        texts = [f"doc {i}" for i in range(25)]
        embeddings = client.embed_documents(texts, batch_size=10)
        assert len(embeddings) == 25

    def test_embed_documents_empty_list_raises(self) -> None:
        """embed_documents should raise on empty list."""
        client = EmbeddingClient(use_mock=True)
        with pytest.raises(ValueError, match="texts list cannot be empty"):
            client.embed_documents([])

    def test_embed_documents_invalid_batch_size_raises(self) -> None:
        """embed_documents should raise on invalid batch_size."""
        client = EmbeddingClient(use_mock=True)
        with pytest.raises(ValueError, match="batch_size must be positive"):
            client.embed_documents(["text"], batch_size=0)


class TestGetEmbeddingClient:
    """Tests for singleton get_embedding_client function."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        reset_embedding_client()

    def test_returns_same_instance(self) -> None:
        """Singleton should return same instance."""
        client1 = get_embedding_client(use_mock=True)
        client2 = get_embedding_client()
        assert client1 is client2

    def test_reset_clears_singleton(self) -> None:
        """reset_embedding_client should clear singleton."""
        client1 = get_embedding_client(use_mock=True)
        reset_embedding_client()
        # After reset, parameters from first call not used
        client2 = get_embedding_client(use_mock=True)
        assert client1 is not client2

    def test_first_call_parameters_used(self) -> None:
        """Parameters from first call should be used."""
        client1 = get_embedding_client(use_mock=True, dimension=768)
        client2 = get_embedding_client()  # Second call ignores params
        assert client1.dimension == 768
        assert client2.dimension == 768  # Same instance
