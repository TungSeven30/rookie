# Plan: Personal Tax Full Product

**Generated**: 2026-02-06
**Estimated Complexity**: High

## Overview

You already have strong personal-tax processing capability and a working demo UI. The remaining work is productization: operational workflow UI, reviewer UX, production auth/security, integration hardening, and release gating.

This plan moves from the current state (Phase 5 backend partially complete) to a full, deployable personal-tax product for CPA staff and clients.

## Execution Status (2026-02-06)

### Completed

- Sprint 1 / Task 1.1: v1 release contract defined in `.planning/release/personal-tax-v1-release-contract.md`.
- Sprint 1 / Task 1.2: `clients` API implemented with create/list/get/update + tests.
- Sprint 1 / Task 1.3: `tasks` API implemented with filters + state transitions + escalation creation + tests.
- Sprint 1 / Task 1.4 (partial): frontend app switched to product navigation with Operations workspace plus demo fallback.

### In Progress

- Sprint 2 / Task 2.1: status dashboard UI is implemented in Operations workspace; API-level operations flow integration test is in place.
- Sprint 2 / Task 2.2: checker panel is implemented in task detail view.
- Sprint 2 / Task 2.3: explicit feedback quick-tag flow is implemented; click-count validation is pending.
- Sprint 2 / Task 2.4 (partial): implicit feedback capture from reviewer edit/correction workflow is implemented in UI.
- Sprint 2 / Task 2.5 (partial): static WCAG guardrail checks are implemented and passing.

### Remaining

- Sprint 2 / Task 2.4: connect implicit capture directly to final artifact editor once full output editing UI lands.
- Sprint 2 / Task 2.5: run runtime browser accessibility audit (playwright/axe) when environment allows browser binary install.
- Sprint 3-5 items: TaxDome hardening, auth/RBAC, audit logging, retention/PII controls, benchmarks, regression/load testing, UAT.

## Assumptions

- Single-firm deployment remains the v1 scope (no multi-tenant support).
- Humans remain final approvers for all returns.
- Existing personal-tax calculation/extraction behavior is the functional baseline.
- TaxDome remains primary task source/status sink.
- Client-facing intake can remain in TaxDome for v1 unless a dedicated client portal is explicitly required.

## Prerequisites

- Staging and production infrastructure targets available.
- TaxDome sandbox credentials and webhook docs available.
- Seed dataset of anonymized returns for validation.
- Named product owner (CPA lead) for UAT sign-off.

## Sprint 1: Product Workflow Surface

**Goal**: Replace demo-only interaction with a real task-based product flow.

**Demo/Validation**:
- User logs in, opens queue, claims a task, processes docs, and reaches review screen.
- API no longer depends on demo-only workflow for core operations.

### Task 1.1: Define v1 Release Contract
- **Location**: `.planning/release/personal-tax-v1-release-contract.md`
- **Description**: Freeze v1 scope, user roles, and acceptance criteria mapped to requirement IDs.
- **Complexity**: 2/10
- **Dependencies**: None
- **Acceptance Criteria**:
  - Scope in/out list approved.
  - Each critical requirement has measurable acceptance test.
- **Validation**:
  - Team review and sign-off checklist.

### Task 1.2: Implement Real `clients` API
- **Location**: `src/api/clients.py`, `tests/api/test_clients.py`
- **Description**: Replace placeholder with CRUD + search endpoints used by queue/review UIs.
- **Complexity**: 5/10
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - Create/read/search clients works with pagination.
  - Input validation and consistent error model in place.
- **Validation**:
  - API tests with sqlite and Postgres integration test.

### Task 1.3: Implement Real `tasks` API
- **Location**: `src/api/tasks.py`, `tests/api/test_tasks.py`
- **Description**: Replace placeholder with task creation, assignment, status transitions, and list filters.
- **Complexity**: 6/10
- **Dependencies**: Task 1.2
- **Acceptance Criteria**:
  - Queue views can filter by status/agent/date.
  - Assignment and transition rules follow state machine constraints.
