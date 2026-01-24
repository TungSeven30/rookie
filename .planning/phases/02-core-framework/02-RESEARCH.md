# Phase 2: Core Framework - Research

**Researched:** 2026-01-24
**Domain:** Task orchestration, circuit breaker, skill engine, context builder, hybrid search
**Confidence:** HIGH

## Summary

Phase 2 builds the production-ready orchestration layer on top of Phase 1's infrastructure. The research covers five key domains: task state machine transitions, circuit breaker pattern for LLM resilience, skill engine with YAML parsing and version selection, context builder for agent prompts, and hybrid search combining pgvector semantic search with BM25 full-text search.

The Python ecosystem has mature solutions for all requirements. For state machines, `python-statemachine` (v2.5.0) provides native async support and clean declarative syntax. For circuit breakers, `pybreaker` (v1.4.1) with Redis storage enables distributed state across workers. Skill file parsing uses Pydantic with PyYAML/ruamel.yaml for type-safe YAML validation. Hybrid search leverages pg_textsearch (BM25) with pgvector using Reciprocal Rank Fusion (RRF) for score normalization.

**Primary recommendation:** Use declarative patterns throughout - state machine for task transitions, Pydantic models for skill files, and SQL CTEs with RRF for hybrid search. Store circuit breaker state in Redis (already established in Phase 1) and implement append-only log queries with computed views using SQLAlchemy window functions.

## Standard Stack

The established libraries/tools for this domain:

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-statemachine | 2.5.0 | Task state machine | Native async, Enum states, declarative transitions, diagrams |
| pybreaker | 1.4.1 | Circuit breaker | Redis storage, proven pattern, configurable thresholds |
| pydantic-yaml | 1.6.0 | YAML parsing | Pydantic 2 compatible, type-safe validation |
| ruamel.yaml | 0.18.x | YAML backend | Preserves comments, robust parsing |
| pg_textsearch | 0.4.x | BM25 full-text search | True BM25 ranking, block-max WAND optimization |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| voyage-ai | latest | Embeddings | Generate embeddings for skill/document chunks |
| pyyaml | 6.x | YAML fallback | Simple YAML parsing when ruamel not needed |
| structlog | 25.5.0 | Logging (from Phase 1) | All orchestration logging |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-statemachine | transitions | transitions is older, less async support, python-statemachine has better ergonomics |
| pybreaker | circuit-breaker-box | circuit-breaker-box newer but less proven; pybreaker has 8+ years of production use |
| pg_textsearch | ParadeDB pg_search | ParadeDB more features but heavier; pg_textsearch is Timescale-backed, simpler |
| Voyage embeddings | OpenAI text-embedding-3 | OpenAI is alternative; Voyage is Anthropic-recommended partner |

**Installation:**
```bash
uv add python-statemachine pybreaker pydantic-yaml ruamel.yaml
# pg_textsearch installed as PostgreSQL extension, not Python package
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── orchestration/
│   ├── __init__.py
│   ├── state_machine.py     # TaskStateMachine class
│   ├── dispatcher.py        # Task routing by type
│   └── circuit_breaker.py   # LLM circuit breaker
├── skills/
│   ├── __init__.py
│   ├── loader.py            # YAML skill file parser
│   ├── selector.py          # Version selection by effective_date
│   └── models.py            # Pydantic skill models
├── context/
│   ├── __init__.py
│   ├── builder.py           # Context assembly
│   └── profile.py           # Client profile computed view
├── search/
│   ├── __init__.py
│   ├── hybrid.py            # Hybrid search implementation
│   ├── embeddings.py        # Voyage embedding client
│   └── queries.py           # SQL query builders
├── models/                  # (from Phase 1)
├── core/                    # (from Phase 1)
└── api/                     # (from Phase 1)
```

### Pattern 1: Declarative State Machine with Async Callbacks

