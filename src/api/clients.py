"""Clients API router placeholder for Phase 2 implementation."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.post("")
async def create_client() -> None:
    """Create a new client.

    Raises:
        HTTPException: 501 Not Implemented - placeholder for Phase 2.
    """
    raise HTTPException(status_code=501, detail="Not implemented - Phase 2")
