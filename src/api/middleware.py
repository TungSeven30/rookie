"""Request context middleware for correlation ID tracking."""

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.core.logging import task_id_ctx

RequestResponseEndpoint = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that sets request context variables for logging correlation.

    Extracts X-Request-ID header (or generates one) and sets it in the
    task_id context variable for structured logging correlation.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize middleware with ASGI app.

        Args:
            app: The ASGI application to wrap.
        """
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and set context variables.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            Response with X-Request-ID header set.
        """
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        task_id_ctx.set(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response
