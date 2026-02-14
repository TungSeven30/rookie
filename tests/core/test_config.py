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
