# Roadmap: Rookie

**Created:** 2026-01-23
**Phases:** 8
**Core Value:** CPAs are liable for the work, not the AI. Rookie prepares, humans approve.

## Overview

| Phase | Name | Goal | Requirements |
|-------|------|------|--------------|
| 1 | Foundation | Infrastructure operational with observability from Day 1 | INFRA-01 to INFRA-06 |
| 2 | Core Framework | Production-ready orchestration and shared services | ORCH-01 to ORCH-05, SKILL-01 to SKILL-05, SEARCH-01 |
| 3 | Personal Tax - Simple | Prepare W-2-only 1040 returns with CPA-quality output | DOC-01 to DOC-04, DOC-06, DOC-07, PTAX-01 to PTAX-06, PTAX-12 to PTAX-16, INT-04 |
| 4 | Personal Tax - Complex | Handle Schedule C, E, D, Form 8962, and common complexities | DOC-05, PTAX-07 to PTAX-11 |
| 5 | Review Infrastructure | Feedback loop and quality verification operational | CHECK-01 to CHECK-05, FEED-01 to FEED-04, DASH-01 to DASH-05, INT-01, INT-02 |
| 6 | Business Tax | 1120-S returns with K-1 generation | BTAX-01 to BTAX-06 |
| 7 | Bookkeeping | Transaction categorization with QBO integration | BOOK-01 to BOOK-05, INT-03 |
| 8 | Production Hardening | Ready for pilot deployment | PROD-01 to PROD-05 |

## Phase Dependency Map

```
Phase 1 (Foundation)
    |
    v
Phase 2 (Core Framework)
    |
    v
Phase 3 (PT Simple)
    |
    v
Phase 4 (PT Complex)
    |
    +---> Phase 5 (Review Infrastructure)
    |         |
    +---> Phase 6 (Business Tax)
              |
              v
          Phase 7 (Bookkeeping)
              |
              v
          Phase 8 (Production Hardening)
```

**Critical Path:** 1 -> 2 -> 3 -> 4 -> 5 -> 7 -> 8

---

## Phase Details

### Phase 1: Foundation

**Goal:** Infrastructure operational with observability from Day 1.

**Requirements:**
- INFRA-01: FastAPI server with /api/health endpoint returning db/redis connection status
- INFRA-02: PostgreSQL database with all schema tables (tasks, clients, profiles, artifacts, feedback, skills, logs)
- INFRA-03: Redis connection pool for job queue, real-time status, and circuit breaker state
- INFRA-04: Structured JSON logging with task_id, client_id, agent, timestamp, level, message
- INFRA-05: Error tracking integration capturing unhandled exceptions with stack traces
- INFRA-06: Database migrations run without error (Alembic)

**Success Criteria:**
1. FastAPI health endpoint returns `{"status": "ok", "db": "connected", "redis": "connected"}`
2. PostgreSQL migrations run without error
3. Redis connection pool established and responding
4. Structured logging outputs JSON with task_id, timestamp, level, message
5. Error tracking captures unhandled exceptions with stack traces

**Dependencies:** None (first phase)

**Rollback:** If Redis unreliable, fall back to in-memory queue for dev.

**Plans:** 5 plans in 4 waves

Plans:
- [x] 01-01-PLAN.md — Project scaffolding and Pydantic configuration
- [x] 01-02-PLAN.md — SQLAlchemy models and database utilities
- [x] 01-03-PLAN.md — Redis, structlog, and Sentry infrastructure
- [x] 01-04-PLAN.md — Alembic migrations with pgvector support
- [x] 01-05-PLAN.md — FastAPI app with health endpoint

---

### Phase 2: Core Framework

**Goal:** Production-ready orchestration and shared services.

**Requirements:**
- ORCH-01: Task state machine transitions correctly through all states (pending -> assigned -> in_progress -> completed/failed/escalated)
- ORCH-02: Task dispatcher routes tasks to correct agent by task_type
- ORCH-03: Circuit breaker opens after 5 consecutive LLM failures
- ORCH-04: Circuit breaker closes after 30 seconds recovery timeout
- ORCH-05: Circuit breaker requires 2 successes in half-open state before closing
- SKILL-01: Skill engine parses all skill YAML files without error
- SKILL-02: Skill engine selects correct version by effective_date for tax year
- SKILL-03: Context builder assembles client profile + documents + skills for agent
- SKILL-04: Client profile append-only log maintains integrity after 100+ writes
- SKILL-05: Client profile computed view derives current state from log
- SEARCH-01: Hybrid search combining pgvector (semantic) + pg_textsearch (BM25 keyword)

