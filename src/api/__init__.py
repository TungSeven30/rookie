"""API module exports."""

from src.api.clients import router as clients_router
from src.api.demo import router as demo_router
from src.api.deps import get_db, get_redis
from src.api.health import router as health_router
from src.api.tasks import router as tasks_router

__all__ = [
    "clients_router",
    "demo_router",
    "get_db",
    "get_redis",
    "health_router",
    "tasks_router",
]
