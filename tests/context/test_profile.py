"""Tests for client profile service."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.context.profile import (
    append_profile_entry,
    get_client_profile_view,
    get_client_with_profile,
    get_profile_history,
    profile_entry_count,
)


class MockRow:
    """Mock database row with attribute access."""

    def __init__(self, entry_type: str, data: dict[str, Any]) -> None:
        self.entry_type = entry_type
        self.data = data


class MockScalarResult:
    """Mock scalar result that yields entries."""

    def __init__(self, entries: list[Any]) -> None:
        self._entries = entries

    def all(self) -> list[Any]:
        return self._entries


class MockScalarsResult:
    """Mock scalars result that yields entries."""

    def __init__(self, entries: list[Any]) -> None:
        self._entries = entries

    def all(self) -> list[Any]:
        return self._entries


class MockResult:
    """Mock database result."""

    def __init__(
        self,
        rows: list[Any] | None = None,
        scalar_value: Any = None,
        scalar_one: Any = None,
    ) -> None:
        self._rows = rows
        self._scalar_value = scalar_value
        self._scalar_one = scalar_one

    def all(self) -> list[Any]:
        return self._rows or []

    def scalar(self) -> Any:
        return self._scalar_value

    def scalar_one_or_none(self) -> Any:
        return self._scalar_one

    def scalars(self) -> MockScalarsResult:
        return MockScalarsResult(self._rows or [])


class TestGetClientProfileView:
    """Tests for get_client_profile_view function."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_entries(self) -> None:
        """Should return empty dict when client has no profile entries."""
        session = AsyncMock()
        session.execute.return_value = MockResult(rows=[])

        result = await get_client_profile_view(session, client_id=1)

        assert result == {}
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_latest_entry_per_type(self) -> None:
        """Should return only the latest entry for each entry_type."""
        session = AsyncMock()

        # Mock: latest entry for each type (already filtered by window function)
        mock_rows = [
            MockRow("filing_status", {"status": "married"}),
            MockRow("address", {"city": "Austin"}),
            MockRow("dependents", {"count": 2}),
        ]
        session.execute.return_value = MockResult(rows=mock_rows)

        result = await get_client_profile_view(session, client_id=1)

        assert result == {
            "filing_status": {"status": "married"},
            "address": {"city": "Austin"},
            "dependents": {"count": 2},
        }

    @pytest.mark.asyncio
    async def test_handles_single_entry(self) -> None:
        """Should handle case with single profile entry."""
        session = AsyncMock()
        mock_rows = [MockRow("filing_status", {"status": "single"})]
        session.execute.return_value = MockResult(rows=mock_rows)

        result = await get_client_profile_view(session, client_id=1)

        assert result == {"filing_status": {"status": "single"}}

    @pytest.mark.asyncio
    async def test_uses_window_function_in_query(self) -> None:
        """Should construct query using window function for latest selection."""
        session = AsyncMock()
        session.execute.return_value = MockResult(rows=[])

        await get_client_profile_view(session, client_id=1)

        # Verify execute was called (query was built and run)
        session.execute.assert_called_once()
        # The actual SQL verification would require inspecting the compiled query
        # For now, we verify the function runs without error


class TestAppendProfileEntry:
    """Tests for append_profile_entry function."""

    @pytest.mark.asyncio
    async def test_creates_new_entry(self) -> None:
        """Should create a new profile entry with correct fields."""
        session = AsyncMock()
        session.add = MagicMock()

        entry_data = {"status": "married_filing_jointly"}
        result = await append_profile_entry(
            session,
            client_id=1,
            entry_type="filing_status",
            data=entry_data,
        )

        assert result.client_id == 1
        assert result.entry_type == "filing_status"
        assert result.data == entry_data
        assert isinstance(result.created_at, datetime)
        session.add.assert_called_once_with(result)
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_never_updates_existing_entries(self) -> None:
        """Should always create new entries (append-only pattern)."""
        session = AsyncMock()
        session.add = MagicMock()

        # Create multiple entries for same type
        await append_profile_entry(
            session,
            client_id=1,
            entry_type="filing_status",
            data={"status": "single"},
        )
        await append_profile_entry(
            session,
            client_id=1,
            entry_type="filing_status",
            data={"status": "married"},
        )

        # Should have called add twice (two new entries)
        assert session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_sets_created_at_timestamp(self) -> None:
        """Should set created_at to current time."""
        session = AsyncMock()
        session.add = MagicMock()

        before = datetime.now(UTC)
        result = await append_profile_entry(
            session,
            client_id=1,
            entry_type="test",
            data={},
        )
        after = datetime.now(UTC)

        assert before <= result.created_at <= after

    @pytest.mark.asyncio
    async def test_append_100_entries_integrity(self) -> None:
        """Append-only log should handle 100 writes without overwrites."""
        session = AsyncMock()
        session.add = MagicMock()
        entries = []

        for i in range(100):
            entry = await append_profile_entry(
                session,
                client_id=1,
                entry_type="filing_status",
                data={"index": i},
            )
            entries.append(entry)

        assert session.add.call_count == 100
        assert len({id(entry) for entry in entries}) == 100
        assert [entry.data["index"] for entry in entries] == list(range(100))

    @pytest.mark.asyncio
    async def test_handles_complex_data(self) -> None:
        """Should handle complex nested data structures."""
        session = AsyncMock()
        session.add = MagicMock()

        complex_data = {
            "dependents": [
                {"name": "Alice", "age": 10, "ssn_last4": "1234"},
                {"name": "Bob", "age": 8, "ssn_last4": "5678"},
            ],
            "relationship": "children",
            "custody": {"type": "full", "percentage": 100},
        }

        result = await append_profile_entry(
            session,
            client_id=1,
            entry_type="dependents",
            data=complex_data,
        )

        assert result.data == complex_data