**Success Criteria:**
1. Task state machine transitions correctly through all states
2. Circuit breaker opens after 5 consecutive LLM failures
3. Circuit breaker closes after 30 seconds
4. Skill loader parses all skill files without error
5. Context builder assembles profile + documents + skills
6. Client profile append-only log maintains integrity after 100 writes
7. Hybrid search returns relevant results combining semantic and keyword matching

**Dependencies:** Phase 1 (Foundation)

**Rollback:** If circuit breaker causes too many false positives, increase threshold to 10.

**Plans:** 6 plans in 4 waves

Plans:
- [x] 02-01-PLAN.md (Wave 1) - State machine + Phase 2 dependencies
- [x] 02-02-PLAN.md (Wave 1) - Task dispatcher
- [x] 02-03-PLAN.md (Wave 2) - Circuit breaker with Redis
- [x] 02-04-PLAN.md (Wave 2) - Skill engine (YAML loader + version selector)
- [x] 02-05-PLAN.md (Wave 3) - Context builder + profile service
- [x] 02-06-PLAN.md (Wave 4) - Hybrid search (pgvector + BM25 + RRF)

---

### Phase 3: Personal Tax Agent - Simple Returns

**Goal:** Prepare W-2-only 1040 returns with CPA-quality output.

**Requirements:**
- DOC-01: Vision API extracts all fields from W-2 with >95% accuracy
- DOC-02: Vision API extracts all fields from 1099-INT with >95% accuracy
- DOC-03: Vision API extracts all fields from 1099-DIV with >95% accuracy
- DOC-04: Vision API extracts all fields from 1099-NEC with >95% accuracy
- DOC-06: Document classifier correctly identifies document type
- DOC-07: Confidence scoring evaluates extraction reliability (HIGH/MEDIUM/LOW)
- PTAX-01: Agent loads client profile and prior year return before starting
- PTAX-02: Agent scans client folder for current year documents
- PTAX-03: Agent aggregates income from all extracted documents
- PTAX-04: Agent calculates deductions (standard vs itemized comparison)
- PTAX-05: Agent evaluates applicable credits
- PTAX-06: Agent computes tax liability using correct brackets
- PTAX-12: Agent compares current vs prior year, flags variances >10%
- PTAX-13: Agent generates Drake worksheet (Excel) with >95% field accuracy
- PTAX-14: Agent generates preparer notes (Markdown) with all required sections
- PTAX-15: Agent escalates when required document missing
- PTAX-16: Agent escalates on conflicting information
- INT-04: Client folder scanner lists documents from cloud storage

**Success Criteria:**
1. Process 5 test returns with varied data successfully
2. Drake worksheet field accuracy >95% compared to manual baseline
3. Preparer notes include all required sections (Summary, Sources, Flags, Assumptions, Review Focus)
4. Prior year comparison flags changes >10%
5. Escalation fires when expected document is missing

**Dependencies:** Phase 2 (Core Framework)

**Rollback:** If accuracy <90%, revert to Phase 0 manual workflow.

**Plans:** 7 plans in 6 waves

Plans:
- [x] 03-01-PLAN.md (Wave 1) — Document Pydantic models + Phase 3 dependencies
- [x] 03-02-PLAN.md (Wave 1) — Storage integration + client folder scanner
- [x] 03-03-PLAN.md (Wave 2) — Document classifier + confidence scoring
- [x] 03-04-PLAN.md (Wave 3) — Document extractor (Claude Vision + Instructor)
- [x] 03-05-PLAN.md (Wave 4) — Tax calculator (TDD: income, deductions, tax, variances)
- [x] 03-06-PLAN.md (Wave 5) — Output generators (Drake worksheet + preparer notes)
- [x] 03-07-PLAN.md (Wave 6) — Personal Tax Agent orchestration

---

### Phase 4: Personal Tax Agent - Complex Returns

**Goal:** Handle Schedule C, E, D, Form 8962, and common complexities.

