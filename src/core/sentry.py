"""Sentry error tracking integration."""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from src.core.config import settings


def init_sentry() -> None:
    """Initialize Sentry error tracking if DSN is configured.

    Integrates with FastAPI and Starlette for automatic error capture.
    Only captures 5xx errors and samples 10% of traces for performance.
    PII is never sent to protect client data sensitivity.
    """
    if not settings.sentry_dsn:
        return  # Skip gracefully if no DSN

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
        send_default_pii=False,  # Never send PII (CPA data sensitivity)
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes={*range(500, 600)},
            ),
        ],
    )


def capture_test_exception() -> None:
    """Capture a test exception to verify Sentry is working.

    Call this after init_sentry() to confirm the integration is functional.
    """
    try:
        raise ValueError("Sentry test exception")
    except ValueError:
        sentry_sdk.capture_exception()
