"""Tests for extractor authentication behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import settings
from src.documents.extractor import _extract_with_vision
from src.documents.models import ConfidenceLevel, Form1099INT


@pytest.mark.asyncio
async def test_extract_with_vision_uses_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic client uses configured API key."""
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    fake_result = Form1099INT(
        payer_name="Test Bank",
        payer_tin="12-3456789",
        recipient_tin="123-45-6789",
        interest_income=0,
        confidence=ConfidenceLevel.HIGH,
    )
    fake_messages = AsyncMock()
    fake_messages.create = AsyncMock(return_value=fake_result)
    fake_client = SimpleNamespace(messages=fake_messages)

    with patch(
        "instructor.from_anthropic", return_value=fake_client
    ) as mock_instructor:
        with patch("anthropic.AsyncAnthropic") as mock_anthropic:
            result = await _extract_with_vision(
                image_bytes=b"test",
                media_type="image/jpeg",
                prompt="prompt",
                response_model=Form1099INT,
                client=None,
            )

    mock_anthropic.assert_called_once_with(api_key="test-key")
    mock_instructor.assert_called_once()
    assert result == fake_result
