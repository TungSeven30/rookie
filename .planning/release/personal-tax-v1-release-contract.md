# Personal Tax v1 Release Contract

**Version:** v1.0-draft
**Date:** 2026-02-06
**Owner:** Rookie product + CPA lead

## 1) Product Objective

Ship a production-ready personal tax workflow where AI prepares returns and human reviewers approve, with auditable review actions and task-based operations.

## 2) In Scope (Must-Have)

1. Task-based workflow for internal staff:
   - Create/search clients
   - Create/list/filter tasks
   - Transition task states with guardrails
2. Personal tax preparation pipeline:
   - Supported forms and calculators from completed Phase 3/4 work
   - Output artifacts: Drake worksheet + preparer notes
3. Review infrastructure:
   - Checker flags (no auto-approval)
   - Explicit and implicit feedback capture
   - Status/queue/dashboard APIs
4. Integration:
   - TaxDome task assignment webhook intake
   - TaxDome task status sync path
5. Security/operations baseline:
   - Auth + RBAC for staff endpoints (preparer/reviewer/admin)
   - Audit trail for reviewer actions
   - PII-safe logging and retention controls

## 3) Out of Scope (v1)

1. Multi-tenant architecture.
2. Business tax (1120-S) workflows.
3. Bookkeeping/QBO automation workflows.
4. End-client first-party portal (TaxDome remains client-facing intake for v1).
5. SOC 2 certification execution (controls may be prepared, not certified in v1).

## 4) User Roles

- **Preparer:** Creates/works tasks and drafts outputs.
- **Reviewer (CPA):** Reviews checker flags, corrects outputs, approves/escalates.
- **Admin:** System config, assignment overrides, operational controls.

## 5) Acceptance Gates

## 5.1 Functional Gates

1. `clients` API supports create/get/list/update with pagination and search.
2. `tasks` API supports create/get/list and valid state transitions.
3. Review endpoints support explicit + implicit feedback and feedback history retrieval.
4. Dashboard endpoints show queue depth, active agents, and unresolved flags.
5. TaxDome webhook assignment creates/updates tasks idempotently.

## 5.2 Quality Gates

1. Checker benchmark meets CHECK-02 target: >=95% injected error detection.
2. FEED-02 usability target met: explicit tags captured in <=3 clicks in reviewer UI.
3. Regression suite passes on golden return set without material drift.
4. Accessibility: no critical WCAG 2.1 AA violations on core screens.
5. Load/recovery thresholds met for pilot target workload.

## 5.3 Safety Gates

1. Reviewer approval required for all returns.
2. All status-changing actions are auditable (actor, timestamp, before/after).
3. PII redaction rules enforced in logs and telemetry.

## 6) Release Readiness Checklist

- [ ] Functional gates complete
- [ ] Quality gates complete
- [ ] Safety gates complete
- [ ] UAT sign-off by CPA lead
- [ ] Pilot ramp plan approved
- [ ] Rollback playbook validated

## 7) Rollback Policy

If any release gate fails after deployment:
1. Disable affected feature via flag (checker auto-run, TaxDome outbound sync, etc.).
2. Fall back to manual reviewer workflow.
3. Keep task artifacts and audit trail intact.
4. Re-run gate-specific verification before re-enabling.

## 8) Definition of Done (Personal Tax v1)

Personal Tax v1 is complete when all gates and checklist items above are marked complete, and the first pilot cohort runs through end-to-end workflow without severity-1 regressions.
