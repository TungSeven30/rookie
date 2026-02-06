# Requirements: Rookie

**Defined:** 2026-01-23
**Core Value:** CPAs are liable for the work, not the AI. Rookie prepares, humans approve.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Infrastructure

- [ ] **INFRA-01**: FastAPI server with /api/health endpoint returning db/redis connection status
- [ ] **INFRA-02**: PostgreSQL database with all schema tables (tasks, clients, profiles, artifacts, feedback, skills, logs)
- [ ] **INFRA-03**: Redis connection pool for job queue, real-time status, and circuit breaker state
- [ ] **INFRA-04**: Structured JSON logging with task_id, client_id, agent, timestamp, level, message
- [ ] **INFRA-05**: Error tracking integration capturing unhandled exceptions with stack traces
- [ ] **INFRA-06**: Database migrations run without error (Alembic)

### Orchestration

- [ ] **ORCH-01**: Task state machine transitions correctly through all states (pending → assigned → in_progress → completed/failed/escalated)
- [ ] **ORCH-02**: Task dispatcher routes tasks to correct agent by task_type
- [ ] **ORCH-03**: Circuit breaker opens after 5 consecutive LLM failures
- [ ] **ORCH-04**: Circuit breaker closes after 30 seconds recovery timeout
- [ ] **ORCH-05**: Circuit breaker requires 2 successes in half-open state before closing

### Skills & Context

- [ ] **SKILL-01**: Skill engine parses all skill YAML files without error
- [ ] **SKILL-02**: Skill engine selects correct version by effective_date for tax year
- [ ] **SKILL-03**: Context builder assembles client profile + documents + skills for agent
- [ ] **SKILL-04**: Client profile append-only log maintains integrity after 100+ writes
- [ ] **SKILL-05**: Client profile computed view derives current state from log

### Search

- [ ] **SEARCH-01**: Hybrid search combining pgvector (semantic) + pg_textsearch (BM25 keyword)

### Document Processing

- [ ] **DOC-01**: Vision API extracts all fields from W-2 with >95% accuracy
- [ ] **DOC-02**: Vision API extracts all fields from 1099-INT with >95% accuracy
- [ ] **DOC-03**: Vision API extracts all fields from 1099-DIV with >95% accuracy
- [ ] **DOC-04**: Vision API extracts all fields from 1099-NEC with >95% accuracy
- [ ] **DOC-05**: Vision API extracts all fields from K-1 with >90% accuracy
- [ ] **DOC-06**: Document classifier correctly identifies document type
- [ ] **DOC-07**: Confidence scoring evaluates extraction reliability (HIGH/MEDIUM/LOW)

### Personal Tax Agent

- [ ] **PTAX-01**: Agent loads client profile and prior year return before starting
- [ ] **PTAX-02**: Agent scans client folder for current year documents
- [ ] **PTAX-03**: Agent aggregates income from all extracted documents
- [ ] **PTAX-04**: Agent calculates deductions (standard vs itemized comparison)
- [ ] **PTAX-05**: Agent evaluates applicable credits
- [ ] **PTAX-06**: Agent computes tax liability using correct brackets
- [ ] **PTAX-07**: Agent handles Schedule C (self-employment income/expenses)
- [ ] **PTAX-08**: Agent handles Schedule E (rental income)
- [ ] **PTAX-09**: Agent handles Schedule D (capital gains - basic)
- [ ] **PTAX-10**: Agent calculates QBI deduction correctly
- [ ] **PTAX-11**: Agent handles Form 8962 ACA reconciliation (Premium Tax Credit)
- [ ] **PTAX-12**: Agent compares current vs prior year, flags variances >10%
- [ ] **PTAX-13**: Agent generates Drake worksheet (Excel) with >95% field accuracy
- [ ] **PTAX-14**: Agent generates preparer notes (Markdown) with all required sections
- [ ] **PTAX-15**: Agent escalates when required document missing
- [ ] **PTAX-16**: Agent escalates on conflicting information

### Business Tax Agent

- [ ] **BTAX-01**: Agent processes 1120-S returns
- [ ] **BTAX-02**: Agent generates K-1 worksheets for shareholders
- [ ] **BTAX-03**: Agent tracks shareholder basis accurately
- [ ] **BTAX-04**: Agent extracts trial balance from source documents
- [ ] **BTAX-05**: Schedule L (balance sheet) reconciles to trial balance
- [ ] **BTAX-06**: K-1 data flows correctly to Personal Tax Agent context via handoff protocol

### Bookkeeping Agent

- [ ] **BOOK-01**: Agent categorizes transactions with >90% accuracy
- [ ] **BOOK-02**: QuickBooks Online API reads transactions successfully
- [ ] **BOOK-03**: QuickBooks Online API writes categorizations successfully
- [ ] **BOOK-04**: Agent detects anomalies (transactions >2σ from historical pattern)
- [ ] **BOOK-05**: Agent generates reconciliation reports

### Checker Agent

Phase 5 execution status: backend implementation in progress (2026-02-06).

- [ ] **CHECK-01**: Agent verifies numbers against source documents
- [ ] **CHECK-02**: Agent identifies 95% of intentionally injected errors
- [ ] **CHECK-03**: Agent analyzes variances from prior year
- [ ] **CHECK-04**: Agent flags items without documented reasons
- [ ] **CHECK-05**: Agent cannot approve — only flags for human review

### Feedback System

- [ ] **FEED-01**: Implicit feedback captures 100% of CPA changes (diff)
- [ ] **FEED-02**: Explicit feedback tags captured with <3 clicks
- [ ] **FEED-03**: Feedback entries stored with task_id, reviewer_id, timestamps
- [ ] **FEED-04**: Feedback includes original_content, corrected_content, diff_summary

### Status & Dashboard

