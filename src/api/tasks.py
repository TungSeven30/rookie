"""Tasks API router placeholder for Phase 2 implementation."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
async def create_task() -> None:
    """Create a new task.

    Raises:
        HTTPException: 501 Not Implemented - placeholder for Phase 2.
    """
    raise HTTPException(status_code=501, detail="Not implemented - Phase 2")