- **Validation**:
  - Unit + API tests for state transition edge cases.

### Task 1.4: Create Product App Navigation + Queue UI
- **Location**: `frontend/src/App.tsx`, `frontend/src/pages/*`, `frontend/src/api/*`
- **Description**: Add queue page, task detail page, and client selector workflow.
- **Complexity**: 7/10
- **Dependencies**: Tasks 1.2, 1.3
- **Acceptance Criteria**:
  - Users can navigate between queue, task detail, and results.
  - Demo upload path remains available behind feature flag for fallback.
- **Validation**:
  - Playwright happy-path test for queue-to-results flow.

## Sprint 2: Review UX Completion (Phase 5 Completion)

**Goal**: Complete reviewer-facing workflows and accessibility targets.

**Demo/Validation**:
- Reviewer sees checker report, edits outputs, applies explicit tags in <=3 clicks, and submits review decision.

### Task 2.1: Build Status Dashboard UI
- **Location**: `frontend/src/pages/dashboard/*`, `frontend/src/components/*`
- **Description**: Surface `GET /api/status/tasks`, `/agents`, `/dashboard` with live refresh.
- **Complexity**: 6/10
- **Dependencies**: Sprint 1 complete
- **Acceptance Criteria**:
  - Queue depth, completion counts, and attention flags visible.
  - Page updates within defined refresh interval.
- **Validation**:
  - UI integration tests with mocked API responses.

### Task 2.2: Build Checker Report Panel
- **Location**: `frontend/src/pages/task-detail/*`, `frontend/src/api/review.ts`
- **Description**: Display checker flags, severity, variance context, and supporting evidence links.
- **Complexity**: 5/10
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - Reviewer can run checker and inspect flags per field.
  - No approve action is offered by checker UI.
- **Validation**:
  - Component tests + manual review against seeded flagged tasks.

### Task 2.3: Implement Explicit Feedback Quick-Tag UX
- **Location**: `frontend/src/components/feedback/*`
- **Description**: Add one-click tag chips and compact submission flow meeting FEED-02.
- **Complexity**: 5/10
- **Dependencies**: Task 2.2
- **Acceptance Criteria**:
  - Explicit feedback captured in <=3 clicks from task detail.
  - Tag analytics are persisted for reporting.
- **Validation**:
  - Usability script with click-count verification.

### Task 2.4: Implement Implicit Diff Capture from Reviewer Edits
- **Location**: `frontend/src/pages/task-detail/*`, `src/api/review.py`
- **Description**: Capture original vs corrected content on save and write implicit feedback entry automatically.
- **Complexity**: 6/10
- **Dependencies**: Task 2.3
- **Acceptance Criteria**:
  - Every reviewer edit creates feedback diff record.
  - Diff summary is inspectable in review history.
- **Validation**:
  - End-to-end test asserting feedback entry creation after edit.

### Task 2.5: WCAG 2.1 AA Accessibility Hardening
- **Location**: `frontend/src/**/*`, `frontend/tests/accessibility/*`
- **Description**: Keyboard nav, labels, focus order, contrast, and screen reader semantics.
- **Complexity**: 5/10
- **Dependencies**: Tasks 2.1-2.4
- **Acceptance Criteria**:
  - No critical axe violations on queue/task/dashboard pages.
  - Keyboard-only completion of review workflow.
- **Validation**:
  - Automated axe checks + manual keyboard pass.

## Sprint 3: TaxDome Integration Hardening

**Goal**: Make TaxDome integration reliable in real environments.

**Demo/Validation**:
- Assignment webhook creates task idempotently; status updates sync back reliably with retries.

### Task 3.1: Add Webhook Signature Validation and Idempotency
- **Location**: `src/api/integrations.py`, `src/models/task.py`, migration file
- **Description**: Verify signatures, dedupe by external event/task IDs, and prevent duplicate task creation.
- **Complexity**: 7/10
- **Dependencies**: Sprint 2 complete
- **Acceptance Criteria**:
  - Replayed webhook events do not create duplicate tasks.
  - Invalid signatures are rejected.
