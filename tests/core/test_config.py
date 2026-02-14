"""Configuration parsing tests."""

from src.core.config import Settings


def test_allowed_upload_types_accepts_csv(monkeypatch) -> None:
    """CSV string in env parses into a list of content types."""
    monkeypatch.setenv(
        "ALLOWED_UPLOAD_TYPES",
        "application/pdf,image/jpeg,image/png,image/jpg",
    )
    cfg = Settings(database_url="postgresql+asyncpg://user@localhost:5432/testdb")
    assert cfg.allowed_upload_types == [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]


def test_allowed_upload_types_accepts_json_array(monkeypatch) -> None:
    """JSON array string in env parses into a list of content types."""
    monkeypatch.setenv(
        "ALLOWED_UPLOAD_TYPES",
        '["application/pdf","image/jpeg","image/png","image/jpg"]',
    )
    cfg = Settings(database_url="postgresql+asyncpg://user@localhost:5432/testdb")
    assert cfg.allowed_upload_types == [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]


def test_allowed_upload_types_rejects_invalid_object(monkeypatch) -> None:
    """Invalid values fail with a clear validation error."""
    monkeypatch.setenv("ALLOWED_UPLOAD_TYPES", '{"invalid":"json"}')
    try:
        Settings(database_url="postgresql+asyncpg://user@localhost:5432/testdb")
    except Exception as exc:
        assert "ALLOWED_UPLOAD_TYPES" in str(exc)
    else:
        raise AssertionError("Expected invalid ALLOWED_UPLOAD_TYPES to fail")