**Requirements:**
- DOC-05: Vision API extracts all fields from K-1 with >90% accuracy
- PTAX-07: Agent handles Schedule C (self-employment income/expenses)
- PTAX-08: Agent handles Schedule E (rental income)
- PTAX-09: Agent handles Schedule D (capital gains - basic)
- PTAX-10: Agent calculates QBI deduction correctly
- PTAX-11: Agent handles Form 8962 ACA reconciliation (Premium Tax Credit)

**Success Criteria:**
1. K-1 extraction accuracy >90% on test documents
2. Schedule C extraction from 1099-NEC + expenses works correctly
3. Schedule E rental income/expense handling is accurate
4. Schedule D capital gains from 1099-B are processed
5. QBI deduction calculation matches manual verification
6. Form 8962 ACA reconciliation (Premium Tax Credit) calculates correctly
7. 5 complex test returns complete with >90% accuracy
8. All existing Phase 3 tests continue to pass

**Dependencies:** Phase 3 (Personal Tax - Simple)

**Rollback:** If Schedule C accuracy <85%, exclude self-employment from automation.

**Plans:** 8 plans in 5 waves

Plans:
- [x] 04-01-PLAN.md (Wave 1) — K-1 and 1099-B Document Models
- [x] 04-02-PLAN.md (Wave 1) — K-1 and 1099-B Extractors
- [x] 04-03-PLAN.md (Wave 2) — Schedule C Calculator and Self-Employment Tax
- [x] 04-04-PLAN.md (Wave 3) — Schedule E Calculator (Rental Income)
- [x] 04-05-PLAN.md (Wave 3) — Schedule D Calculator (Capital Gains)
- [x] 04-06-PLAN.md (Wave 4) — QBI Deduction (Section 199A)
- [x] 04-07-PLAN.md (Wave 4) — Form 8962 ACA Reconciliation
- [x] 04-08-PLAN.md (Wave 5) — Complex Return Agent Integration

---

### Phase 5: Review Infrastructure

**Goal:** Feedback loop and quality verification operational.

**Requirements:**
- CHECK-01: Agent verifies numbers against source documents
- CHECK-02: Agent identifies 95% of intentionally injected errors
- CHECK-03: Agent analyzes variances from prior year
- CHECK-04: Agent flags items without documented reasons
- CHECK-05: Agent cannot approve - only flags for human review
- FEED-01: Implicit feedback captures 100% of CPA changes (diff)
- FEED-02: Explicit feedback tags captured with <3 clicks
- FEED-03: Feedback entries stored with task_id, reviewer_id, timestamps
- FEED-04: Feedback includes original_content, corrected_content, diff_summary
- DASH-01: Real-time task status API returns current progress
- DASH-02: Agent status API shows active tasks per agent
- DASH-03: Dashboard displays queue depth and completion counts
- DASH-04: Dashboard shows flags requiring attention
- DASH-05: Dashboard meets WCAG 2.1 AA accessibility standards
- INT-01: TaxDome webhook processes task assignments
- INT-02: TaxDome API updates task status

**Success Criteria:**
1. Implicit feedback captures 100% of CPA changes
2. Explicit feedback tags captured with <3 clicks
3. Checker Agent identifies 95% of intentionally injected errors
4. Status dashboard shows real-time task progress
5. TaxDome webhook processes task assignments correctly

**Dependencies:** Phase 4 (Personal Tax - Complex)

**Rollback:** If TaxDome API unavailable, implement email-based polling.

**Plans:** 4 plans in 3 waves

Plans:
- [x] 05-01-PLAN.md (Wave 1) — Review Infrastructure Backend APIs
- [ ] 05-02-PLAN.md (Wave 2) — Reviewer Dashboard UI + WCAG 2.1 AA checks
- [ ] 05-03-PLAN.md (Wave 2) — Checker accuracy benchmark + injected-error harness
- [ ] 05-04-PLAN.md (Wave 3) — TaxDome live sync hardening + fallback polling path

---

### Phase 6: Business Tax Agent

**Goal:** 1120-S returns with K-1 generation.

**Requirements:**
- BTAX-01: Agent processes 1120-S returns
- BTAX-02: Agent generates K-1 worksheets for shareholders
- BTAX-03: Agent tracks shareholder basis accurately
- BTAX-04: Agent extracts trial balance from source documents
- BTAX-05: Schedule L (balance sheet) reconciles to trial balance
- BTAX-06: K-1 data flows correctly to Personal Tax Agent context via handoff protocol