- **Validation**:
  - API tests covering replay and tampered signature cases.

### Task 3.2: Build Outbound TaxDome Status Sync Service
- **Location**: `src/integrations/taxdome_client.py`, `src/orchestration/*`
- **Description**: Add resilient outbound sync with retry, timeout, and circuit breaker behavior.
- **Complexity**: 7/10
- **Dependencies**: Task 3.1
- **Acceptance Criteria**:
  - Status changes enqueue outbound sync jobs.
  - Temporary TaxDome outages do not lose updates.
- **Validation**:
  - Integration tests with simulated 5xx/timeout behavior.

### Task 3.3: Add Fallback Polling Path
- **Location**: `src/jobs/taxdome_polling.py`, scheduler wiring
- **Description**: Implement rollback path from roadmap for webhook-unavailable conditions.
- **Complexity**: 5/10
- **Dependencies**: Task 3.2
- **Acceptance Criteria**:
  - Poller reconciles missed assignments and statuses.
- **Validation**:
  - Disaster-recovery test using disabled webhook mode.

## Sprint 4: Production Security and Operations Baseline

**Goal**: Move from demo auth model to production-safe operation.

**Demo/Validation**:
- Users authenticate with role-based permissions and full audit trail.

### Task 4.1: Replace Demo API Key with Auth + RBAC
- **Location**: `src/api/deps.py`, `src/api/auth.py`, `frontend/src/auth/*`
- **Description**: Add authenticated sessions/JWT and role checks (preparer/reviewer/admin).
- **Complexity**: 8/10
- **Dependencies**: Sprint 3 complete
- **Acceptance Criteria**:
  - Unauthorized users cannot access task/review endpoints.
  - Role checks enforce reviewer-only actions.
- **Validation**:
  - Security-focused API tests and role matrix tests.

### Task 4.2: Add Audit Logging for Reviewer Actions
- **Location**: `src/models/log.py`, `src/api/review.py`
- **Description**: Persist immutable action logs for edits, flags, overrides, and status transitions.
- **Complexity**: 5/10
- **Dependencies**: Task 4.1
- **Acceptance Criteria**:
  - Every review action has actor, timestamp, before/after context.
- **Validation**:
  - Audit trail query tests and sample compliance export.

### Task 4.3: PII Guardrails + Retention Jobs
- **Location**: `src/core/logging.py`, `src/jobs/retention.py`, config
- **Description**: Ensure sensitive fields are redacted in logs and retention jobs run correctly.
- **Complexity**: 6/10
- **Dependencies**: Task 4.2
- **Acceptance Criteria**:
  - Sensitive data is excluded/redacted from logs.
  - Retention policies enforce configured windows.
- **Validation**:
  - Log snapshot tests and retention dry-run tests.

## Sprint 5: Quality Gates and Release Readiness

**Goal**: Prove accuracy, reliability, and performance before pilot.

**Demo/Validation**:
- Full release-candidate pass: accuracy thresholds met, regression clean, operational metrics green.

### Task 5.1: Checker Accuracy Benchmark Harness (CHECK-02)
- **Location**: `tests/benchmarks/checker_accuracy/*`
- **Description**: Build injected-error dataset and benchmark tool to measure detection rate.
- **Complexity**: 6/10
- **Dependencies**: Sprint 4 complete
- **Acceptance Criteria**:
  - Report shows >=95% detection in benchmark scenarios.
- **Validation**:
  - CI benchmark run artifact retained.

### Task 5.2: Golden Return Regression Suite
- **Location**: `tests/regression/personal_tax/*`
- **Description**: Build fixed expected outputs for representative return types.
- **Complexity**: 7/10
- **Dependencies**: Task 5.1
- **Acceptance Criteria**:
  - No unintended drift in worksheet/notes/tax totals.
- **Validation**:
  - Regression suite required in CI for merge.