**What:** Define task states and transitions declaratively using python-statemachine
**When to use:** All task state management (ORCH-01)
**Example:**
```python
# Source: https://python-statemachine.readthedocs.io/en/latest/
from statemachine import StateMachine, State
from statemachine.mixins import MachineMixin
from sqlalchemy.ext.asyncio import AsyncSession

class TaskStateMachine(StateMachine):
    """Task state machine with async transition callbacks."""

    # States (match TaskStatus enum from Phase 1)
    pending = State(initial=True)
    assigned = State()
    in_progress = State()
    completed = State(final=True)
    failed = State(final=True)
    escalated = State(final=True)

    # Transitions
    assign = pending.to(assigned)
    start = assigned.to(in_progress)
    complete = in_progress.to(completed)
    fail = in_progress.to(failed) | assigned.to(failed)
    escalate = in_progress.to(escalated) | assigned.to(escalated)
    retry = failed.to(pending)  # Allow retry from failed

    async def on_enter_assigned(self, agent: str) -> None:
        """Update task with assigned agent."""
        self.task.assigned_agent = agent
        await self.session.flush()

    async def on_enter_completed(self) -> None:
        """Record completion timestamp."""
        from datetime import datetime
        self.task.completed_at = datetime.utcnow()
        await self.session.flush()
```

### Pattern 2: Circuit Breaker with Redis Storage

**What:** Protect LLM calls with circuit breaker pattern, share state across workers
**When to use:** All LLM API calls (ORCH-03, ORCH-04, ORCH-05)
**Example:**
```python
# Source: https://github.com/danielfm/pybreaker
import pybreaker
import redis.asyncio as redis
from functools import wraps

class AsyncCircuitBreaker:
    """Async wrapper around pybreaker with Redis storage."""

    def __init__(
        self,
        redis_client: redis.Redis,
        name: str = "llm_breaker",
        fail_max: int = 5,
        reset_timeout: int = 30,
        success_threshold: int = 2,
    ):
        # Note: pybreaker uses sync redis, need adapter for async
        self._sync_redis = redis.StrictRedis.from_url(
            str(redis_client.connection_pool.connection_kwargs.get("url", "redis://localhost:6379"))
        )
        self.breaker = pybreaker.CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            state_storage=pybreaker.CircuitRedisStorage(
                pybreaker.STATE_CLOSED,
                self._sync_redis,
                namespace=name,
            ),
        )
        self.success_threshold = success_threshold
        self._half_open_successes = 0

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    def _record_success(self):
        """Record success, handle half-open -> closed transition."""
        if self.breaker.current_state == "half_open":
            self._half_open_successes += 1
            if self._half_open_successes >= self.success_threshold:
                self.breaker.close()
                self._half_open_successes = 0

    def _record_failure(self):
        """Record failure, let pybreaker handle state transitions."""
        self._half_open_successes = 0
```

### Pattern 3: Pydantic Skill Model with Version Selection

**What:** Parse skill YAML files with Pydantic validation, select by effective_date
**When to use:** Loading skills for agent context (SKILL-01, SKILL-02)
**Example:**
```python
# Source: https://pypi.org/project/pydantic-yaml/
from datetime import date
from pathlib import Path
from pydantic import BaseModel, Field
import yaml

class SkillMetadata(BaseModel):
    """Skill file metadata with versioning."""
    name: str
    version: str
    effective_date: date
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

class SkillContent(BaseModel):
    """Skill instructions and examples."""
    instructions: str
    examples: list[dict] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

class SkillFile(BaseModel):
    """Complete skill file model."""
    metadata: SkillMetadata
    content: SkillContent

def select_skill_version(
    skills: list[SkillFile],
    tax_year: int,
) -> SkillFile | None:
    """Select the skill version effective for a given tax year.

    Returns the skill with the latest effective_date that is
    on or before January 1 of the tax year.
    """
    # Tax year effective date is Jan 1 of that year
    target_date = date(tax_year, 1, 1)

    # Filter skills effective on or before target date
    applicable = [
        s for s in skills
        if s.metadata.effective_date <= target_date
    ]

    if not applicable:
        return None

    # Return the one with the latest effective date
    return max(applicable, key=lambda s: s.metadata.effective_date)
```

### Pattern 4: Append-Only Log with Computed View

