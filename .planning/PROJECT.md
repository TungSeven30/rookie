# Rookie

## What This Is

An AI employee platform for CPA firms that performs actual accounting work — tax return preparation, transaction categorization, and reconciliation — under human supervision. Unlike chatbots or narrow automation tools, Rookie operates as a full workflow participant: it reads source documents, understands client history, follows firm procedures, and produces professional work products ready for human review.

## Core Value

**CPAs are liable for the work, not the AI. Rookie prepares, humans approve. That's non-negotiable.**

Every design decision flows from this: the AI never approves its own work, always escalates uncertainty, and treats corrections as learning opportunities — exactly like a trustworthy junior employee.

## Requirements

### Validated

(None yet — ship to validate)

### Active

#### Foundation (Phase 1)
- [ ] FastAPI server with health, tasks, clients endpoints
- [ ] PostgreSQL database with full schema (tasks, clients, profiles, artifacts, feedback, skills)
- [ ] Redis connection for queue, circuit breaker, and real-time status
- [ ] Structured JSON logging with task_id, client_id, agent, duration
- [ ] Error tracking integration (Sentry or equivalent)

#### Core Framework (Phase 2)
- [ ] Task state machine (pending → assigned → in_progress → completed/failed/escalated)
- [ ] Task dispatcher with agent routing by task type
- [ ] Circuit breaker (5-fail threshold, 30s recovery, 2-success close)
- [ ] Skill engine (YAML parsing, version selection by effective date)
- [ ] Client profile manager (append-only log pattern)
- [ ] Context builder (profile + documents + skills assembly)

#### Personal Tax Agent (Phases 3-4)
- [ ] Document extraction via vision API (W-2, 1099-INT/DIV/NEC, K-1)
- [ ] 1040 preparation with Schedule A/B/C/D/E support
- [ ] QBI deduction calculation
- [ ] Form 8962 ACA reconciliation (Premium Tax Credit)
- [ ] Prior year comparison with variance flagging
- [ ] Drake worksheet generation (Excel format)
- [ ] Preparer notes generation (Markdown format)
- [ ] Escalation handler for uncertainty and missing documents

#### Review Infrastructure (Phase 5)
- [ ] Implicit feedback capture (diff AI output vs final)
- [ ] Explicit feedback tags (misclassified, missing_context, judgment_call, etc.)
- [ ] Checker Agent (cross-reference, variance analysis, completeness check)
- [ ] Status dashboard (real-time task progress)
- [ ] TaxDome webhook integration

#### Business Tax Agent (Phase 6)
- [ ] 1120-S preparation
- [ ] K-1 generation with basis tracking
- [ ] K-1 handoff protocol to Personal Tax Agent
- [ ] Trial balance extraction

#### Bookkeeping Agent (Phase 7)
- [ ] Transaction categorization (>90% accuracy)
- [ ] QuickBooks Online API integration (OAuth, read/write)
- [ ] Bank reconciliation
- [ ] Anomaly detection (>2σ from historical pattern)

#### Production Hardening (Phase 8)
- [ ] Load testing (10 concurrent tasks)
- [ ] Crash recovery (<2 min)
- [ ] Security audit
- [ ] Backup/restore procedures
- [ ] Operational runbook

### Out of Scope

- Multi-tenancy — prove value for one firm first, add later
- Drake XML import — worksheets sufficient for V1, evaluate later
- Multi-state apportionment — complex edge case, escalate to human
- Cryptocurrency handling — specialized domain, requires separate skill development
- SOC 2 certification — functionality first, compliance after
- Mobile dashboard — desktop-first for CPA workflow
- Automated client communication — humans control client-facing messages
- Fine-tuning/RLHF — prompt engineering and RAG sufficient for V1
- Wash sale tracking — complex Schedule D edge case, escalate
- Foreign income (Form 2555) — specialized, always escalate
- Estate/Trust returns (1041) — different domain, future agent
- Payroll processing — integrate with existing payroll providers

## Context

**Deployment model:** Single-firm deployment for V1. Multi-tenancy deferred until core value is proven.

**Target workflow:** CPA assigns work in TaxDome → Rookie picks it up → Agent executes with skill files → Produces Drake worksheet + preparer notes → Human reviews and provides feedback → System learns from corrections.

**Trust graduation:** First 10 returns reviewed line-by-line. Next 50 spot-checked. Eventually only exceptions need attention.

**Client profile system:** Append-only log with 3-year detailed retention, older years summarized. Profiles follow defined schema: income sources, deduction patterns, filing history, red flags, planning opportunities.

**Skill files:** Versioned YAML with effective dates, checklists, decision rules, and escalation triggers. Tax law changes → update skill file with new effective date → agent applies correct rules per tax year.

## Constraints

- **Tech stack**: Python 3.11+ / FastAPI / PostgreSQL 15+ / pgvector / Redis — best AI/ML ecosystem, mature tooling
- **LLM provider**: Claude primary (best reasoning + vision), multi-provider architecture (no vendor lock-in)
- **Document output**: Drake worksheets (Excel) for manual entry — evaluate XML import later
- **Security**: No client PII in AI training, only SSN last-4 stored, full audit trail, role-based access
- **Data retention**: Completed tasks 7 years (IRS audit window), agent logs 1 year, client profiles 3 years detailed

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Start Phase 1 (Foundation) instead of Phase 0 (Golden Path) | User preference — build infrastructure first | — Pending |
| Single-firm deployment for V1 | Reduce complexity, prove value before scaling | — Pending |
| Append-only log for client profiles | Eliminates merge conflicts, provides full history | — Pending |
| Worksheet output (not Drake XML) | Avoids reverse-engineering GruntWorx schema | — Pending |
| Vision API for document extraction | Direct extraction without OCR pipeline | — Pending |

---
*Last updated: 2026-01-23 after initialization*
