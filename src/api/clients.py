"""Clients API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.models.client import Client

router = APIRouter(prefix="/api/clients", tags=["clients"])


class ClientCreateRequest(BaseModel):
    """Payload for creating a client."""

    name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class ClientUpdateRequest(BaseModel):
    """Payload for updating a client."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class ClientResponse(BaseModel):
    """Client response model."""

    id: int
    name: str
    email: str | None
    created_at: datetime
    updated_at: datetime | None


class ClientListResponse(BaseModel):
    """Paginated client list response."""

    items: list[ClientResponse]
    total: int
    limit: int
    offset: int


def _to_client_response(client: Client) -> ClientResponse:
    """Map SQLAlchemy client model to response model."""
    return ClientResponse(
        id=client.id,
        name=client.name,
        email=client.email,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Create a new client."""
    client = Client(name=payload.name.strip(), email=payload.email)
    db.add(client)
    await db.flush()
    return _to_client_response(client)


@router.get("", response_model=ClientListResponse)
async def list_clients(
    search: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ClientListResponse:
    """List clients with optional search and pagination."""
    filters = []
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Client.name).like(search_pattern),
                func.lower(func.coalesce(Client.email, "")).like(search_pattern),
            )
        )

    count_stmt = select(func.count(Client.id))
    list_stmt = select(Client).order_by(Client.created_at.desc(), Client.id.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar() or 0)

    clients_result = await db.execute(list_stmt.limit(limit).offset(offset))
    clients = clients_result.scalars().all()

    return ClientListResponse(
        items=[_to_client_response(client) for client in clients],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Get client by ID."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return _to_client_response(client)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Partially update client fields."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        client.name = updates["name"].strip()
    if "email" in updates:
        client.email = updates["email"]

    await db.flush()
    return _to_client_response(client)