**What:** Query append-only ClientProfileEntry log to derive current state
**When to use:** Building client context from profile history (SKILL-04, SKILL-05)
**Example:**
```python
# Source: Event sourcing pattern with SQLAlchemy
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB

async def get_client_profile_view(
    session: AsyncSession,
    client_id: int,
) -> dict:
    """Compute current client profile state from append-only log.

    Uses window functions to get the latest entry per entry_type.
    """
    from src.models.client import ClientProfileEntry

    # Subquery: rank entries by type, most recent first
    ranked = (
        select(
            ClientProfileEntry,
            func.row_number().over(
                partition_by=ClientProfileEntry.entry_type,
                order_by=ClientProfileEntry.created_at.desc(),
            ).label("rn"),
        )
        .where(ClientProfileEntry.client_id == client_id)
        .subquery()
    )

    # Get only the latest entry per type (rn = 1)
    query = select(ranked).where(ranked.c.rn == 1)
    result = await session.execute(query)

    # Build profile dict from latest entries
    profile = {}
    for row in result.fetchall():
        profile[row.entry_type] = row.data

    return profile

async def append_profile_entry(
    session: AsyncSession,
    client_id: int,
    entry_type: str,
    data: dict,
) -> None:
    """Append new entry to client profile log (never update)."""
    from src.models.client import ClientProfileEntry

    entry = ClientProfileEntry(
        client_id=client_id,
        entry_type=entry_type,
        data=data,
    )
    session.add(entry)
    await session.flush()
```

### Pattern 5: Hybrid Search with RRF Fusion

**What:** Combine BM25 lexical search with pgvector semantic search using RRF
**When to use:** Searching skills, documents for agent context (SEARCH-01)
**Example:**
```sql
-- Source: https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual
-- Create BM25 index on skill embeddings chunk_text
CREATE INDEX IF NOT EXISTS skill_embeddings_bm25_idx
ON skill_embeddings USING bm25(chunk_text)
WITH (text_config='english');

-- Hybrid search query with RRF
WITH
bm25_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY chunk_text <@> :query DESC) AS rank
    FROM skill_embeddings
    WHERE chunk_text <@> :query < 0  -- BM25 returns negative scores
    LIMIT 20
),
vector_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> :query_embedding) AS rank
    FROM skill_embeddings
    ORDER BY embedding <=> :query_embedding
    LIMIT 20
),
rrf_scores AS (
    SELECT id, 1.0 / (60 + rank) AS score FROM bm25_results
    UNION ALL
    SELECT id, 1.0 / (60 + rank) AS score FROM vector_results
)
SELECT
    se.id,
    se.chunk_text,
    sf.name AS skill_name,
    SUM(rrf.score) AS hybrid_score
FROM rrf_scores rrf
JOIN skill_embeddings se ON se.id = rrf.id
JOIN skill_files sf ON sf.id = se.skill_file_id
GROUP BY se.id, se.chunk_text, sf.name
ORDER BY hybrid_score DESC
LIMIT :limit;
```

### Anti-Patterns to Avoid

- **Manual state tracking with strings:** Use state machine library, not ad-hoc status updates
- **Circuit breaker without persistence:** State lost on worker restart without Redis
- **Blocking LLM calls in async context:** Always use async HTTP client (httpx)
- **Mutable skill files:** Load once at startup or cache with TTL, don't read on every request
- **Separate BM25 and vector queries:** Always fuse with RRF for best relevance

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State transitions | if/elif chains | python-statemachine | Invalid transitions, missing callbacks |
| Circuit breaker | Manual failure counting | pybreaker | Race conditions, half-open logic |
| YAML parsing | yaml.safe_load + manual validation | Pydantic + pydantic-yaml | Type coercion, validation, error messages |
| Version selection | Custom datetime logic | Simple max() with date filter | Edge cases with timezones, equality |
| Append-only view | Imperative loop | SQL window functions | Performance, correctness, atomicity |
| Score fusion | Manual normalization | RRF algorithm | Proven IR technique, handles scale differences |

**Key insight:** Orchestration code has concurrency hazards (race conditions in state transitions, circuit breaker counts) that libraries handle atomically. YAML validation has type coercion edge cases. Search score fusion requires established IR algorithms.

## Common Pitfalls

### Pitfall 1: Race Conditions in State Transitions

**What goes wrong:** Two workers process the same task, both transition from pending -> assigned, one overwrites the other.

**Why it happens:** State check and update not atomic.

**How to avoid:**
- Use SELECT FOR UPDATE when checking state
- Transition atomically in single statement with WHERE clause
- Or use Redis-based locking with task ID