### Task 5.3: Load and Recovery Testing
- **Location**: `tests/load/*`, runbook docs
- **Description**: Validate concurrency, failure recovery, and service health behavior.
- **Complexity**: 5/10
- **Dependencies**: Task 5.2
- **Acceptance Criteria**:
  - Meets agreed throughput and recovery thresholds.
- **Validation**:
  - Load test report with pass/fail criteria.

### Task 5.4: CPA UAT and Sign-Off
- **Location**: `.planning/uat/personal-tax-v1-uat.md`
- **Description**: Run UAT sessions with CPA reviewers and close all P1/P2 defects.
- **Complexity**: 4/10
- **Dependencies**: Task 5.3
- **Acceptance Criteria**:
  - Signed UAT document and release go/no-go decision.
- **Validation**:
  - Checklist completion and defect closure list.

## Sprint 6: Deployment and Pilot Rollout

**Goal**: Launch safely with observability and rollback controls.

**Demo/Validation**:
- Deployed release candidate running in staging and production-like pilot.

### Task 6.1: Deployment Pipeline + Environment Promotion
- **Location**: CI/CD config, deployment docs
- **Description**: Define build/test/deploy gates and promote from staging to production.
- **Complexity**: 6/10
- **Dependencies**: Sprint 5 complete
- **Acceptance Criteria**:
  - One-command reproducible deploy with migration checks.
- **Validation**:
  - Successful staging and production dry-run deploy.

### Task 6.2: Feature Flags + Kill Switches
- **Location**: `src/core/config.py`, `frontend/src/config/*`
- **Description**: Add runtime flags for high-risk features and emergency disable paths.
- **Complexity**: 4/10
- **Dependencies**: Task 6.1
- **Acceptance Criteria**:
  - TaxDome sync, checker auto-run, and feedback capture can be toggled safely.
- **Validation**:
  - Operational toggle drill in staging.

### Task 6.3: Pilot Ramp Plan
- **Location**: `.planning/release/pilot-ramp-plan.md`
- **Description**: Launch in batches (10 returns -> 50 returns -> broader use) with rollback thresholds.
- **Complexity**: 3/10
- **Dependencies**: Task 6.2
- **Acceptance Criteria**:
  - Defined stop/go criteria per ramp stage.
- **Validation**:
  - Post-stage review checklists completed.

## Testing Strategy

- Unit tests for all new domain logic and API validation.
- API integration tests (sqlite + selected Postgres integration coverage).
- Frontend component tests and end-to-end Playwright flow tests.
- Accessibility tests (axe + manual keyboard path).
- Benchmark and regression suites required before release.
- Load and recovery tests before pilot ramp.

## Potential Risks & Gotchas

- Demo assumptions leaking into production workflow.
  - Mitigation: Explicit feature flags and release contract acceptance checks.
- TaxDome event duplication and out-of-order updates.
  - Mitigation: Idempotency keys and authoritative state reconciliation.
- Checker benchmark overfitting to synthetic errors.
  - Mitigation: Mixed synthetic + real historical correction dataset.
- Accessibility gaps discovered late.
  - Mitigation: Bake axe checks into CI by Sprint 2.
- Reviewer adoption friction.
  - Mitigation: UAT in Sprint 5 with explicit workflow refinements.

## Rollback Plan

- Keep demo upload flow behind a flag as fallback during early rollout.
- Disable outbound TaxDome sync independently if integration instability is detected.
- Revert to manual review queue export if checker or feedback flows regress.
- Use staged rollback by environment (pilot -> staging -> production).

## Suggested Execution Order

1. Sprint 1 + Sprint 2 (finish product and review UX)
2. Sprint 3 (harden external integration)
3. Sprint 4 (production auth/security baseline)
4. Sprint 5 (quality gates and UAT)
5. Sprint 6 (deploy and ramp)

## Open Decisions (Resolve Before Sprint 1)

1. Client portal strategy: use TaxDome portal only vs build first-party client portal.
2. Authentication stack: simple internal auth vs enterprise SSO integration.
3. Deployment target: single VM/container stack vs managed platform rollout.
4. Pilot success metrics: exact throughput/error thresholds for go/no-go.