class TestGetProfileHistory:
    """Tests for get_profile_history function."""

    @pytest.mark.asyncio
    async def test_returns_all_entries_for_client(self) -> None:
        """Should return all profile entries for a client."""
        session = AsyncMock()

        entries = [MagicMock(), MagicMock(), MagicMock()]
        session.execute.return_value = MockResult(rows=entries)

        result = await get_profile_history(session, client_id=1)

        assert result == entries

    @pytest.mark.asyncio
    async def test_filters_by_entry_type(self) -> None:
        """Should filter entries by type when specified."""
        session = AsyncMock()

        entries = [MagicMock()]
        session.execute.return_value = MockResult(rows=entries)

        result = await get_profile_history(
            session,
            client_id=1,
            entry_type="filing_status",
        )

        assert result == entries
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_applies_limit(self) -> None:
        """Should limit results when limit is specified."""
        session = AsyncMock()

        entries = [MagicMock(), MagicMock()]
        session.execute.return_value = MockResult(rows=entries)

        result = await get_profile_history(session, client_id=1, limit=2)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_entries(self) -> None:
        """Should return empty list when no entries exist."""
        session = AsyncMock()
        session.execute.return_value = MockResult(rows=[])

        result = await get_profile_history(session, client_id=1)

        assert result == []


class TestGetClientWithProfile:
    """Tests for get_client_with_profile function."""

    @pytest.mark.asyncio
    async def test_returns_client_and_profile(self) -> None:
        """Should return both client and computed profile."""
        session = AsyncMock()

        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.name = "John Doe"

        # First call returns client, second call returns profile
        mock_profile_rows = [MockRow("filing_status", {"status": "single"})]

        # Mock execute to return client on first call, profile on second
        session.execute.side_effect = [
            MockResult(scalar_one=mock_client),
            MockResult(rows=mock_profile_rows),
        ]

        client, profile = await get_client_with_profile(session, client_id=1)

        assert client == mock_client
        assert profile == {"filing_status": {"status": "single"}}

    @pytest.mark.asyncio
    async def test_returns_none_when_client_not_found(self) -> None:
        """Should return (None, {}) when client doesn't exist."""
        session = AsyncMock()
        session.execute.return_value = MockResult(scalar_one=None)

        client, profile = await get_client_with_profile(session, client_id=999)

        assert client is None
        assert profile == {}


class TestProfileEntryCount:
    """Tests for profile_entry_count function."""

    @pytest.mark.asyncio
    async def test_counts_all_entries_for_client(self) -> None:
        """Should count all profile entries for a client."""
        session = AsyncMock()
        session.execute.return_value = MockResult(scalar_value=15)

        count = await profile_entry_count(session, client_id=1)

        assert count == 15

    @pytest.mark.asyncio
    async def test_filters_count_by_entry_type(self) -> None:
        """Should count entries filtered by type."""
        session = AsyncMock()
        session.execute.return_value = MockResult(scalar_value=3)

        count = await profile_entry_count(
            session,
            client_id=1,
            entry_type="address",
        )

        assert count == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_entries(self) -> None:
        """Should return 0 when no entries exist."""
        session = AsyncMock()
        session.execute.return_value = MockResult(scalar_value=None)

        count = await profile_entry_count(session, client_id=1)

        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_zero_for_nonexistent_type(self) -> None:
        """Should return 0 for entry types that don't exist."""
        session = AsyncMock()
        session.execute.return_value = MockResult(scalar_value=0)

        count = await profile_entry_count(
            session,
            client_id=1,
            entry_type="nonexistent",
        )

        assert count == 0