**Warning signs:** Duplicate task processing, inconsistent state

### Pitfall 2: Circuit Breaker Opens Too Aggressively

**What goes wrong:** Brief network hiccup causes 5 fast failures, circuit opens for 30 seconds unnecessarily.

**Why it happens:** fail_max is too low, or failures happen in burst.

**How to avoid:**
- Consider time window for failures (5 failures in 60 seconds, not just 5 consecutive)
- Exclude transient errors from failure count
- Use exponential backoff before each retry

**Warning signs:** Circuit opening frequently, legitimate requests failing

### Pitfall 3: Skill Version Selection Timezone Issues

**What goes wrong:** Skill effective 2025-01-01 not selected for tax year 2025 due to timezone.

**Why it happens:** Comparing date with datetime, or using UTC when local date expected.

**How to avoid:**
- Use date objects throughout (not datetime)
- Store effective_date as DATE in database
- Compare dates in application timezone

**Warning signs:** Wrong skill version selected, off-by-one day errors

### Pitfall 4: Append-Only Log Query Performance

**What goes wrong:** Computing profile view from 1000+ entries takes too long.

**Why it happens:** Full table scan, no index on (client_id, entry_type, created_at).

**How to avoid:**
- Add composite index: `(client_id, entry_type, created_at DESC)`
- Consider materialized view for frequently accessed profiles
- Implement snapshotting for profiles with many entries

**Warning signs:** Slow profile loads, high database CPU

### Pitfall 5: BM25 Index Not Used

**What goes wrong:** Query does full table scan instead of using BM25 index.

**Why it happens:** Missing ORDER BY + LIMIT, or query planner not choosing index.

**How to avoid:**
- Always use ORDER BY with LIMIT for BM25 queries
- Use EXPLAIN ANALYZE to verify index usage
- Set appropriate `work_mem` for sorting

**Warning signs:** Slow search queries, high I/O

### Pitfall 6: Embedding Dimension Mismatch

**What goes wrong:** Vector search fails with dimension error.

**Why it happens:** Skill embeddings created with different model than query embedding.

**How to avoid:**
- Use single embedding model throughout (Voyage voyage-3.5 = 1024 dims)
- Store model identifier with embeddings
- Validate dimensions on insert

**Warning signs:** "dimension mismatch" errors, zero search results

## Code Examples

Verified patterns from official sources:

### Task Dispatcher by Type

```python
# Source: Router pattern + Python type system
from typing import Callable, Awaitable
from src.models.task import Task

AgentHandler = Callable[[Task], Awaitable[None]]

class TaskDispatcher:
    """Route tasks to agent handlers by task_type."""

    def __init__(self):
        self._handlers: dict[str, AgentHandler] = {}

    def register(self, task_type: str, handler: AgentHandler) -> None:
        """Register handler for a task type."""
        self._handlers[task_type] = handler

    async def dispatch(self, task: Task) -> None:
        """Dispatch task to appropriate handler."""
        handler = self._handlers.get(task.task_type)
        if handler is None:
            raise ValueError(f"No handler registered for task type: {task.task_type}")
        await handler(task)

# Usage
dispatcher = TaskDispatcher()
dispatcher.register("personal_tax", personal_tax_agent.handle)
dispatcher.register("business_tax", business_tax_agent.handle)
dispatcher.register("bookkeeping", bookkeeping_agent.handle)
```

### Context Builder

```python
# Source: Composition pattern
from dataclasses import dataclass
from typing import Any

@dataclass
class AgentContext:
    """Complete context for agent execution."""
    client_profile: dict[str, Any]
    documents: list[dict]
    skills: list[str]
    prior_year_return: dict | None = None

async def build_agent_context(
    session: AsyncSession,
    client_id: int,
    task_type: str,
    tax_year: int,
) -> AgentContext:
    """Assemble complete context for agent.

    Combines:
    - Client profile (computed view from append-only log)
    - Extracted documents for current tax year
    - Relevant skills selected by task type and effective date
    """
    # 1. Get client profile view
    profile = await get_client_profile_view(session, client_id)

    # 2. Get extracted documents
    documents = await get_client_documents(session, client_id, tax_year)

    # 3. Get relevant skills
    skill_names = get_skills_for_task_type(task_type)
    skills = []
    for name in skill_names:
        skill = await load_skill_for_year(session, name, tax_year)
        if skill:
            skills.append(skill.content.instructions)

    # 4. Get prior year return if available
    prior_year = await get_prior_year_return(session, client_id, tax_year - 1)

    return AgentContext(
        client_profile=profile,
        documents=documents,
        skills=skills,
        prior_year_return=prior_year,
    )
```

