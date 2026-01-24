# Project State: Rookie

**Last Updated:** 2026-01-24
**Current Phase:** 2 - Core Framework
**Status:** In Progress

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-23)

**Core value:** CPAs are liable for the work, not the AI. Rookie prepares, humans approve.

**Current focus:** Phase 2 - Core Framework

## Phase Progress

| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1 - Foundation | Complete | 5/5 | 100% |
| 2 - Core Framework | In Progress | 1/6 | 17% |
| 3 - Personal Tax Simple | Pending | 0/0 | 0% |
| 4 - Personal Tax Complex | Pending | 0/0 | 0% |
| 5 - Review Infrastructure | Pending | 0/0 | 0% |
| 6 - Business Tax | Pending | 0/0 | 0% |
| 7 - Bookkeeping | Pending | 0/0 | 0% |
| 8 - Production Hardening | Pending | 0/0 | 0% |

**Overall Progress:** [##______] 15%

## Current Position

- **Phase:** 2 of 8 (Core Framework)
- **Plan:** 02-02 complete, 02-01 in parallel
- **Status:** In Progress
- **Last activity:** 2026-01-24 - Completed 02-02-PLAN.md (Task Dispatcher)

## Performance Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Plans completed | 6 | - |
| Requirements delivered | 6/60 | 60 |
| Phases complete | 1/8 | 8 |

## Accumulated Context

### Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-23 | Start Phase 1 (Foundation) instead of Phase 0 (Golden Path) | User preference - build infrastructure first |
| 2026-01-23 | Single-firm deployment for V1 | Reduce complexity, prove value before scaling |
| 2026-01-23 | Append-only log for client profiles | Eliminates merge conflicts, provides full history |
| 2026-01-23 | Worksheet output (not Drake XML) | Avoids reverse-engineering GruntWorx schema |
| 2026-01-23 | Vision API for document extraction | Direct extraction without OCR pipeline |
| 2026-01-24 | Use uv for Python package management | Fast, modern resolver, better than pip |
| 2026-01-24 | Pydantic Settings for configuration | Type-safe, .env file support, validation |
| 2026-01-24 | Max 20 Redis connections per pool | Reasonable for single-firm deployment |
| 2026-01-24 | orjson for structlog JSON serialization | Performance, already a dependency |
| 2026-01-24 | 10% Sentry trace sampling | Balance observability cost vs insight |
| 2026-01-24 | Disable PII in Sentry | CPA data sensitivity requirement |
| 2026-01-24 | TaskStatus as Python enum | Cleaner than string constants, type safety |
| 2026-01-24 | Pool size 20, max_overflow 0 | Bounded connections prevent database overload |
| 2026-01-24 | expire_on_commit=False | Objects usable after commit in FastAPI responses |
| 2026-01-24 | Lazy engine initialization | Avoids connection at import time |
| 2026-01-24 | Async migrations with NullPool | Prevents connection leaks during migration runs |
| 2026-01-24 | pgvector via ischema_names | Autogenerate recognizes Vector type |
| 2026-01-24 | PostgreSQL 17 for local dev | pgvector Homebrew bottle compatibility |
| 2026-01-24 | LifespanManager for tests | httpx ASGITransport doesn't trigger lifespan |
| 2026-01-24 | "degraded" status for partial failure | More informative than binary ok/error |
| 2026-01-24 | Singleton with reset for dispatcher | Convenient access via get_dispatcher(), test isolation via reset_dispatcher() |
| 2026-01-24 | Handler replacement logs warning | Allows hot-reload patterns without raising exceptions |

### Deferred Items

Items explicitly moved to v2:
- Multi-tenancy (MULTI-01 to MULTI-03)
- Multi-state apportionment (ADV-01)
- Cryptocurrency handling (ADV-02)
- Wash sale tracking (ADV-03)
- Foreign income Form 2555 (ADV-04)
- Estate/Trust returns Form 1041 (ADV-05)
- SOC 2 certification (COMP-01, COMP-02)

### Known Blockers

None currently.

### TODOs

- [x] Run `/gsd:plan-phase 1` to create execution plans for Phase 1
- [x] Execute 01-01-PLAN.md (Project Scaffolding)
- [x] Execute 01-02-PLAN.md (Database Models)
- [x] Execute 01-03-PLAN.md (Infrastructure Services)
- [x] Execute 01-04-PLAN.md (Alembic Migrations)
- [x] Execute 01-05-PLAN.md (FastAPI Application)
- [x] Plan Phase 2 (Core Framework)
- [ ] Execute 02-01-PLAN.md (State Machine + Dependencies)
- [x] Execute 02-02-PLAN.md (Task Dispatcher)
- [ ] Execute 02-03-PLAN.md (Circuit Breaker)
- [ ] Execute 02-04-PLAN.md (Skill Engine)
- [ ] Execute 02-05-PLAN.md (Context Builder)
- [ ] Execute 02-06-PLAN.md (Hybrid Search)

## Recent Activity

| Date | Activity |
|------|----------|
| 2026-01-23 | Project initialized |
| 2026-01-23 | Requirements defined (60 v1 requirements) |
| 2026-01-23 | Roadmap created (8 phases) |
| 2026-01-24 | Phase 1 plans created |
| 2026-01-24 | Completed 01-01: Project Scaffolding (3 min) |
| 2026-01-24 | Completed 01-02: Database Models (4 min) |
| 2026-01-24 | Completed 01-03: Infrastructure Services (4 min) |
| 2026-01-24 | Completed 01-04: Alembic Migrations (4 min) |
| 2026-01-24 | Completed 01-05: FastAPI Application (5 min) |
| 2026-01-24 | **Phase 1 Complete** - Foundation operational |
| 2026-01-24 | Phase 2 plans created (6 plans in 4 waves) |
| 2026-01-24 | Completed 02-02: Task Dispatcher (3 min) |

## Session Continuity

### Last Session Summary

Executed 02-02-PLAN.md (Task Dispatcher):
- TaskDispatcher class with register/unregister/dispatch methods
- Handler routing by task.task_type to registered async handlers
- ValueError for unregistered task types with helpful error message
- Comprehensive test coverage with 12 passing tests

### Next Session Starting Point

Continue Phase 2 execution - remaining plans: 02-01 (parallel), 02-03, 02-04, 02-05, 02-06.

### Context to Preserve

**Tech Stack:**
- Python 3.11+ / FastAPI / PostgreSQL 15+ / pgvector / Redis
- Claude primary LLM (best reasoning + vision)
- Drake worksheets (Excel) for manual entry
- Package management: uv
- Dependencies installed: fastapi, sqlalchemy, asyncpg, alembic, redis, pgvector, structlog, sentry-sdk, pydantic-settings, orjson
- Dev dependencies: pytest, pytest-asyncio, httpx, mypy, ruff, asgi-lifespan

**Database Models (01-02):**
- `src/models/base.py` - Base, TimestampMixin
- `src/models/task.py` - Task, Escalation, TaskArtifact, TaskStatus
- `src/models/client.py` - Client, ClientProfileEntry
- `src/models/artifact.py` - FeedbackEntry, DocumentEmbedding
- `src/models/skill.py` - SkillFile, SkillEmbedding
- `src/models/log.py` - AgentLog, AgentMetric
- `src/core/database.py` - Engine factory, session maker

**Infrastructure Services (01-03):**
- `src/core/redis.py` - Redis pool factory, health check
- `src/core/logging.py` - structlog config, contextvars
- `src/core/sentry.py` - Sentry init with FastAPI integration

**Alembic Migrations (01-04):**
- `alembic.ini` - Configuration with URL from env.py
- `migrations/env.py` - Async migrations with pgvector support
- `migrations/versions/c5fc18e7c719_*.py` - Initial 11-table schema

**FastAPI Application (01-05):**
- `src/main.py` - App with lifespan context manager
- `src/api/deps.py` - get_db, get_redis dependencies
- `src/api/health.py` - Health endpoint with Pydantic response model
- `tests/test_health.py` - Integration tests with asgi-lifespan

**Key Constraints:**
- No client PII in AI training
- Only SSN last-4 stored
- Full audit trail required
- 7-year data retention for completed tasks

**Orchestration (02-02):**
- `src/orchestration/dispatcher.py` - TaskDispatcher class for routing tasks to handlers
- `tests/orchestration/test_dispatcher.py` - 12 comprehensive tests

**Critical Path:**
Phase 1 -> 2 -> 3 -> 4 -> 5 -> 7 -> 8

---

*State initialized: 2026-01-23*
*Last updated: 2026-01-24*
