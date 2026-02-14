"""Tests for document model resolution."""

from src.documents.model_resolver import VisionModelSpec, resolve_vision_model

DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_OPENAI_MODEL = "gpt-5.3"


def test_resolve_vision_model_keeps_known_model() -> None:
    model = resolve_vision_model("claude-3-5-sonnet-20241022")
    assert model == VisionModelSpec(provider="anthropic", model=DEFAULT_ANTHROPIC_MODEL)


def test_resolve_vision_model_aliases() -> None:
    assert resolve_vision_model("opus-4.6") == VisionModelSpec(
        provider="anthropic", model=DEFAULT_ANTHROPIC_MODEL
    )
    assert resolve_vision_model("opus 4.6") == VisionModelSpec(
        provider="anthropic", model=DEFAULT_ANTHROPIC_MODEL
    )
    assert resolve_vision_model("gpt-5.3") == VisionModelSpec(
        provider="openai", model=DEFAULT_OPENAI_MODEL
    )
    assert resolve_vision_model("gpt-5.3-mini") == VisionModelSpec(
        provider="openai", model=DEFAULT_OPENAI_MODEL
    )


def test_resolve_vision_model_empty_or_none() -> None:
    assert resolve_vision_model("") == VisionModelSpec(
        provider="anthropic", model=DEFAULT_ANTHROPIC_MODEL
    )
    assert resolve_vision_model(None) == VisionModelSpec(
        provider="anthropic", model=DEFAULT_ANTHROPIC_MODEL
    )