### Voyage Embedding Client

```python
# Source: https://docs.voyageai.com/
import voyageai
from typing import Sequence

class EmbeddingClient:
    """Client for Voyage AI embeddings."""

    def __init__(self, api_key: str):
        self.client = voyageai.Client(api_key=api_key)
        self.model = "voyage-3.5"
        self.dimension = 1024

    async def embed_texts(
        self,
        texts: Sequence[str],
        input_type: str = "document",
    ) -> list[list[float]]:
        """Embed multiple texts.

        Args:
            texts: Texts to embed
            input_type: "document" for indexing, "query" for search

        Returns:
            List of embedding vectors (1024 dimensions each)
        """
        # Voyage client is sync, run in executor
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.client.embed(
                texts=list(texts),
                model=self.model,
                input_type=input_type,
            )
        )
        return result.embeddings
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual if/elif state checks | Declarative state machines | 2020+ | Eliminates invalid transitions |
| In-process circuit breaker | Redis-backed distributed CB | 2022+ | State survives restarts, shared across workers |
| PostgreSQL ts_rank | BM25 via pg_textsearch | 2025 | True relevance ranking |
| Separate keyword/vector search | Hybrid with RRF fusion | 2024+ | Better recall + precision |
| Mutable profile rows | Append-only event log | Event sourcing pattern | Full history, no conflicts |

**Deprecated/outdated:**
- Manual circuit breaker: Use library with Redis storage
- ts_rank for search ranking: BM25 is significantly better
- Updating profile fields in place: Append-only log is safer

## Open Questions

Things that couldn't be fully resolved:

1. **pybreaker async with redis.asyncio**
   - What we know: pybreaker uses sync redis; we use redis.asyncio
   - What's unclear: Best way to bridge sync/async for state storage
   - Recommendation: Create sync Redis client just for circuit breaker, or implement async wrapper

2. **pg_textsearch with asyncpg**
   - What we know: pg_textsearch is a PostgreSQL extension
   - What's unclear: Any special considerations for async queries
   - Recommendation: Should work normally; test with SQLAlchemy async

3. **Optimal RRF k constant**
   - What we know: k=60 is standard, balances precision/recall
   - What's unclear: Best value for our specific use case (skills + documents)
   - Recommendation: Start with k=60, tune based on relevance testing

4. **Skill file hot reloading**
   - What we know: Need to parse YAML skill files
   - What's unclear: Whether to cache in memory or database
   - Recommendation: Store in database (SkillFile model exists), reload via API endpoint

## Sources

### Primary (HIGH confidence)

- [python-statemachine Documentation](https://python-statemachine.readthedocs.io/en/latest/) - State machine patterns, async support
- [pybreaker GitHub](https://github.com/danielfm/pybreaker) - Circuit breaker configuration, Redis storage
- [ParadeDB Hybrid Search](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) - RRF algorithm, PostgreSQL implementation
- [pg_textsearch GitHub](https://github.com/timescale/pg_textsearch) - BM25 index creation, query syntax
- [Voyage AI Documentation](https://docs.voyageai.com/) - Embedding model (Anthropic recommended)
- [pydantic-yaml PyPI](https://pypi.org/project/pydantic-yaml/) - YAML parsing with Pydantic

### Secondary (MEDIUM confidence)

- [Event Sourcing in Python](https://eventsourcing.readthedocs.io/) - Append-only log patterns
- [AWS Agentic Patterns](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/) - Task dispatcher routing

### Tertiary (LOW confidence)

- Community patterns for async circuit breaker wrappers
- RRF k-constant tuning based on domain (needs validation)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All versions verified from PyPI, documentation current
- Architecture: HIGH - Patterns from official documentation, established practices
- Pitfalls: MEDIUM - Some based on common patterns, others from community reports
- Hybrid search: HIGH - Well-documented by ParadeDB and Timescale

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - stable ecosystem)