- [ ] **DASH-01**: Real-time task status API returns current progress
- [ ] **DASH-02**: Agent status API shows active tasks per agent
- [ ] **DASH-03**: Dashboard displays queue depth and completion counts
- [ ] **DASH-04**: Dashboard shows flags requiring attention
- [ ] **DASH-05**: Dashboard meets WCAG 2.1 AA accessibility standards

### Integrations

- [ ] **INT-01**: TaxDome webhook processes task assignments
- [ ] **INT-02**: TaxDome API updates task status
- [ ] **INT-03**: QuickBooks Online OAuth connector handles token refresh
- [ ] **INT-04**: Client folder scanner lists documents from cloud storage

### Production Hardening

- [ ] **PROD-01**: System handles 10 concurrent tasks without degradation
- [ ] **PROD-02**: Recovery from agent crash within 2 minutes
- [ ] **PROD-03**: All security vulnerabilities addressed
- [ ] **PROD-04**: Backup/restore tested successfully
- [ ] **PROD-05**: Operational runbook covers 10 most common issues

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Multi-tenancy

- **MULTI-01**: Tenant isolation for multiple CPA firms
- **MULTI-02**: Per-tenant configuration and branding
- **MULTI-03**: Tenant-scoped data access controls

### Advanced Tax Scenarios

- **ADV-01**: Multi-state apportionment
- **ADV-02**: Cryptocurrency handling
- **ADV-03**: Wash sale tracking
- **ADV-04**: Foreign income (Form 2555)
- **ADV-05**: Estate/Trust returns (Form 1041)

### Compliance

- **COMP-01**: SOC 2 Type I certification
- **COMP-02**: SOC 2 Type II certification

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Drake XML import | Requires reverse-engineering GruntWorx schema; worksheets sufficient for V1 |
| Mobile dashboard | Desktop-first for CPA workflow |
| Automated client communication | Humans should control client-facing messages |
| Fine-tuning/RLHF | Prompt engineering and RAG sufficient for V1 |
| Payroll processing | Out of domain; integrate with existing payroll providers |
| Real-time chat | High complexity, not core to accounting value |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| INFRA-06 | Phase 1 | Pending |
| ORCH-01 | Phase 2 | Pending |
| ORCH-02 | Phase 2 | Pending |
| ORCH-03 | Phase 2 | Pending |
| ORCH-04 | Phase 2 | Pending |
| ORCH-05 | Phase 2 | Pending |
| SKILL-01 | Phase 2 | Pending |
| SKILL-02 | Phase 2 | Pending |
| SKILL-03 | Phase 2 | Pending |
| SKILL-04 | Phase 2 | Pending |
| SKILL-05 | Phase 2 | Pending |
| SEARCH-01 | Phase 2 | Pending |
| DOC-01 | Phase 3 | Pending |
| DOC-02 | Phase 3 | Pending |
| DOC-03 | Phase 3 | Pending |
| DOC-04 | Phase 3 | Pending |
| DOC-05 | Phase 4 | Pending |
| DOC-06 | Phase 3 | Pending |
| DOC-07 | Phase 3 | Pending |
| PTAX-01 | Phase 3 | Pending |
| PTAX-02 | Phase 3 | Pending |
| PTAX-03 | Phase 3 | Pending |
| PTAX-04 | Phase 3 | Pending |
| PTAX-05 | Phase 3 | Pending |
| PTAX-06 | Phase 3 | Pending |
| PTAX-07 | Phase 4 | Pending |
| PTAX-08 | Phase 4 | Pending |
| PTAX-09 | Phase 4 | Pending |
| PTAX-10 | Phase 4 | Pending |
| PTAX-11 | Phase 4 | Pending |
| PTAX-12 | Phase 3 | Pending |
| PTAX-13 | Phase 3 | Pending |
| PTAX-14 | Phase 3 | Pending |
| PTAX-15 | Phase 3 | Pending |
| PTAX-16 | Phase 3 | Pending |
| BTAX-01 | Phase 6 | Pending |
| BTAX-02 | Phase 6 | Pending |
| BTAX-03 | Phase 6 | Pending |
| BTAX-04 | Phase 6 | Pending |
| BTAX-05 | Phase 6 | Pending |
| BTAX-06 | Phase 6 | Pending |
| BOOK-01 | Phase 7 | Pending |
| BOOK-02 | Phase 7 | Pending |
| BOOK-03 | Phase 7 | Pending |
| BOOK-04 | Phase 7 | Pending |
| BOOK-05 | Phase 7 | Pending |
| CHECK-01 | Phase 5 | In Progress |
| CHECK-02 | Phase 5 | In Progress |
| CHECK-03 | Phase 5 | In Progress |
| CHECK-04 | Phase 5 | In Progress |
| CHECK-05 | Phase 5 | In Progress |
| FEED-01 | Phase 5 | In Progress |
| FEED-02 | Phase 5 | In Progress |
| FEED-03 | Phase 5 | In Progress |
| FEED-04 | Phase 5 | In Progress |
| DASH-01 | Phase 5 | In Progress |
| DASH-02 | Phase 5 | In Progress |
| DASH-03 | Phase 5 | In Progress |
| DASH-04 | Phase 5 | In Progress |
| DASH-05 | Phase 5 | In Progress |
| INT-01 | Phase 5 | In Progress |
| INT-02 | Phase 5 | In Progress |
| INT-03 | Phase 7 | Pending |
| INT-04 | Phase 3 | Pending |
| PROD-01 | Phase 8 | Pending |
| PROD-02 | Phase 8 | Pending |
| PROD-03 | Phase 8 | Pending |
| PROD-04 | Phase 8 | Pending |
| PROD-05 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 61 total
- Mapped to phases: 61
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-23*
*Last updated: 2026-01-23 after initial definition*