**Success Criteria:**
1. Process test 1120-S with 2 shareholders successfully
2. K-1 worksheets generated with accurate basis allocation
3. K-1 data flows correctly to Personal Tax Agent context
4. Balance sheet (Schedule L) reconciles to trial balance

**Dependencies:** Phase 4 (Personal Tax - Complex)

**Rollback:** If K-1 accuracy <85%, defer to manual K-1 preparation.

**Plans:** 7 plans in 5 waves

Plans:
- [ ] 06-01-PLAN.md (Wave 1) -- Business tax Pydantic models (Form1120S, ScheduleK, ScheduleL, ShareholderInfo, TrialBalance)
- [ ] 06-02-PLAN.md (Wave 2) -- Trial balance extraction + GL-to-1120S mapping (TDD)
- [ ] 06-03-PLAN.md (Wave 2) -- Shareholder basis tracker (TDD, highest risk)
- [ ] 06-04-PLAN.md (Wave 3) -- 1120-S calculator: Page 1, Schedule K, Schedule L, M-1, M-2 (TDD)
- [ ] 06-05-PLAN.md (Wave 3) -- K-1 allocation + handoff protocol (TDD)
- [ ] 06-06-PLAN.md (Wave 4) -- Output generators (Drake 1120-S, K-1, basis worksheets, preparer notes)
- [ ] 06-07-PLAN.md (Wave 5) -- BusinessTaxAgent orchestrator + dispatcher integration + end-to-end tests

---

### Phase 7: Bookkeeping Agent

**Goal:** Transaction categorization with QBO integration.

**Requirements:**
- BOOK-01: Agent categorizes transactions with >90% accuracy
- BOOK-02: QuickBooks Online API reads transactions successfully
- BOOK-03: QuickBooks Online API writes categorizations successfully
- BOOK-04: Agent detects anomalies (transactions >2 sigma from historical pattern)
- BOOK-05: Agent generates reconciliation reports
- INT-03: QuickBooks Online OAuth connector handles token refresh

**Success Criteria:**
1. Categorize 100 test transactions with >90% accuracy
2. QBO API reads transactions successfully
3. QBO API writes categorizations successfully
4. Anomaly detection flags transactions >2 sigma from historical pattern
5. Reconciliation reports generate correctly

**Dependencies:** Phase 5 (Review Infrastructure), Phase 6 (Business Tax)

**Rollback:** If QBO API unreliable, operate in batch-only mode (CSV).

---

### Phase 8: Production Hardening

**Goal:** Ready for pilot deployment.

**Requirements:**
- PROD-01: System handles 10 concurrent tasks without degradation
- PROD-02: Recovery from agent crash within 2 minutes
- PROD-03: All security vulnerabilities addressed
- PROD-04: Backup/restore tested successfully
- PROD-05: Operational runbook covers 10 most common issues

**Success Criteria:**
1. System handles 10 concurrent tasks without degradation
2. Recovery from agent crash within 2 minutes
3. All security vulnerabilities addressed
4. Backup/restore tested successfully
5. Operational runbook covers 10 most common issues

**Dependencies:** Phase 7 (Bookkeeping)

**Rollback:** N/A - final phase before pilot.

---

## Progress Tracking

| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1 - Foundation | Complete | 5/5 | 100% |
| 2 - Core Framework | Complete | 6/6 | 100% |
| 3 - Personal Tax Simple | Complete | 7/7 | 100% |
| 4 - Personal Tax Complex | Complete | 8/8 | 100% |
| 5 - Review Infrastructure | In Progress | 1/4 | 25% |
| 6 - Business Tax | Planned | 0/7 | 0% |
| 7 - Bookkeeping | Pending | 0/0 | 0% |
| 8 - Production Hardening | Pending | 0/0 | 0% |

**Overall:** 4/8 phases complete (50%)

---

## Parallel Workstreams

| Primary Track | Parallel Track | Can Start When |
|---------------|----------------|----------------|
| Phase 3: PT Simple | Skill file authoring (Business Tax) | Phase 2 complete |
| Phase 4: PT Complex | TaxDome API integration research | Phase 3 in progress |
| Phase 5: Review Infrastructure | Phase 6: Business Tax Agent | Phase 4 complete |
| Phase 6: Business Tax | QBO OAuth connector setup | Phase 5 in progress |

---

*Roadmap created: 2026-01-23*
*Last updated: 2026-02-06 (Phase 5 backend slice complete)*
