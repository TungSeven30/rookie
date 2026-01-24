# Rookie Master Plan & Technical Specification

**Version**: 1.0  
**Date**: January 23, 2026  
**Status**: Comprehensive Implementation Specification

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Implementation Phases](#implementation-phases)
4. [Technical Stack](#technical-stack)
5. [Core Data Models](#core-data-models)
6. [Agent Specifications](#agent-specifications)
7. [Integration Specifications](#integration-specifications)
8. [Workflow & State Management](#workflow--state-management)
9. [Error Handling & Escalation](#error-handling--escalation)
10. [Feedback & Learning Mechanisms](#feedback--learning-mechanisms)
11. [Security & Compliance](#security--compliance)
12. [Monitoring & Observability](#monitoring--observability)
13. [Appendices](#appendices)

---

## Executive Summary

Rookie is an AI employee platform for CPA firms that prepares tax returns, categorizes transactions, and produces work products following the same processes as junior staff. The system operates as a virtual employee within existing workflows (TaxDome), producing deliverables ready for human review and sign-off.

### Core Principles

1. **AI as Employee**: Treat AI like a new hire — expects supervision, learns from feedback, earns trust over time
2. **Human-in-the-Loop**: CPA remains professionally liable; all work requires human review and approval
3. **Build It Right**: Prioritize correctness and maintainability over speed
4. **Single-Firm First**: Multi-tenancy deferred to post-v1; focus on proving value for one firm
5. **Append-Only Logs**: Client profiles use append-only structure to eliminate merge conflicts

### Key Deliverables

- **Personal Tax Agent**: Prepares 1040 returns with Drake worksheets and preparer notes
- **Business Tax Agent**: Prepares 1120/1120-S/1065 returns with K-1 schedules
- **Bookkeeping Agent**: Categorizes transactions, reconciles accounts, produces month-end reports
- **Checker Agent**: Verifies work against source documents and prior year returns

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    TaxDome / Task Assignment                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │   Rookie Orchestration Layer  │
        │   (Task Router & State Mgmt)  │
        └───────────────┬───────────────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
┌───▼────┐        ┌─────▼─────┐      ┌─────▼──────┐
│Personal│        │  Business │      │Bookkeeping │
│  Tax   │        │    Tax    │      │   Agent    │
│ Agent  │        │   Agent   │      │            │
└───┬────┘        └─────┬─────┘      └─────┬──────┘
    │                   │                   │
    └───────────────────┼───────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │      Shared Infrastructure     │
        │  • Client Profile Manager      │
        │  • Document Processor          │
        │  • Skill File Manager          │
        │  • Feedback Collector          │
        └───────────────┬───────────────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
┌───▼────┐        ┌─────▼─────┐      ┌─────▼──────┐
│Postgres│        │   Redis   │      │  pgvector  │
│   DB   │        │  (Cache)  │      │   (RAG)    │
└────────┘        └───────────┘      └────────────┘
```

### Core Services

1. **Orchestration Service**: Routes tasks to agents, manages state, handles escalations
2. **Client Profile Service**: Manages append-only client logs, profile summaries, retention policies
3. **Document Processing Service**: Extracts data from PDFs/images using LLM vision
4. **Skill File Service**: Manages versioned skill files for each agent type
5. **Feedback Service**: Collects implicit (diff-based) and explicit (tagged) feedback
6. **Integration Service**: Handles TaxDome, QuickBooks, Drake integrations

---

## Implementation Phases

### Phase 0: Foundation (Weeks 1-4)

**Objective**: Establish core infrastructure and shared services

**Deliverables**:
- PostgreSQL schema with pgvector extension
- Redis cache setup
- FastAPI application skeleton
- Authentication/authorization framework
- Basic logging and monitoring
- Client profile append-only log structure
- Document storage and retrieval system

**Success Criteria**:
- Database migrations run cleanly
- API endpoints respond with proper auth
- Client profiles can be created and updated
- Documents can be uploaded and retrieved

---

### Phase 1: Personal Tax Agent - Core (Weeks 5-10)

**Objective**: Build Personal Tax agent capable of preparing simple 1040 returns

**Deliverables**:
- Personal Tax agent implementation
- Skill file: Personal Tax 1040 (v1.0)
- Document extraction pipeline (W-2, 1099, 1098, etc.)
- Client profile loader and updater
- Drake worksheet generator (Excel format)
- Preparer notes generator
- Prior year comparison logic
- Basic error handling and escalation

**Workflow**:
1. Load client profile (last 3 years)
2. Load Personal Tax skill file
3. Scan client folder for current year documents
4. Extract data from source documents
5. Execute preparation checklist
6. Generate Drake worksheet
7. Generate preparer notes
8. Compare to prior year return (PDF)
9. Flag significant changes
10. Produce handoff artifacts

**Success Criteria**:
- Agent completes simple W-2-only returns correctly
- Drake worksheets are properly formatted
- Preparer notes include all required sections
- Prior year comparison flags significant changes
- Errors escalate to human with clear context

---

### Phase 2: Personal Tax Agent - Advanced (Weeks 11-14)

**Objective**: Expand Personal Tax agent to handle complex returns

**Deliverables**:
- Schedule A (Itemized Deductions) support
- Schedule B (Interest/Dividends) support
- Schedule C (Business Income) support
- Schedule D (Capital Gains) support
- Schedule E (Rental Income) support
- Schedule SE (Self-Employment Tax) support
- Dependent handling
- Estimated tax calculations
- Extension handling

**Success Criteria**:
- Agent handles returns with multiple schedules
- Complex scenarios (rental properties, side businesses) processed correctly
- Confidence scoring implemented for uncertain items

---

### Phase 3: Business Tax Agent - Core (Weeks 15-20)

**Objective**: Build Business Tax agent for entity returns

**Deliverables**:
- Business Tax agent implementation
- Skill file: Business Tax 1120/1120-S/1065 (v1.0)
- Entity profile structure (extends client profile)
- K-1 generation logic
- Basis tracking
- Depreciation handling
- Payroll reconciliation
- Business expense categorization

**Workflow**:
1. Load entity profile
2. Load Business Tax skill file
3. Scan entity folder for current year documents
4. Extract financial statements (P&L, Balance Sheet)
5. Extract supporting documents (1099s, W-2s, invoices)
6. Execute preparation checklist
7. Generate entity return worksheet
8. Generate K-1 schedules (if applicable)
9. Generate preparer notes
10. Compare to prior year return
11. Produce handoff artifacts

**Success Criteria**:
- Agent completes simple S-Corp returns correctly
- K-1 schedules are accurate
- Basis calculations are correct
- Entity worksheets follow firm conventions

---

### Phase 4: Bookkeeping Agent - Core (Weeks 21-26)

**Objective**: Build Bookkeeping agent for transaction categorization and reconciliation

**Deliverables**:
- Bookkeeping agent implementation
- Skill file: Bookkeeping (v1.0)
- QuickBooks API integration
- Transaction categorization logic
- Bank reconciliation logic
- Month-end checklist automation
- Variance analysis reports
- Chart of accounts mapping

**Workflow**:
1. Load client/entity profile
2. Load Bookkeeping skill file
3. Fetch transactions from QuickBooks (or CSV import)
4. Categorize transactions using rules + ML
5. Flag uncategorized or unusual transactions
6. Generate reconciliation report
7. Produce month-end checklist
8. Generate variance analysis (vs prior periods)
9. Produce handoff artifacts

**Success Criteria**:
- Agent categorizes 90%+ of transactions correctly
- Reconciliation reports are accurate
- Unusual transactions are flagged
- QuickBooks integration works reliably

---

### Phase 5: Checker Agent (Weeks 27-30)

**Objective**: Build Checker agent to verify preparer work

**Deliverables**:
- Checker agent implementation
- Skill file: Checking Procedures (v1.0)
- Source document verification logic
- Prior year variance analysis
- Mathematical verification
- Completeness checks
- Flag generation and prioritization

**Workflow**:
1. Load preparer's work product
2. Load source documents
3. Load prior year return
4. Verify numbers match source documents
5. Check mathematical accuracy
6. Compare to prior year (flag significant changes)
7. Verify completeness (all required forms/schedules)
8. Generate checker report with flags
9. Escalate critical issues to human

**Success Criteria**:
- Checker identifies 95%+ of preparer errors
- False positive rate < 10%
- Critical issues escalated immediately
- Checker reports are actionable

---

### Phase 6: TaxDome Integration (Weeks 31-32)

**Objective**: Integrate Rookie with TaxDome workflow

**Deliverables**:
- TaxDome API integration (or email-based task assignment)
- Task assignment handler
- Status update mechanism
- Work product delivery to TaxDome
- Notification system

**Success Criteria**:
- Tasks assigned in TaxDome route to Rookie
- Rookie status updates reflect in TaxDome
- Work products accessible in TaxDome
- Notifications work reliably

---

### Phase 7: Feedback & Learning System (Weeks 33-36)

**Objective**: Implement feedback collection and learning mechanisms

**Deliverables**:
- Implicit feedback collector (diff AI draft vs final)
- Explicit feedback interface (lightweight tags)
- Feedback storage and analysis
- Skill file update process
- RAG system for incorporating feedback into context
- Feedback dashboard for CPAs

**Success Criteria**:
- Implicit feedback captured automatically
- Explicit feedback optional and lightweight
- Feedback influences future agent behavior
- Skill files updated based on feedback patterns

---

### Phase 8: Monitoring & Status Dashboard (Weeks 37-38)

**Objective**: Build granular status monitoring interface

**Deliverables**:
- Real-time status dashboard
- Task progress visualization
- Agent activity logs
- Performance metrics
- Error tracking and alerts

**Success Criteria**:
- CPAs can see exactly where AI is in a project
- Status updates are real-time
- Errors are visible and actionable
- Performance metrics are meaningful

---

### Phase 9: Production Hardening (Weeks 39-40)

**Objective**: Prepare for production deployment

**Deliverables**:
- Load testing and optimization
- Security audit
- Backup and disaster recovery
- Documentation (user guides, API docs)
- Training materials
- Pilot deployment plan

**Success Criteria**:
- System handles tax season load
- Security vulnerabilities addressed
- Backup/recovery tested
- Documentation complete
- Pilot users trained

---

## Technical Stack

### Backend

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL 15+ with pgvector extension
- **Cache**: Redis 7+
- **Task Queue**: Celery with Redis broker (for async processing)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic

### AI/ML

- **LLM APIs**: 
  - Anthropic Claude (primary)
  - OpenAI GPT-4 (fallback/alternative)
  - Google Gemini (specialized tasks)
- **Vision**: LLM native vision APIs for document extraction
- **Vector DB**: pgvector (PostgreSQL extension)
- **Embeddings**: OpenAI text-embedding-3-large or similar

### Integrations

- **TaxDome**: REST API or email-based
- **QuickBooks Online**: OAuth 2.0 API
- **Drake**: File-based (CSV/Excel worksheets, future XML)
- **Google Drive / Dropbox**: API for document access

### Infrastructure

- **Containerization**: Docker
- **Orchestration**: Docker Compose (dev), Kubernetes (prod)
- **Monitoring**: Prometheus + Grafana
- **Logging**: Structured logging (JSON) to centralized log aggregation
- **Error Tracking**: Sentry or similar

### Development Tools

- **Code Quality**: Ruff (linting/formatting), mypy (type checking)
- **Testing**: pytest, pytest-asyncio
- **API Documentation**: FastAPI auto-generated docs (OpenAPI/Swagger)

---

## Core Data Models

### Client Profile

**Storage**: Append-only log in PostgreSQL

**Schema**:
```sql
CREATE TABLE client_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    entry_type VARCHAR(50) NOT NULL, -- 'profile_update', 'meeting_note', 'work_completion', etc.
    author VARCHAR(100) NOT NULL, -- 'human:user_id' or 'ai:agent_type'
    content JSONB NOT NULL,
    effective_date DATE,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_client_profiles_client_id ON client_profiles(client_id);
CREATE INDEX idx_client_profiles_effective_date ON client_profiles(effective_date);
CREATE INDEX idx_client_profiles_content_gin ON client_profiles USING GIN(content);
```

**Profile Content Structure** (see Appendix A for full schema):
- Identification (name, SSN, DOB, address)
- Contact information
- Household composition
- Income sources (W-2, 1099, K-1, etc.)
- Deductions and credits history
- Tax planning history
- Historical return summary (last 3 years)
- Client preferences
- Red flags and special situations
- Planning opportunities

**Retention Policy**: Last 3 years of detailed information retained; older data archived.

### Tasks

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(100) UNIQUE NOT NULL, -- External ID (e.g., TaxDome task ID)
    client_id VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL, -- 'personal_tax', 'business_tax', 'bookkeeping', 'checking'
    tax_year INTEGER,
    assigned_agent VARCHAR(50), -- 'personal_tax', 'business_tax', 'bookkeeping', 'checker'
    status VARCHAR(50) NOT NULL, -- 'pending', 'in_progress', 'completed', 'escalated', 'cancelled'
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    assigned_by VARCHAR(100), -- User ID
    metadata JSONB
);

CREATE INDEX idx_tasks_client_id ON tasks(client_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assigned_agent ON tasks(assigned_agent);
```

### Task State

```sql
CREATE TABLE task_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    state_key VARCHAR(100) NOT NULL,
    state_value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(task_id, state_key)
);

CREATE INDEX idx_task_states_task_id ON task_states(task_id);
```

### Documents

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id VARCHAR(100) NOT NULL,
    tax_year INTEGER,
    document_type VARCHAR(50), -- 'w2', '1099', '1098', 'bank_statement', etc.
    file_path VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL, -- SHA-256
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    extracted_data JSONB,
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    metadata JSONB
);

CREATE INDEX idx_documents_client_id ON documents(client_id);
CREATE INDEX idx_documents_tax_year ON documents(tax_year);
CREATE INDEX idx_documents_type ON documents(document_type);
```

### Work Products

```sql
CREATE TABLE work_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    product_type VARCHAR(50) NOT NULL, -- 'drake_worksheet', 'preparer_notes', 'k1_schedule', etc.
    file_path VARCHAR(500) NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1,
    metadata JSONB
);

CREATE INDEX idx_work_products_task_id ON work_products(task_id);
```

### Skill Files

```sql
CREATE TABLE skill_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type VARCHAR(50) NOT NULL, -- 'personal_tax', 'business_tax', 'bookkeeping', 'checker'
    version VARCHAR(20) NOT NULL,
    effective_date DATE NOT NULL,
    content TEXT NOT NULL, -- Markdown content
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    UNIQUE(agent_type, version)
);

CREATE INDEX idx_skill_files_agent_type ON skill_files(agent_type);
CREATE INDEX idx_skill_files_effective_date ON skill_files_effective_date(effective_date);
```

### Feedback

```sql
CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    feedback_type VARCHAR(50) NOT NULL, -- 'implicit', 'explicit'
    source VARCHAR(50) NOT NULL, -- 'diff', 'tag', 'correction'
    content JSONB NOT NULL,
    provided_by VARCHAR(100) NOT NULL,
    provided_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    incorporated BOOLEAN DEFAULT FALSE,
    incorporated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_feedback_task_id ON feedback(task_id);
CREATE INDEX idx_feedback_incorporated ON feedback(incorporated);
```

### Agent Executions

```sql
CREATE TABLE agent_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL, -- 'success', 'failed', 'escalated', 'cancelled'
    error_message TEXT,
    execution_log JSONB, -- Step-by-step execution trace
    tokens_used INTEGER,
    cost_estimate DECIMAL(10,4)
);

CREATE INDEX idx_agent_executions_task_id ON agent_executions(task_id);
CREATE INDEX idx_agent_executions_status ON agent_executions(status);
```

---

## Agent Specifications

### Personal Tax Agent

**Purpose**: Prepare individual tax returns (Form 1040) with all applicable schedules

**Inputs**:
- Client profile (append-only log)
- Current year documents (W-2, 1099, 1098, etc.)
- Prior year return (PDF)
- Personal Tax skill file (versioned)

**Outputs**:
- Drake worksheet (Excel format)
- Preparer notes (markdown)
- Prior year comparison report
- Flagged items list

**Core Capabilities**:
1. Document extraction and classification
2. Data extraction from tax documents (W-2, 1099, 1098, K-1, etc.)
3. Schedule preparation (A, B, C, D, E, SE, etc.)
4. Tax calculation (AGI, taxable income, tax liability, credits)
5. Prior year comparison and variance analysis
6. Confidence scoring for uncertain items
7. Assumption documentation

**Skill File Structure**:
- Tax law references (current year)
- Form completion procedures
- Common scenarios and treatments
- Firm-specific preferences
- Quality checkpoints

**Error Handling**:
- Missing documents → escalate to human
- Ambiguous data → flag in preparer notes, proceed with assumption
- Calculation errors → escalate immediately
- Unusual scenarios → escalate for review

---

### Business Tax Agent

**Purpose**: Prepare business entity returns (1120, 1120-S, 1065) with K-1 schedules

**Inputs**:
- Entity profile (extends client profile)
- Financial statements (P&L, Balance Sheet)
- Supporting documents (1099s, W-2s, invoices, receipts)
- Prior year return (PDF)
- Business Tax skill file (versioned)

**Outputs**:
- Entity return worksheet (Excel format)
- K-1 schedules (if applicable)
- Preparer notes (markdown)
- Basis tracking worksheet
- Prior year comparison report

**Core Capabilities**:
1. Financial statement parsing
2. Expense categorization and verification
3. Depreciation calculations
4. Payroll reconciliation
5. K-1 generation (for partnerships/S-Corps)
6. Basis tracking and calculations
7. Entity-specific tax calculations
8. Prior year comparison

**Skill File Structure**:
- Entity type-specific procedures
- Depreciation methods and conventions
- Basis calculation rules
- K-1 preparation guidelines
- Firm-specific entity preferences

**Error Handling**:
- Missing financial statements → escalate
- Unreconciled accounts → flag in preparer notes
- Basis calculation discrepancies → escalate
- Complex transactions → escalate for review

---

### Bookkeeping Agent

**Purpose**: Categorize transactions, reconcile accounts, produce month-end reports

**Inputs**:
- Client/entity profile
- Transactions from QuickBooks (or CSV)
- Chart of accounts
- Prior period data
- Bookkeeping skill file (versioned)

**Outputs**:
- Categorized transactions report
- Bank reconciliation report
- Month-end checklist
- Variance analysis (vs prior periods)
- Flagged transactions list

**Core Capabilities**:
1. Transaction categorization (rules + ML)
2. Bank reconciliation
3. Account reconciliation
4. Variance analysis
5. Unusual transaction detection
6. Month-end checklist generation

**Skill File Structure**:
- Categorization rules
- Chart of accounts mapping
- Reconciliation procedures
- Variance thresholds
- Firm-specific bookkeeping preferences

**Error Handling**:
- Unreconciled items → flag in report
- Uncategorized transactions → flag for review
- Significant variances → flag with explanation
- Integration failures → escalate immediately

---

### Checker Agent

**Purpose**: Verify preparer work against source documents and prior year returns

**Inputs**:
- Preparer's work product (Drake worksheet, preparer notes)
- Source documents
- Prior year return (PDF)
- Checking Procedures skill file (versioned)

**Outputs**:
- Checker report (markdown)
- Flagged items (prioritized)
- Verification checklist
- Escalation recommendations

**Core Capabilities**:
1. Source document verification (numbers match)
2. Mathematical verification
3. Completeness checks (all required forms)
4. Prior year variance analysis
5. Reasonableness checks
6. Flag prioritization (critical, warning, info)

**Skill File Structure**:
- Verification procedures
- Variance thresholds
- Completeness checklists
- Flag prioritization rules
- Firm-specific checking standards

**Error Handling**:
- Critical errors → escalate immediately
- Warnings → flag in checker report
- Missing documents → flag in report
- Calculation errors → escalate

---

## Integration Specifications

### TaxDome Integration

**Approach**: REST API (preferred) or email-based task assignment

**API Endpoints** (if available):
- `GET /tasks/assigned` - Fetch assigned tasks
- `POST /tasks/{task_id}/status` - Update task status
- `POST /tasks/{task_id}/deliverables` - Upload work products
- `GET /clients/{client_id}` - Fetch client information

**Email-Based Alternative**:
- Monitor TaxDome email notifications
- Parse task assignment emails
- Send status updates via email
- Attach work products to email replies

**Status Mapping**:
- `pending` → TaxDome: "Assigned"
- `in_progress` → TaxDome: "In Progress"
- `completed` → TaxDome: "Ready for Review"
- `escalated` → TaxDome: "Needs Attention"
- `cancelled` → TaxDome: "Cancelled"

---

### QuickBooks Online Integration

**Authentication**: OAuth 2.0

**API Endpoints**:
- `GET /v3/company/{companyId}/query` - Query transactions
- `POST /v3/company/{companyId}/journalentries` - Create journal entries
- `GET /v3/company/{companyId}/accounts` - Fetch chart of accounts
- `GET /v3/company/{companyId}/reports` - Fetch financial reports

**Fallback**: CSV export/import for batch processing

**Data Flow**:
1. Authenticate with QuickBooks OAuth
2. Fetch transactions for specified date range
3. Categorize transactions (Bookkeeping Agent)
4. Generate reconciliation reports
5. Optionally create journal entries (with human approval)

---

### Drake Integration

**Phase 1**: Excel worksheet output (manual entry)

**Worksheet Format**:
- One sheet per form/schedule
- Columns map to Drake input fields
- Source references in comments
- Confidence indicators for uncertain values

**Phase 2** (Future): Direct XML import

**Research Required**:
- GruntWorx XML schema
- Drake import specifications
- Data validation requirements

**Current Approach**:
1. Generate structured Excel worksheet
2. Human enters data into Drake using worksheet
3. Human verifies accuracy
4. File return in Drake

---

### Document Storage Integration

**Google Drive / Dropbox**:

**Access Pattern**:
- Client folder structure: `ClientID_Name/Year/documents`
- Read-only access for document retrieval
- Document classification and extraction
- Store extracted data in database

**API Endpoints** (Google Drive example):
- `GET /files` - List files in folder
- `GET /files/{fileId}` - Download file
- `POST /files` - Upload file (if needed)

---

## Workflow & State Management

### Task Lifecycle

```
pending → in_progress → completed → reviewed → filed
                ↓
            escalated → resolved → in_progress
                ↓
            cancelled
```

### State Persistence

**Task State Storage**:
- Current step in workflow
- Extracted data (intermediate results)
- Decisions made (assumptions, classifications)
- Error context (if failed)
- Execution log (step-by-step trace)

**Recovery Strategy**:
- On agent crash: Restart from beginning (no partial state recovery)
- State stored in `task_states` table for debugging/monitoring
- Human can review execution log to understand progress

### Context Management

**Client Profile Loading**:
1. Query `client_profiles` table for `client_id`
2. Filter by `effective_date` (last 3 years)
3. Reconstruct current state by reading log forward
4. Generate summary for LLM context

**Skill File Loading**:
1. Query `skill_files` table for `agent_type`
2. Filter by `effective_date` (current date)
3. Load most recent version
4. Include in LLM context

**Document Loading**:
1. Query `documents` table for `client_id` and `tax_year`
2. Load file paths
3. Extract data (if not already extracted)
4. Include extracted data in context

---

## Error Handling & Escalation

### Error Classification

**Critical Errors** (immediate escalation):
- Calculation errors
- Missing required documents
- Data integrity issues
- System failures

**Warnings** (flag in work product):
- Ambiguous data (proceed with assumption)
- Unusual scenarios (document assumption)
- Low confidence extractions
- Significant prior year variances

**Info** (document in preparer notes):
- Minor variances
- Assumptions made
- Data sources used

### Escalation Protocol

1. **Error Detection**: Agent identifies error/warning
2. **Classification**: Determine severity (critical/warning/info)
3. **Context Collection**: Gather relevant data (documents, calculations, assumptions)
4. **Escalation**: 
   - Critical → Immediate notification to assigned CPA
   - Warning → Flag in work product, continue processing
   - Info → Document in preparer notes
5. **Human Response**: CPA reviews and provides guidance
6. **Resolution**: Agent continues with human input

### Error Recovery

**Agent Crash**:
- Task status → `failed`
- Execution log saved
- Human notified
- Task can be restarted (fresh start, no partial recovery)

**Human Interrupt**:
- CPA cancels task → Status → `cancelled`
- Agent stops processing immediately
- No speculative continuation

**Ambiguous Situation**:
- Agent escalates → Status → `escalated`
- Agent waits for human input
- If other tasks available, agent can work on those
- Agent does not guess on ambiguous situations

---

## Feedback & Learning Mechanisms

### Implicit Feedback (Automatic)

**Diff-Based Learning**:
1. Store AI's draft work product
2. Store final submitted work product (after CPA edits)
3. Compute diff between draft and final
4. Extract changes (what was corrected)
5. Store as feedback with context

**Implementation**:
- Compare Drake worksheets (cell-by-cell)
- Compare preparer notes (section-by-section)
- Identify changed values, added items, removed items
- Store changes with context (form, schedule, line item)

### Explicit Feedback (Optional)

**Lightweight Tags**:
- CPA can tag corrections with reasons:
  - `misclassified` - Wrong category/classification
  - `missing_context` - Needed additional information
  - `judgment_call` - Subjective decision required
  - `calculation_error` - Math mistake
  - `firm_preference` - Firm-specific rule not followed

**Interface**:
- Optional tagging during review
- No required fields (keeps it lightweight)
- Quick selection from predefined tags
- Optional free-text explanation

### Feedback Incorporation

**RAG-Based Learning**:
1. Store feedback in vector database (pgvector)
2. Embed feedback with context (client type, scenario, correction)
3. Retrieve relevant feedback when similar scenarios arise
4. Include in LLM context as "lessons learned"

**Skill File Updates**:
1. Analyze feedback patterns (scheduled, e.g., weekly)
2. Identify common errors or firm preferences
3. Update skill files with new guidance
4. Version skill files with effective dates

**Prompt Engineering**:
1. Incorporate feedback examples into prompts
2. Adjust confidence thresholds based on error rates
3. Refine escalation criteria based on feedback

---

## Security & Compliance

### Data Protection

**PII Handling**:
- Client data encrypted at rest (PostgreSQL encryption)
- Client data encrypted in transit (TLS)
- No client PII in LLM training data
- No client PII in logs (masked/hashed)

**Access Control**:
- Role-based access control (RBAC)
- CPA users can only access their firm's data
- Audit log of all data access

**Data Retention**:
- Client profiles: Last 3 years detailed, older archived
- Documents: Retained per firm policy
- Work products: Retained per firm policy
- Feedback: Retained indefinitely for learning

### Compliance Roadmap

**Phase 1** (v1):
- Basic security (encryption, access control)
- No PII in training data
- Audit logging

**Phase 2** (Post-v1):
- SOC 2 Type II certification
- Formal security audit
- Penetration testing
- Compliance framework (HIPAA if applicable)

---

## Monitoring & Observability

### Metrics

**Agent Performance**:
- Tasks completed per day/week
- Average completion time
- Error rate (by agent type)
- Escalation rate
- Cost per task (LLM tokens)

**Quality Metrics**:
- CPA review time
- Correction rate (implicit feedback)
- Accuracy rate (by return type)
- Confidence score distribution

**System Health**:
- API response times
- Database query performance
- Cache hit rates
- Error rates by type

### Logging

**Structured Logging** (JSON):
- Task execution logs
- Agent decision logs
- Error logs with stack traces
- API request/response logs

**Log Levels**:
- DEBUG: Detailed execution traces
- INFO: Normal operations
- WARNING: Recoverable issues
- ERROR: Failures requiring attention
- CRITICAL: System failures

### Status Dashboard

**Real-Time Status**:
- Current tasks by agent
- Task progress (step-by-step)
- Active escalations
- System health indicators

**Historical Views**:
- Task completion trends
- Error trends
- Performance over time
- Cost trends

---

## Appendices

### Appendix A: Client Profile Schema Reference

**Full Client Profile Structure** (JSON schema):

```json
{
  "identification": {
    "name": {
      "first": "string",
      "middle": "string",
      "last": "string",
      "suffix": "string"
    },
    "ssn": "string (masked)",
    "dob": "date",
    "address": {
      "street": "string",
      "city": "string",
      "state": "string",
      "zip": "string"
    },
    "filing_status": "string",
    "tax_id": "string"
  },
  "contact": {
    "email": "string",
    "phone": "string",
    "preferred_contact_method": "string"
  },
  "household": {
    "spouse": {
      "name": "string",
      "ssn": "string (masked)",
      "dob": "date"
    },
    "dependents": [
      {
        "name": "string",
        "ssn": "string (masked)",
        "dob": "date",
        "relationship": "string"
      }
    ]
  },
  "income_sources": {
    "w2_employers": [
      {
        "employer_name": "string",
        "ein": "string",
        "years_active": ["integer"]
      }
    ],
    "1099_sources": [
      {
        "payer_name": "string",
        "payer_tin": "string",
        "income_type": "string",
        "years_active": ["integer"]
      }
    ],
    "k1_sources": [
      {
        "entity_name": "string",
        "entity_type": "string",
        "years_active": ["integer"]
      }
    ],
    "other_income": [
      {
        "source": "string",
        "type": "string",
        "years_active": ["integer"]
      }
    ]
  },
  "deductions_credits": {
    "itemized_deductions": {
      "medical": "boolean",
      "state_local_tax": "boolean",
      "mortgage_interest": "boolean",
      "charitable_contributions": "boolean"
    },
    "credits": [
      {
        "credit_type": "string",
        "years_claimed": ["integer"]
      }
    ]
  },
  "tax_planning": {
    "estimated_tax_history": [
      {
        "year": "integer",
        "quarterly_payments": ["decimal"],
        "final_amount": "decimal"
      }
    ],
    "planning_opportunities": [
      {
        "year": "integer",
        "opportunity": "string",
        "status": "string"
      }
    ]
  },
  "historical_returns": {
    "last_3_years": [
      {
        "year": "integer",
        "agi": "decimal",
        "taxable_income": "decimal",
        "total_tax": "decimal",
        "refund_owed": "decimal",
        "filing_status": "string",
        "key_changes": ["string"]
      }
    ]
  },
  "preferences": {
    "filing_preferences": {
      "paper_filing": "boolean",
      "direct_deposit": "boolean",
      "refund_timing": "string"
    },
    "communication_preferences": {
      "preferred_method": "string",
      "response_time_expectation": "string"
    }
  },
  "red_flags": [
    {
      "year": "integer",
      "flag": "string",
      "resolution": "string",
      "recurring": "boolean"
    }
  ],
  "planning_opportunities": [
    {
      "year": "integer",
      "opportunity": "string",
      "status": "string",
      "notes": "string"
    }
  ]
}
```

**Profile Update Entry Format** (append-only log):

```json
{
  "entry_type": "profile_update",
  "author": "human:user_id" | "ai:agent_type",
  "timestamp": "ISO 8601",
  "updates": {
    "field_path": "identification.name.first",
    "old_value": "string",
    "new_value": "string",
    "reason": "string"
  },
  "effective_date": "date"
}
```

---

### Appendix B: Drake Worksheet Format Specification

**Excel Structure**:

**Sheet 1: Form 1040**
- Columns: `Line`, `Description`, `Amount`, `Source_Document`, `Confidence`, `Notes`
- Rows: One per line item on Form 1040

**Sheet 2: Schedule A** (if applicable)
- Same column structure
- Rows: One per deduction category

**Sheet 3: Schedule B** (if applicable)
- Same column structure
- Rows: One per interest/dividend source

**Additional Sheets**: One per schedule (C, D, E, SE, etc.)

**Column Definitions**:
- `Line`: Form/schedule line number
- `Description`: Human-readable description
- `Amount`: Dollar amount (formatted as currency)
- `Source_Document`: Reference to source document (e.g., "W-2: Employer ABC, Box 1")
- `Confidence`: Confidence score (0.00-1.00) or "HIGH"/"MEDIUM"/"LOW"
- `Notes`: Additional context, assumptions, or flags

**Example Row**:
```
Line: 1
Description: Wages, salaries, tips
Amount: $75,000.00
Source_Document: W-2: ABC Corp (EIN: 12-3456789), Box 1
Confidence: HIGH
Notes: Matches prior year employer
```

---

### Appendix C: Preparer Notes Template

**Standard Structure**:

```markdown
# Preparer Notes - [Client Name] - [Tax Year]

## Summary
- AGI: $[amount]
- Total Tax: $[amount]
- Refund/Owed: $[amount]
- Prior Year Comparison: [summary of changes]

## Data Sources Used
- W-2: [employer name] - Confidence: [HIGH/MEDIUM/LOW]
- 1099-INT: [payer name] - Confidence: [HIGH/MEDIUM/LOW]
- [Additional documents...]

## Flags/Questions
1. [Flag description] - Requires reviewer attention
2. [Question] - Needs clarification

## Assumptions Made
1. [Assumption] - Reasoning: [explanation]
2. [Assumption] - Reasoning: [explanation]

## Suggested Review Focus Areas
- [Area 1]: [reason]
- [Area 2]: [reason]

## Prior Year Comparison
- Significant Changes:
  - [Change 1]: [explanation]
  - [Change 2]: [explanation]
- Expected Changes:
  - [Change]: [explanation]
```

**Variations by Work Type**:
- Business returns: Include entity-specific sections (K-1 details, basis calculations)
- Bookkeeping: Include reconciliation details, variance explanations

---

### Appendix D: API Specification

**Base URL**: `https://api.rookie.cpa/v1`

**Authentication**: Bearer token (JWT)

**Endpoints**:

#### Tasks

- `GET /tasks` - List tasks (with filters)
- `GET /tasks/{task_id}` - Get task details
- `POST /tasks` - Create task (from TaxDome)
- `PATCH /tasks/{task_id}/status` - Update task status
- `GET /tasks/{task_id}/status` - Get real-time status

#### Client Profiles

- `GET /clients/{client_id}/profile` - Get current client profile
- `GET /clients/{client_id}/profile/history` - Get profile history (append-only log)
- `POST /clients/{client_id}/profile/entries` - Add profile entry (append-only)

#### Documents

- `POST /documents` - Upload document
- `GET /documents/{document_id}` - Get document metadata
- `GET /documents/{document_id}/file` - Download document file
- `GET /clients/{client_id}/documents` - List client documents

#### Work Products

- `GET /tasks/{task_id}/work-products` - List work products for task
- `GET /work-products/{product_id}/file` - Download work product file

#### Feedback

- `POST /tasks/{task_id}/feedback` - Submit feedback
- `GET /tasks/{task_id}/feedback` - Get feedback for task

#### Agent Status

- `GET /agents/status` - Get status of all agents
- `GET /agents/{agent_type}/status` - Get status of specific agent

---

### Appendix E: Error Codes Reference

**System Errors**:
- `SYS_001`: Database connection failure
- `SYS_002`: External API failure (QuickBooks, TaxDome)
- `SYS_003`: Document processing failure
- `SYS_004`: LLM API failure

**Task Errors**:
- `TASK_001`: Missing required documents
- `TASK_002`: Ambiguous data requiring human input
- `TASK_003`: Calculation error
- `TASK_004`: Invalid client profile data

**Agent Errors**:
- `AGENT_001`: Agent crash (unhandled exception)
- `AGENT_002`: Timeout (task took too long)
- `AGENT_003`: Context overflow (too much data)
- `AGENT_004`: Invalid skill file

**Integration Errors**:
- `INT_001`: TaxDome API failure
- `INT_002`: QuickBooks API failure
- `INT_003`: Document storage access failure
- `INT_004`: Authentication failure

---

### Appendix F: Skill File Versioning

**Version Format**: `MAJOR.MINOR.PATCH`

**Versioning Rules**:
- `MAJOR`: Breaking changes (tax law changes, major procedure changes)
- `MINOR`: New capabilities, non-breaking additions
- `PATCH`: Bug fixes, clarifications

**Effective Dates**:
- Each version has an `effective_date`
- System uses version effective for current date
- Historical tasks use version effective at task date

**Example**:
```
agent_type: personal_tax
version: 1.2.0
effective_date: 2026-01-01
content: [markdown content]
```

---

### Appendix G: Testing Strategy

**Unit Tests**:
- Agent logic (data extraction, calculations)
- Profile reconstruction from append-only log
- Document processing
- Worksheet generation

**Integration Tests**:
- Agent end-to-end workflows
- API endpoints
- Database operations
- External integrations (mocked)

**Validation Tests**:
- Parallel preparation (AI vs human) on test returns
- Accuracy verification
- Prior year comparison accuracy
- Error detection rates

**Load Tests**:
- Concurrent agent executions
- Database performance under load
- API response times
- LLM API rate limits

---

### Appendix H: Deployment Checklist

**Pre-Deployment**:
- [ ] All tests passing
- [ ] Security audit complete
- [ ] Documentation updated
- [ ] Backup/recovery tested
- [ ] Monitoring configured
- [ ] Error tracking configured

**Deployment**:
- [ ] Database migrations run
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] API keys configured
- [ ] External integrations tested

**Post-Deployment**:
- [ ] Health checks passing
- [ ] Monitoring dashboards active
- [ ] Error tracking active
- [ ] User access verified
- [ ] Pilot tasks assigned

---

## Conclusion

This master plan provides a comprehensive specification for building Rookie, an AI employee platform for CPA firms. The plan is self-contained and executable by any competent agent (Claude Code, Codex, or human developer) without requiring external context.

**Key Success Factors**:
1. Build it right (prioritize correctness over speed)
2. Treat AI as employee (expect supervision, learn from feedback)
3. Human-in-the-loop (CPA remains professionally liable)
4. Append-only logs (eliminate merge conflicts)
5. Gradual trust building (start simple, expand complexity)

**Next Steps**:
1. Review and approve this specification
2. Set up development environment (Phase 0)
3. Begin Phase 1 implementation (Personal Tax Agent)
4. Establish feedback loops early
5. Iterate based on operational experience

---

*Document Version: 1.0*  
*Last Updated: January 23, 2026*  
*Status: Ready for Implementation*
