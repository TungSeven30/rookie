"""Client profile service with append-only log pattern.

Provides computed views of client profiles by deriving current state
from the append-only log of profile entries. Each entry_type retains
only the latest value while maintaining full history.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.client import Client, ClientProfileEntry


async def get_client_profile_view(
    session: AsyncSession,
    client_id: int,
) -> dict[str, Any]:
    """Compute the current profile view from append-only log.

    Uses window functions to efficiently get the latest entry for each
    entry_type, building a complete current-state view of the client profile.

    Args:
        session: Database session
        client_id: ID of the client

    Returns:
        Dictionary mapping entry_type to its latest data value.
        Empty dict if no entries exist.

    Example:
        >>> profile = await get_client_profile_view(session, client_id=1)
        >>> profile
        {
            "filing_status": {"status": "married_filing_jointly"},
            "dependents": {"count": 2, "names": ["Alice", "Bob"]},
            "address": {"street": "123 Main St", "city": "Austin", "state": "TX"}
        }
    """
    # Subquery: rank entries by entry_type, ordered by created_at descending
    subquery = (
        select(
            ClientProfileEntry.entry_type,
            ClientProfileEntry.data,
            func.row_number()
            .over(
                partition_by=ClientProfileEntry.entry_type,
                order_by=ClientProfileEntry.created_at.desc(),
            )
            .label("row_num"),
        )
        .where(ClientProfileEntry.client_id == client_id)
        .subquery()
    )

    # Main query: select only the latest (row_num = 1) for each entry_type
    stmt = select(subquery.c.entry_type, subquery.c.data).where(
        subquery.c.row_num == 1
    )

    result = await session.execute(stmt)
    rows = result.all()

    return {row.entry_type: row.data for row in rows}


async def append_profile_entry(
    session: AsyncSession,
    client_id: int,
    entry_type: str,
    data: dict[str, Any],
) -> ClientProfileEntry:
    """Append a new profile entry (never updates existing entries).

    This is the ONLY way to modify profile data. Creates a new log entry
    which will become the latest value for the given entry_type.

    Args:
        session: Database session
        client_id: ID of the client
        entry_type: Type of profile entry (e.g., "filing_status", "address")
        data: JSONB data for this entry

    Returns:
        The newly created ClientProfileEntry

    Example:
        >>> entry = await append_profile_entry(
        ...     session,
        ...     client_id=1,
        ...     entry_type="filing_status",
        ...     data={"status": "married_filing_jointly"}
        ... )
        >>> entry.id
        42
    """
    entry = ClientProfileEntry(
        client_id=client_id,
        entry_type=entry_type,
        data=data,
        created_at=datetime.now(UTC),
    )
    session.add(entry)
    await session.flush()  # Populate ID without committing
    return entry


async def get_profile_history(
    session: AsyncSession,
    client_id: int,
    entry_type: str | None = None,
    limit: int | None = None,
) -> list[ClientProfileEntry]:
    """Get profile entry history for a client.

    Retrieves historical entries, optionally filtered by entry_type.
    Results are ordered by created_at descending (newest first).

    Args:
        session: Database session
        client_id: ID of the client
        entry_type: Optional filter for specific entry type
        limit: Maximum number of entries to return

    Returns:
        List of ClientProfileEntry objects, newest first

    Example:
        >>> history = await get_profile_history(
        ...     session,
        ...     client_id=1,
        ...     entry_type="filing_status",
        ...     limit=5
        ... )
        >>> len(history)
        5
    """
    stmt = (
        select(ClientProfileEntry)
        .where(ClientProfileEntry.client_id == client_id)
        .order_by(ClientProfileEntry.created_at.desc())
    )

    if entry_type is not None:
        stmt = stmt.where(ClientProfileEntry.entry_type == entry_type)

    if limit is not None:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_client_with_profile(
    session: AsyncSession,
    client_id: int,
) -> tuple[Client | None, dict[str, Any]]:
    """Get a client with their computed profile view.

    Convenience function that fetches both the client record and their
    complete current profile in a single call.

    Args:
        session: Database session
        client_id: ID of the client

    Returns:
        Tuple of (Client or None, profile dict).
        If client doesn't exist, returns (None, {}).

    Example:
        >>> client, profile = await get_client_with_profile(session, 1)
        >>> client.name
        "John Doe"
        >>> profile["filing_status"]
        {"status": "single"}
    """
    # Fetch client
    stmt = select(Client).where(Client.id == client_id)
    result = await session.execute(stmt)
    client = result.scalar_one_or_none()

    if client is None:
        return None, {}

    # Fetch profile view
    profile = await get_client_profile_view(session, client_id)
    return client, profile


async def profile_entry_count(
    session: AsyncSession,
    client_id: int,
    entry_type: str | None = None,
) -> int:
    """Count profile entries for a client.

    Args:
        session: Database session
        client_id: ID of the client
        entry_type: Optional filter for specific entry type

    Returns:
        Number of profile entries

    Example:
        >>> count = await profile_entry_count(session, client_id=1)
        >>> count
        15
        >>> count = await profile_entry_count(session, client_id=1, entry_type="address")
        >>> count
        3
    """
    stmt = select(func.count()).select_from(ClientProfileEntry).where(
        ClientProfileEntry.client_id == client_id
    )

    if entry_type is not None:
        stmt = stmt.where(ClientProfileEntry.entry_type == entry_type)

    result = await session.execute(stmt)
    return result.scalar() or 0
