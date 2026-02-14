"""Model resolution helpers for document vision providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import structlog


logger = structlog.get_logger()

_DEFAULT_ANTHROPIC_MODEL: Final[str] = "claude-opus-4-6"
_DEFAULT_OPENAI_MODEL: Final[str] = "gpt-5.3"


@dataclass(frozen=True)
class VisionModelSpec:
    """Resolved provider/model pair for document vision calls."""

    provider: str
    model: str


# `ANTHROPIC_MODEL` aliases are now mapped to the right provider/model.
_ANTHROPIC_MODEL_ALIASES: Final[dict[str, str]] = {
    "opus": _DEFAULT_ANTHROPIC_MODEL,
    "opus-4.6": _DEFAULT_ANTHROPIC_MODEL,
    "opus_4.6": _DEFAULT_ANTHROPIC_MODEL,
    "opus-4-6": _DEFAULT_ANTHROPIC_MODEL,
    "claude-opus": _DEFAULT_ANTHROPIC_MODEL,
    "claude-opus-4-6": _DEFAULT_ANTHROPIC_MODEL,
}

_OPENAI_MODEL_ALIASES: Final[dict[str, str]] = {
    "gpt": _DEFAULT_OPENAI_MODEL,
    "gpt-5": _DEFAULT_OPENAI_MODEL,
    "gpt-5.3": _DEFAULT_OPENAI_MODEL,
    "gpt-5-3": _DEFAULT_OPENAI_MODEL,
    "gpt5.3": _DEFAULT_OPENAI_MODEL,
    "gpt-5.3-mini": _DEFAULT_OPENAI_MODEL,
}


def resolve_vision_model(model_name: str | None) -> VisionModelSpec:
    """Resolve a configured model name to a provider/model pair."""

    if model_name is None:
        return VisionModelSpec(provider="anthropic", model=_DEFAULT_ANTHROPIC_MODEL)

    normalized = model_name.strip().lower().replace("_", "-").replace(" ", "-")
    if not normalized:
        return VisionModelSpec(provider="anthropic", model=_DEFAULT_ANTHROPIC_MODEL)

    if normalized in _ANTHROPIC_MODEL_ALIASES:
        resolved_model = _ANTHROPIC_MODEL_ALIASES[normalized]
        logger.warning(
            "resolved_model_alias",
            requested_model=model_name,
            provider="anthropic",
            resolved_model=resolved_model,
        )
        return VisionModelSpec(provider="anthropic", model=resolved_model)

    if normalized in _OPENAI_MODEL_ALIASES:
        resolved_model = _OPENAI_MODEL_ALIASES[normalized]
        logger.warning(
            "resolved_model_alias",
            requested_model=model_name,
            provider="openai",
            resolved_model=resolved_model,
        )
        return VisionModelSpec(provider="openai", model=resolved_model)

    # Preserve explicit provider prefixes.
    if normalized.startswith("claude") or normalized.startswith("opus"):
        return VisionModelSpec(provider="anthropic", model=normalized)

    if normalized.startswith("gpt"):
        return VisionModelSpec(provider="openai", model=normalized)

    logger.warning(
        "resolved_model_fallback",
        requested_model=model_name,
        provider="anthropic",
        resolved_model=_DEFAULT_ANTHROPIC_MODEL,
    )
    return VisionModelSpec(provider="anthropic", model=_DEFAULT_ANTHROPIC_MODEL)
