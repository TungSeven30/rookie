# Project State: Rookie

**Last Updated:** 2026-01-26
**Current Phase:** 4 - Personal Tax Complex
**Status:** In Progress

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-23)

**Core value:** CPAs are liable for the work, not the AI. Rookie prepares, humans approve.

**Current focus:** Phase 3 - Personal Tax Simple

## Phase Progress

| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1 - Foundation | Complete | 5/5 | 100% |
| 2 - Core Framework | Complete | 6/6 | 100% |
| 3 - Personal Tax Simple | Complete | 7/7 | 100% |
| 4 - Personal Tax Complex | In Progress | 1/8 | 12.5% |
| 5 - Review Infrastructure | Pending | 0/0 | 0% |
| 6 - Business Tax | Pending | 0/0 | 0% |
| 7 - Bookkeeping | Pending | 0/0 | 0% |
| 8 - Production Hardening | Pending | 0/0 | 0% |

**Overall Progress:** [######__] 48%

## Current Position

- **Phase:** 4 of 8 (Personal Tax Complex)
- **Plan:** 04-02-PLAN.md (K-1 and 1099-B Extractors)
- **Status:** 04-01 Complete - Executing 04-02 next
- **Last activity:** 2026-01-26 - Completed K-1 and 1099-B Document Models

## Performance Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Plans completed | 18 | - |
| Requirements delivered | 18/60 | 60 |
| Phases complete | 3/8 | 8 |

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
| 2026-01-24 | python-statemachine model binding pattern | Binds task.status field for automatic state sync |
| 2026-01-24 | Failed state is not final (allows retry) | Enables retry workflow from failed back to pending |
| 2026-01-24 | Completed and escalated states are final | No transitions out of terminal states |
| 2026-01-24 | Custom Redis storage for circuit breaker | Cross-instance state sharing via pybreaker subclass |
| 2026-01-24 | Circuit breaker thresholds: 5/30/2 | 5 failures to open, 30s timeout, 2 successes to close |
| 2026-01-24 | Async circuit breaker call method | pybreaker sync decorators insufficient for async |
| 2026-01-24 | Two-section skill file structure | metadata + content keeps identity separate from behavior |
| 2026-01-24 | effective_date for version selection | Skills become effective on a date, selector picks most recent |
| 2026-01-24 | ruamel.yaml for YAML parsing | Preserves quotes and formatting for round-trip editing |
| 2026-01-24 | Window functions for computed view | Efficient single-query latest-per-type for profile |
| 2026-01-24 | Append-only log for profile entries | Never update existing entries, always append |
| 2026-01-24 | TASK_TYPE_SKILLS mapping | Central mapping of task types to required skills |
| 2026-01-24 | Mock mode for embedding client | Testing without Voyage AI API key using deterministic vectors |
| 2026-01-24 | RRF_K=60 for fusion | Standard value from Reciprocal Rank Fusion literature |
| 2026-01-24 | GIN index on chunk_text | Efficient full-text search on skill embeddings |
| 2026-01-24 | Decimal for monetary fields | Float precision issues with currency calculations |
| 2026-01-24 | SSN format XXX-XX-XXXX | Standard IRS format, consistent storage |
| 2026-01-24 | EIN format XX-XXXXXXX | Standard IRS format for employer IDs |
| 2026-01-24 | ConfidenceLevel enum | Extraction quality indicator for human review |
| 2026-01-24 | uncertain_fields list | Identifies fields needing human verification |
| 2026-01-24 | Mock mode via MOCK_LLM env var | Enable testing without Anthropic API key |
| 2026-01-24 | Confidence weights 0.3/0.4/0.3 | Field validation is most objective measure |
| 2026-01-24 | HIGH requires all critical fields | Missing critical data should never be auto-approved |
| 2026-01-24 | Decimal for all monetary values | Float precision issues with currency calculations |
| 2026-01-24 | Dataclasses for tax structures | Simple, immutable data containers |
| 2026-01-24 | Constants indexed by (year, status) | Easy to add new tax years |
| 2026-01-24 | CTC phaseout rounds up to $1,000 | IRS rounds up when calculating reduction |
| 2026-01-24 | EITC simplified for no-children | Full EITC tables complex, defer to v2 |
| 2026-01-24 | Variance threshold >10% (not >=) | Must exceed threshold to flag |

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
- [x] Execute 02-01-PLAN.md (State Machine + Dependencies)
- [x] Execute 02-02-PLAN.md (Task Dispatcher)
- [x] Execute 02-03-PLAN.md (Circuit Breaker)
- [x] Execute 02-04-PLAN.md (Skill Engine)
- [x] Execute 02-05-PLAN.md (Context Builder)
- [x] Execute 02-06-PLAN.md (Hybrid Search)
- [x] Plan Phase 3 (Personal Tax Simple)
- [x] Execute 03-01-PLAN.md (Tax Document Models)
- [x] Execute 03-02-PLAN.md (Storage & Scanner)
- [x] Execute 03-03-PLAN.md (Classifier & Confidence)
- [x] Execute 03-04-PLAN.md (Document Extractor)
- [x] Execute 03-05-PLAN.md (Tax Calculator)
- [x] Execute 03-06-PLAN.md (Output Generators)
- [x] Execute 03-07-PLAN.md (Personal Tax Agent)
- [x] Plan Phase 4 (Personal Tax Complex)
- [x] Execute 04-01-PLAN.md (K-1 and 1099-B Document Models)
- [ ] Execute 04-02-PLAN.md (K-1 and 1099-B Extractors)
- [ ] Execute 04-03-PLAN.md (Schedule C Calculator)
- [ ] Execute 04-04-PLAN.md (Schedule E Calculator)
- [ ] Execute 04-05-PLAN.md (Schedule D Calculator)
- [ ] Execute 04-06-PLAN.md (QBI Deduction)
- [ ] Execute 04-07-PLAN.md (Form 8962 ACA Reconciliation)
- [ ] Execute 04-08-PLAN.md (Complex Return Agent Integration)

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
| 2026-01-24 | Completed 02-01: State Machine (4 min) |
| 2026-01-24 | Completed 02-03: Circuit Breaker (4 min) |
| 2026-01-24 | Completed 02-04: Skill Engine (7 min) |
| 2026-01-24 | Completed 02-05: Context Builder (6 min) |
| 2026-01-24 | Completed 02-06: Hybrid Search (5 min) |
| 2026-01-24 | **Phase 2 Complete** - Core Framework operational |
| 2026-01-24 | Phase 3 plans created (7 plans) |
| 2026-01-24 | Completed 03-01: Tax Document Models (5 min) |
| 2026-01-24 | Completed 03-02: Storage & Scanner (5 min) |
| 2026-01-24 | Completed 03-03: Classifier & Confidence (10 min) |
| 2026-01-24 | Completed 03-04: Document Extractor (5 min) |
| 2026-01-24 | Completed 03-05: Tax Calculator with Credits (10 min) |
| 2026-01-24 | Completed 03-06: Output Generators (5 min) |
| 2026-01-25 | Completed 03-07: Personal Tax Agent (5 min) |
| 2026-01-25 | **Phase 3 Complete** - Personal Tax Simple operational |
| 2026-01-26 | Completed 04-01: K-1 and 1099-B Document Models (5 min) |

## Session Continuity

### Last Session Summary

Completed 04-01-PLAN.md: K-1 and 1099-B Document Models:
- Added FORM_K1, FORM_1099_B, FORM_1095_A to DocumentType enum
- Created FormK1 model with all K-1 boxes, capital account tracking, debt basis fields
- Created Form1099B model for broker transactions with basis_reported_to_irs flag
- Created Form1099BSummary model for high-volume statements (Form 8949 categories A/B/D/E)
- Created Form1095A model for ACA marketplace statements
- Added requires_basis_escalation property to FormK1 and Form1099B
- Updated CRITICAL_FIELDS in confidence.py for new document types
- Added get_critical_fields_for_1099b() for conditional cost_basis validation
- Updated classifier prompt to recognize K-1, 1099-B, 1095-A
- Created 38 comprehensive tests for new models
- Updated module exports in __init__.py

**04-01 Complete** - 219 document tests passing.

### Next Session Starting Point

Execute 04-02-PLAN.md (K-1 and 1099-B Extractors) - Add extraction prompts and functions for K-1, 1099-B, and 1095-A documents.

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

**Orchestration (02-01, 02-02, 02-03):**
- `src/orchestration/state_machine.py` - TaskStateMachine class with model binding
- `src/orchestration/dispatcher.py` - TaskDispatcher class for routing tasks to handlers
- `src/orchestration/circuit_breaker.py` - CircuitBreaker with Redis persistence
- `tests/orchestration/test_state_machine.py` - 17 comprehensive tests
- `tests/orchestration/test_dispatcher.py` - 12 comprehensive tests
- `tests/orchestration/test_circuit_breaker.py` - 23 comprehensive tests

**Skill Engine (02-04):**
- `src/skills/models.py` - Pydantic models for skill files
- `src/skills/loader.py` - YAML skill file parser with validation
- `src/skills/selector.py` - Version selector by effective_date
- `skills/example_skill.yaml` - W-2 processing skill example
- `tests/skills/test_loader.py` - 23 loader tests
- `tests/skills/test_selector.py` - 26 selector tests

**Context Builder (02-05):**
- `src/context/__init__.py` - Module exports
- `src/context/profile.py` - Profile service with append-only log pattern
- `src/context/builder.py` - Context assembly with AgentContext dataclass
- `tests/context/test_profile.py` - 18 profile service tests
- `tests/context/test_builder.py` - 24 context builder tests

**Hybrid Search (02-06):**
- `src/search/__init__.py` - Module exports
- `src/search/embeddings.py` - Voyage AI client with mock mode
- `src/search/hybrid.py` - Semantic search, keyword search, RRF fusion
- `tests/search/test_embeddings.py` - 16 embedding client tests
- `tests/search/test_hybrid.py` - 14 RRF and SearchResult tests
- `migrations/versions/83c01ef4c8fc_*.py` - Full-text search GIN index

**Phase 2 Dependencies Added:**
- python-statemachine, pybreaker, pydantic-yaml, ruamel.yaml, voyageai

**Document Models (03-01, 04-01):**
- `src/documents/__init__.py` - Module exports
- `src/documents/models.py` - W2Data, Form1099INT, Form1099DIV, Form1099NEC, FormK1, Form1099B, Form1099BSummary, Form1095A models
- `src/documents/confidence.py` - CRITICAL_FIELDS + get_critical_fields_for_1099b() for conditional validation
- `tests/documents/test_models.py` - 84 model tests (including 38 new K-1/1099-B tests)

**Storage Integration (03-02):**
- `src/integrations/__init__.py` - Module exports
- `src/integrations/storage.py` - fsspec wrapper (get_filesystem, list_files, read_file)
- `src/documents/scanner.py` - ClientDocument + scan_client_folder
- `tests/integrations/test_storage.py` - 18 storage tests
- `tests/documents/test_scanner.py` - 23 scanner tests

**Document Classifier & Confidence (03-03):**
- `src/documents/classifier.py` - ClassificationResult + classify_document()
- `src/documents/confidence.py` - ConfidenceResult + calculate_confidence()
- Mock mode via MOCK_LLM=true environment variable
- CRITICAL_FIELDS by document type (W2, 1099-INT, 1099-DIV, 1099-NEC)
- `tests/documents/test_classifier.py` - 26 classifier tests
- `tests/documents/test_confidence.py` - 39 confidence tests

**Document Extractor (03-04):**
- `src/documents/extractor.py` - extract_document() + type-specific extractors
- `src/documents/prompts.py` - detailed extraction prompts for each form type
- Uses instructor.from_anthropic() for validated Pydantic output
- Model: claude-sonnet-4-5-20250514, 2048 max tokens
- Mock mode via MOCK_LLM=true with realistic test data
- `tests/documents/test_extractor.py` - 33 extractor tests

**Tax Calculator (03-05):**
- `src/agents/__init__.py` - Agent package marker
- `src/agents/personal_tax/__init__.py` - Module exports
- `src/agents/personal_tax/calculator.py` - Pure tax calculation functions
- Data structures: IncomeSummary, DeductionResult, TaxSituation, CreditItem, CreditsResult, TaxResult, VarianceItem
- Functions: aggregate_income, get_standard_deduction, calculate_deductions, evaluate_credits, calculate_tax, compare_years
- Credits: CTC ($2k/child with phaseout), AOC (up to $2,500), Saver's Credit (10-50%), EITC (simplified)
- Tax brackets: 2024 rates for single, mfj, mfs, hoh
- `tests/agents/personal_tax/test_calculator.py` - 72 tests

**Output Generators (03-06):**
- `src/agents/personal_tax/output.py` - Drake worksheet and preparer notes generators
- generate_drake_worksheet() creates Excel with Summary, W-2 Income, 1099-INT, 1099-DIV, 1099-NEC sheets
- generate_preparer_notes() creates Markdown with Summary, Sources, Flags, Assumptions, Review Focus
- Both exported from personal_tax module __init__.py
- `tests/agents/personal_tax/test_output.py` - 30 tests

**Personal Tax Agent (03-07):**
- `src/agents/personal_tax/agent.py` - PersonalTaxAgent class orchestrating complete workflow
- PersonalTaxResult dataclass with outputs, calculations, and confidence
- EscalationRequired exception for human intervention
- personal_tax_handler for TaskDispatcher integration
- Workflow: context -> scan -> classify -> extract -> missing check -> conflict check -> calculate -> compare -> generate
- `tests/agents/personal_tax/test_agent.py` - 30 tests

**Phase 3 Dependencies Added:**
- anthropic, instructor, openpyxl, fsspec

**Phase 4 Plan Structure:**
- Wave 1: 04-01 (Document Models) + 04-02 (Extractors) - parallel
- Wave 2: 04-03 (Schedule C + SE Tax)
- Wave 3: 04-04 (Schedule E) + 04-05 (Schedule D) - parallel
- Wave 4: 04-06 (QBI) + 04-07 (Form 8962/PTC) - parallel
- Wave 5: 04-08 (Agent Integration)

**Critical Path:**
Phase 1 -> 2 -> 3 -> 4 -> 5 -> 7 -> 8

---

*State initialized: 2026-01-23*
*Last updated: 2026-01-26*
