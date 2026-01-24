# Rookie: AI Employee Platform for CPA Firms

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

---

## Purpose / Big Picture

Rookie is an AI-powered digital employee platform that performs actual accounting work under human supervision. Unlike chatbots that answer questions, Rookie agents prepare tax returns, categorize transactions, reconcile accounts, and produce work products indistinguishable from those of a competent junior staff member.

After this system is built, a CPA firm will be able to assign a tax return preparation task to an AI agent via TaxDome, and receive back a completed Drake-ready worksheet, preparer notes with flagged issues, and an updated client profile — all without human intervention until the review stage.

The platform treats AI agents exactly like new employees: they start with simple tasks, earn trust through demonstrated accuracy, and gradually take on more responsibility. Human CPAs remain the final gatekeepers for all client-facing work.

---

## Progress

- [ ] Phase 0: Project setup and infrastructure
- [ ] Phase 1: Core framework and skill system
- [ ] Phase 2: Personal Tax Agent (1040)
- [ ] Phase 3: Business Tax Agent (1120/1120-S/1065)
- [ ] Phase 4: Bookkeeping Agent
- [ ] Phase 5: Checker Agent capability
- [ ] Phase 6: Monitoring dashboard and advanced features

---

## Surprises & Discoveries

(To be updated during implementation)

---

## Decision Log

- Decision: Treat Rookie as independent project, not integrated with GAAPT initially
  Rationale: Cleaner architecture, easier to test in isolation, can integrate later when both systems are stable
  Date/Author: 2026-01-23 / Planning Session

- Decision: Use append-only log structure for client profile updates
  Rationale: Eliminates merge conflicts, provides full audit trail, can derive current state by reading forward
  Date/Author: 2026-01-23 / Planning Session

- Decision: Start with Drake worksheet output (human data entry) before XML automation
  Rationale: Most controllable, easiest to verify accuracy, doesn't require reverse-engineering GruntWorx schema
  Date/Author: 2026-01-23 / Planning Session

- Decision: Multi-agent architecture with domain specialization
  Rationale: Each agent can have focused skill files, clearer responsibility boundaries, easier to scale horizontally
  Date/Author: 2026-01-23 / Planning Session

- Decision: Python tech stack with FastAPI
  Rationale: Best ecosystem for AI/ML, mature agent frameworks, first-class LLM support, consistent with GAAPT
  Date/Author: 2026-01-23 / Planning Session

- Decision: Two-layer feedback capture (implicit diff + explicit optional tags)
  Rationale: Implicit always works without CPA effort; explicit captures reasoning when CPA chooses to provide it
  Date/Author: 2026-01-23 / Planning Session

---

## Outcomes & Retrospective

(To be completed at milestones)

---

## Context and Orientation

### What This System Does

Rookie provides AI agents that perform the work of junior accounting staff. Each agent specializes in a domain (personal tax, business tax, bookkeeping) and executes tasks assigned through the firm's workflow system (TaxDome). Agents read client profiles, source documents, and skill files to produce work products that human reviewers then approve, modify, or reject.

### Key Terminology

**Agent**: An AI worker specialized in a specific domain. Each agent has access to relevant skill files and can execute tasks within its domain. Agents are stateless between tasks but maintain context within a task through structured artifacts.

**Skill File**: A markdown document containing task-specific instructions, firm policies, decision trees, examples, and edge case handling. Skill files are versioned and have effective dates for tax law changes.

**Client Profile**: A structured markdown document (following CLIENT_SCHEMA.md) containing everything known about a client: identification, income sources, deductions, historical returns, preferences, red flags, and planning opportunities. Updated after each engagement.

**Client Living Doc**: The append-only activity log within a client's folder that records all interactions, decisions, and changes over time. Each entry has timestamp, author (human name or agent ID), entry type, and content.

**Work Product**: The output artifacts an agent produces: Drake worksheets, preparer notes, updated client profile entries, draft communications.

**Task**: A unit of work assigned to an agent, corresponding to a TaxDome job/project step. Examples: "Prepare 2025 1040 for Client 1011", "Categorize January 2026 transactions for Client 2045".

**Checker**: A review function (initially human, potentially AI later) that verifies preparer work against source documents and expected outcomes before final CPA review.

**Escalation**: When an agent encounters something it cannot resolve, it creates a structured question and waits for human guidance before proceeding.

### Current Firm Environment

The target firm uses:
- **Drake Tax** for tax preparation (desktop software, supports Excel/CSV imports for some data, GruntWorx integration for document processing)
- **QuickBooks Online** for bookkeeping (has REST API for transaction management)
- **TaxDome** for workflow management (has API for tasks, status updates, client data; can also assign email to virtual employees)

Document flow: Client documents arrive in cloud-synced folders (Google Drive or Dropbox), organized by client ID and tax year.

### File System Structure

    rookie/
    ├── backend/
    │   ├── src/
    │   │   ├── agents/                 # Agent implementations
    │   │   │   ├── base_agent.py       # Abstract base class
    │   │   │   ├── personal_tax.py     # 1040 preparation
    │   │   │   ├── business_tax.py     # 1120/1120-S/1065
    │   │   │   ├── bookkeeping.py      # Transaction categorization
    │   │   │   └── checker.py          # Review/verification
    │   │   ├── orchestrator/           # Task routing and management
    │   │   │   ├── dispatcher.py       # Routes tasks to agents
    │   │   │   ├── state_machine.py    # Task state management
    │   │   │   └── queue.py            # Job queue integration
    │   │   ├── integrations/           # External system connectors
    │   │   │   ├── taxdome.py          # TaxDome API client
    │   │   │   ├── quickbooks.py       # QBO API client
    │   │   │   ├── drake.py            # Drake worksheet generator
    │   │   │   └── storage.py          # Cloud storage (GDrive/Dropbox)
    │   │   ├── skills/                 # Skill file loader and parser
    │   │   │   ├── loader.py           # Loads and validates skill files
    │   │   │   └── registry.py         # Maps task types to skills
    │   │   ├── artifacts/              # Work product generation
    │   │   │   ├── drake_worksheet.py  # Drake-ready output format
    │   │   │   ├── preparer_notes.py   # Review notes generator
    │   │   │   └── client_profile.py   # Profile update handler
    │   │   ├── context/                # Context assembly
    │   │   │   ├── builder.py          # Builds agent context window
    │   │   │   ├── prior_year.py       # Prior year comparison
    │   │   │   └── document_reader.py  # Reads source docs (vision)
    │   │   ├── feedback/               # Learning from corrections
    │   │   │   ├── diff_analyzer.py    # Implicit feedback via diff
    │   │   │   └── tag_processor.py    # Explicit review tags
    │   │   ├── api/                    # FastAPI routes
    │   │   │   ├── tasks.py            # Task management endpoints
    │   │   │   ├── status.py           # Status and monitoring
    │   │   │   └── webhooks.py         # TaxDome/QBO callbacks
    │   │   └── db/                     # Database models and migrations
    │   └── tests/
    ├── skills/                         # Skill file library
    │   ├── personal_tax/
    │   │   ├── 1040_prep.md
    │   │   ├── schedule_c.md
    │   │   ├── schedule_e.md
    │   │   ├── aca_reconciliation.md
    │   │   └── qbi_deduction.md
    │   ├── business_tax/
    │   │   ├── 1120s_prep.md
    │   │   ├── 1065_prep.md
    │   │   ├── k1_generation.md
    │   │   └── basis_tracking.md
    │   ├── bookkeeping/
    │   │   ├── transaction_categorization.md
    │   │   ├── bank_reconciliation.md
    │   │   ├── month_end_close.md
    │   │   └── payroll_entries.md
    │   └── common/
    │       ├── firm_standards.md       # Firm-wide policies
    │       ├── communication_style.md  # How to write notes
    │       └── escalation_protocol.md  # When and how to escalate
    ├── clients/                        # Client data (mounted from cloud storage)
    │   └── [CLIENT_ID]_[NAME]/
    │       ├── profile.md              # Client profile (CLIENT_SCHEMA)
    │       ├── activity_log.md         # Append-only living doc
    │       └── [YEAR]/
    │           ├── source_docs/        # W-2s, 1099s, etc.
    │           ├── workpapers/         # Agent-produced artifacts
    │           └── final/              # Reviewed/approved outputs
    ├── templates/                      # Output templates
    │   ├── drake_worksheet.xlsx        # Drake data entry template
    │   ├── preparer_notes.md           # Notes template
    │   └── client_update.md            # Profile update template
    └── monitoring/                     # Status dashboard
        └── dashboard/                  # React/Next.js frontend

---

## Plan of Work

### Phase 0: Project Setup and Infrastructure

Establish the foundational infrastructure before any agent logic. This includes the database schema, job queue, API skeleton, and integration stubs.

Create the FastAPI application structure in `backend/src/` with placeholder routers. Set up PostgreSQL with tables for tasks, task_logs, agent_sessions, escalations, and feedback. Configure Redis for job queue and real-time status updates. Create integration stubs for TaxDome, QuickBooks, and cloud storage that initially use mock data.

Set up the skill file loader that reads markdown files from the `skills/` directory, parses front matter for metadata (effective dates, applicable forms, version), and validates required sections exist.

### Phase 1: Core Framework and Skill System

Build the agent base class and orchestration layer. The base agent defines the interface all specialized agents implement: `load_context()`, `execute_task()`, `produce_artifacts()`, `handle_escalation()`.

The dispatcher receives tasks (from API or queue), determines which agent type handles them based on task metadata, loads the appropriate skill files, assembles context (client profile, source documents, prior year data), and invokes the agent.

The state machine tracks task progress: `pending` → `assigned` → `in_progress` → `awaiting_human` (if escalated) → `completed` or `failed`. State transitions are logged with timestamps for the monitoring dashboard.

Implement the context builder that assembles everything an agent needs: client profile content, relevant skill files, source document contents (via vision API for PDFs/images), prior year return data (from final PDF), and current year documents list.

### Phase 2: Personal Tax Agent (1040)

The first fully functional agent handles individual tax return preparation. This is the highest volume work and has the clearest process.

The agent's workflow for a 1040 preparation task:

1. Load client profile and identify income sources, deductions, credits from prior history
2. Scan source documents folder for current year: W-2s, 1099s, K-1s, etc.
3. Extract data from each document using vision API
4. Compare extracted data to prior year profile — flag significant changes
5. Apply skill file instructions to determine treatment for each item
6. Generate Drake worksheet with line-by-line values and source references
7. Generate preparer notes: summary, data sources, flags, assumptions, review focus
8. Update client activity log with work performed
9. Update task status to completed, notify via TaxDome

Skill files for Personal Tax cover: basic 1040 flow, Schedule C (self-employment), Schedule E (rental), Schedule D (capital gains), ACA reconciliation (Form 8962), QBI deduction calculation, education credits, child tax credit, and firm-specific policies.

The Drake worksheet output is an Excel file formatted to match Drake's data entry screens. Each row contains: Drake screen name, field name, value, source document reference, and confidence level. Human enters data into Drake using this as a guide.

### Phase 3: Business Tax Agent (1120/1120-S/1065)

Extends the framework for business returns. More complex than personal due to: multi-entity structures, K-1 generation, basis tracking, and state apportionment.

The agent handles three return types with shared infrastructure but specialized skill files:
- **1120**: C-Corporation returns
- **1120-S**: S-Corporation returns with K-1 generation
- **1065**: Partnership returns with K-1 generation

Key additions beyond personal tax:
- Balance sheet reconciliation (Schedule L)
- M-1/M-3 book-tax adjustments
- Shareholder/partner basis tracking
- K-1 preparation for pass-through entities
- State filing requirements analysis

The agent must maintain awareness of related entities. If a client has both a business (1120-S) and personal return (1040), the K-1 from the business must flow correctly to the personal return.

### Phase 4: Bookkeeping Agent

Handles ongoing transaction categorization and reconciliation rather than point-in-time tax preparation.

Two integration modes:
- **API Mode**: Direct QuickBooks Online integration. Agent reviews uncategorized transactions, applies categorization rules, and posts categories back to QBO.
- **Batch Mode**: Processes exported CSV/Excel files. Agent categorizes and produces an import file or categorization report for human to apply.

Agent capabilities:
- Transaction categorization using firm's chart of accounts
- Vendor/payee recognition and consistent coding
- Anomaly detection (unusual amounts, unexpected vendors, missing expected transactions)
- Bank reconciliation support
- Month-end close checklist execution
- Accrual adjustments identification

The bookkeeping agent operates more continuously than tax agents — potentially processing daily transaction batches rather than seasonal return preparation.

### Phase 5: Checker Agent Capability

Adds AI-powered review as a layer between preparation and human final review. The Checker agent doesn't prepare work — it verifies work against source documents and expected patterns.

Checker functions:
- Verify all source document values appear correctly in work product
- Compare current year to prior year and flag unexplained variances
- Validate calculations (totals, percentages, carryforwards)
- Check for missing expected items (based on client profile history)
- Confirm all required forms are addressed
- Generate checker notes highlighting verified items and concerns

The Checker agent uses a different context than the preparer: it receives the work product as primary input, with source documents for verification. Its output is a pass/fail assessment with detailed notes.

Important: The Checker cannot approve work. Human reviewer remains the final gate. Checker merely adds a quality layer and focuses human attention on areas of concern.

### Phase 6: Monitoring Dashboard and Advanced Features

Build the monitoring UI that shows real-time agent status across all active tasks.

Dashboard views:
- **Queue Overview**: All pending, in-progress, and completed tasks with agent assignment
- **Agent Detail**: For each task, granular progress through checklist steps
- **Escalation Queue**: All items awaiting human input
- **Performance Metrics**: Completion rates, accuracy (based on revision rates), throughput

Advanced features for later expansion:
- **TaxDome deep integration**: Bi-directional sync of task status, automated job creation
- **Drake XML generation**: Direct import capability bypassing manual entry
- **Meeting prep integration**: Pre-call briefing documents
- **Client communication drafting**: Email templates for missing document requests

---

## Concrete Steps

### Phase 0 Commands

Set up project structure:

    mkdir -p rookie/backend/src/{agents,orchestrator,integrations,skills,artifacts,context,feedback,api,db}
    mkdir -p rookie/skills/{personal_tax,business_tax,bookkeeping,common}
    mkdir -p rookie/templates
    mkdir -p rookie/monitoring/dashboard
    cd rookie/backend
    uv venv
    source .venv/bin/activate
    uv pip install fastapi uvicorn asyncpg redis anthropic openai pydantic python-multipart openpyxl

Expected: Virtual environment created, dependencies installed.

Initialize FastAPI application in `backend/src/main.py`:

    uvicorn src.main:app --reload

Expected: Server starts on localhost:8000, returns {"status": "ok"} at root.

### Phase 1 Commands

After implementing core framework:

    pytest tests/test_skill_loader.py -v

Expected: Skill file loading tests pass, validates markdown parsing and metadata extraction.

    pytest tests/test_dispatcher.py -v

Expected: Task routing tests pass, correct agent selected for each task type.

### Phase 2 Commands

After implementing Personal Tax Agent:

    python -m src.cli.run_task --task-id test_1040 --client-id 1011 --dry-run

Expected: Agent loads context, processes documents, generates artifacts in `--dry-run` mode without persisting. Output shows Drake worksheet content and preparer notes.

Run against test client with known expected output:

    python -m src.cli.run_task --task-id prod_1040_1011 --client-id 1011

Expected: Artifacts written to `clients/1011_Nguyen_Ethan/2025/workpapers/`. Compare Drake worksheet to manually prepared return for same client to validate accuracy.

---

## Validation and Acceptance

### Phase 0 Acceptance

- FastAPI server starts and responds to health check
- Database migrations run successfully
- All placeholder routers return 501 Not Implemented
- Integration stubs can be instantiated with mock credentials

### Phase 1 Acceptance

- Skill loader parses all skill files in `skills/` directory without errors
- Skill loader correctly extracts effective dates and version metadata
- Dispatcher correctly routes test tasks to appropriate agent types
- State machine correctly transitions tasks through all states
- Context builder assembles client profile + skill files + document list

### Phase 2 Acceptance

- Personal Tax Agent processes test client 1011 (Nguyen, Ethan) and produces:
  - Drake worksheet with values matching 2024 return within 5% (assuming similar 2025 data)
  - Preparer notes identifying the ACA reconciliation risk (documented in profile)
  - Client activity log entry recording work performed
- Agent correctly escalates when encountering unknown document type
- Agent correctly flags when expected document (based on profile) is missing

### Phase 3 Acceptance

- Business Tax Agent processes test 1120-S client and produces:
  - Drake worksheet for business return
  - K-1 worksheets for each shareholder
  - Basis tracking schedule
- K-1 data can be used by Personal Tax Agent for shareholder's 1040

### Phase 4 Acceptance

- Bookkeeping Agent in batch mode:
  - Processes 100-transaction CSV export
  - Categorizes at least 90% with high confidence
  - Flags anomalies appropriately
  - Produces import-ready categorized file
- Bookkeeping Agent in API mode:
  - Connects to QBO sandbox
  - Reads uncategorized transactions
  - Posts categorizations back successfully

### Phase 5 Acceptance

- Checker Agent reviews Personal Tax Agent output and:
  - Correctly identifies intentionally introduced error (wrong W-2 amount)
  - Passes correctly prepared return
  - Generates checker notes with verification evidence

### Phase 6 Acceptance

- Dashboard displays real-time task status updates
- Escalation queue shows pending items with full context
- Performance metrics calculate accurately from task logs

---

## Idempotence and Recovery

All agent operations are designed to be safely re-runnable.

**Task restart**: If an agent fails mid-task, restarting the task begins fresh. The agent does not attempt to resume from partial state — it regenerates all artifacts from source documents. This is simpler than checkpointing and acceptable given task duration (minutes, not hours).

**Artifact overwrite**: Work products are written with task attempt number in filename (e.g., `drake_worksheet_attempt_2.xlsx`). Previous attempts are preserved for debugging but the latest is clearly identified.

**Client profile updates**: The activity log is append-only. Even if an agent runs twice for the same task, each run appends its own log entry. Duplicates are visible but not harmful.

**Database idempotency**: Task state transitions check current state before updating. Attempting to transition from `completed` to `in_progress` is rejected.

**Recovery from crash**: If the process dies mid-execution, the task remains in `in_progress` state. A supervisor process monitors for stuck tasks (in_progress for >30 minutes) and can reset them to `pending` for retry.

---

## Artifacts and Notes

### Example Drake Worksheet Entry

    Screen: W2
    Field: Wages (Box 1)
    Value: 122698.00
    Source: Kim_W2_AllHealth_2025.pdf, Box 1
    Confidence: HIGH
    Notes: Matches employer name in client profile
    
    Screen: SCHC
    Field: Gross Receipts
    Value: 40964.00
    Source: Calculated sum of 1099-NEC amounts
    Confidence: HIGH
    Notes: Amazing Nail (5717) + Nessha Love Nail (10562) + Texas Nail Bar (24685)

### Example Preparer Notes Structure

    # Preparer Notes: Client 1011 - Nguyen, Ethan & Kim
    ## Tax Year 2025 | Prepared by: PERSONAL_TAX_AGENT_v1
    ## Prepared: 2026-01-23 14:32:00 CST
    
    ### Summary
    - Filing Status: MFJ
    - Estimated AGI: $148,500 (up 3% from 2024)
    - Estimated Total Tax: $17,200
    - Estimated Refund: $1,100
    
    ### Data Sources Used
    | Document | Type | Confidence | Notes |
    |----------|------|------------|-------|
    | Kim_W2_AllHealth.pdf | W-2 | HIGH | Wages $122,698 |
    | Ethan_1099NEC_AmazingNail.pdf | 1099-NEC | HIGH | $5,717 |
    | Ethan_1099NEC_NesshaLoveNail.pdf | 1099-NEC | HIGH | $10,562 |
    | Ethan_1099NEC_TexasNailBar.pdf | 1099-NEC | HIGH | $24,685 |
    | 1099INT_Discover.pdf | 1099-INT | HIGH | $3,100 combined |
    | 1099DIV_Robinhood.pdf | 1099-DIV | MEDIUM | Small qualified dividends |
    
    ### Flags / Questions for Reviewer
    1. **ACA RECONCILIATION**: Client had $888 excess APTC repayment in 2024. 
       Verify 2025 APTC amounts and income estimate for potential repayment.
    2. **RENTAL PROPERTY**: Depreciation schedule continuing from prior year.
       Confirm no improvements or dispositions in 2025.
    3. **MILEAGE**: Profile shows 7,234 business miles in 2024. 
       No mileage log found in 2025 documents. Escalated to request from client.
    
    ### Assumptions Made
    - Filing status MFJ (same as prior year, no indication of change)
    - Standard deduction (itemized would require $31K+, client typically below)
    - Same daycare provider as prior year (no new receipt found, used profile info)
    
    ### Review Focus Areas
    - Schedule C expense categorization (supplies vs. other)
    - QBI deduction calculation (verify under threshold)
    - Estimated tax payments (2024 had large balance due)

### Example Client Activity Log Entry

    ---
    timestamp: 2026-01-23T14:32:00-06:00
    author: PERSONAL_TAX_AGENT_v1
    task_id: TASK_2025_1040_1011
    entry_type: WORK_COMPLETED
    
    content: |
      Completed first-pass preparation of 2025 Form 1040.
      
      Documents processed: 8
      - 1 W-2 (Kim - All Health LLC)
      - 3 1099-NEC (Ethan - nail salon income)
      - 2 1099-INT (Discover, PNC)
      - 1 1099-DIV (Robinhood)
      - 1 1098 (mortgage interest)
      
      Artifacts produced:
      - drake_worksheet_2025_attempt_1.xlsx
      - preparer_notes_2025.md
      
      Escalations created: 1
      - Missing 2025 business mileage documentation
      
      Prior year comparison:
      - AGI: +3% ($144,265 → estimated $148,500)
      - Schedule C net: roughly flat
      - Rental income: +5%
    ---

---

## Interfaces and Dependencies

### Core Dependencies

**Python Packages**:
- `fastapi` (0.109+): API framework
- `uvicorn`: ASGI server
- `asyncpg`: Async PostgreSQL driver
- `redis`: Redis client for queue and pub/sub
- `anthropic`: Claude API client
- `openai`: GPT/Whisper API client (backup LLM, vision)
- `pydantic` (2.0+): Data validation
- `openpyxl`: Excel file generation
- `python-multipart`: File uploads
- `httpx`: Async HTTP client for integrations

**External Services**:
- PostgreSQL 15+ (primary database)
- Redis 7+ (job queue, real-time updates)
- Anthropic API (Claude for agent reasoning)
- OpenAI API (GPT as backup, vision for documents)
- TaxDome API (workflow integration)
- QuickBooks Online API (bookkeeping integration)
- Cloud Storage (Google Drive or Dropbox API)

### Agent Interface

In `backend/src/agents/base_agent.py`:

    from abc import ABC, abstractmethod
    from dataclasses import dataclass
    from typing import List, Optional
    from enum import Enum
    
    class AgentType(Enum):
        PERSONAL_TAX = "personal_tax"
        BUSINESS_TAX = "business_tax"
        BOOKKEEPING = "bookkeeping"
        CHECKER = "checker"
    
    @dataclass
    class AgentContext:
        client_profile: str                    # Full markdown content
        skill_files: List[str]                 # List of skill file contents
        source_documents: List[DocumentData]   # Extracted document data
        prior_year_return: Optional[str]       # Prior year PDF extracted data
        task_metadata: dict                    # Task-specific parameters
    
    @dataclass
    class DocumentData:
        filename: str
        document_type: str                     # W2, 1099NEC, 1099INT, etc.
        extracted_data: dict                   # Structured extraction
        confidence: float
        raw_text: Optional[str]
    
    @dataclass
    class AgentOutput:
        artifacts: List[Artifact]              # Files produced
        activity_log_entry: str                # Entry for client log
        escalations: List[Escalation]          # Questions for human
        status: str                            # completed, escalated, failed
    
    @dataclass
    class Artifact:
        filename: str
        content: bytes
        artifact_type: str                     # drake_worksheet, preparer_notes, etc.
    
    @dataclass
    class Escalation:
        question: str
        context: str
        blocking: bool                         # Does agent wait or continue?
    
    class BaseAgent(ABC):
        agent_type: AgentType
        
        @abstractmethod
        async def load_context(self, task_id: str) -> AgentContext:
            """Assemble all context needed for task execution."""
            pass
        
        @abstractmethod
        async def execute(self, context: AgentContext) -> AgentOutput:
            """Perform the work and produce artifacts."""
            pass
        
        @abstractmethod
        def get_required_skills(self, task_metadata: dict) -> List[str]:
            """Return list of skill file paths needed for this task."""
            pass

### Skill File Format

Each skill file is markdown with YAML front matter:

    ---
    skill_id: personal_tax_1040_prep
    version: 2025.1
    effective_date: 2025-01-01
    expires_date: 2025-12-31
    applicable_forms: [1040, 1040-SR]
    author: Firm Tax Director
    last_reviewed: 2025-01-15
    ---
    
    # 1040 Preparation Skill
    
    ## Purpose
    Guide the agent through preparing a complete first-pass Form 1040...
    
    ## Prerequisites
    Before beginning, verify you have:
    - Client profile loaded
    - All source documents for the tax year
    - Prior year return PDF (if available)
    
    ## Step-by-Step Process
    
    ### Step 1: Document Inventory
    ...
    
    ## Firm-Specific Rules
    
    ### Standard vs Itemized Deduction
    Always calculate both and recommend itemized only if benefit exceeds $500...
    
    ## Common Edge Cases
    
    ### Self-Employment with Multiple 1099s
    ...
    
    ## Escalation Triggers
    Escalate to human reviewer if:
    - Foreign income (Form 2555)
    - AMT likely applies
    - Cryptocurrency transactions
    - Client profile indicates prior audit

### Database Schema

    -- Tasks table
    CREATE TABLE tasks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        external_id VARCHAR(255),           -- TaxDome job ID
        client_id VARCHAR(50) NOT NULL,
        task_type VARCHAR(50) NOT NULL,     -- 1040_prep, 1120s_prep, categorize, etc.
        tax_year INTEGER,
        assigned_agent VARCHAR(50),
        status VARCHAR(20) DEFAULT 'pending',
        attempt_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        metadata JSONB DEFAULT '{}'
    );
    
    -- Task state transitions log
    CREATE TABLE task_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID REFERENCES tasks(id),
        from_status VARCHAR(20),
        to_status VARCHAR(20),
        agent_id VARCHAR(50),
        message TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Escalations awaiting human response
    CREATE TABLE escalations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID REFERENCES tasks(id),
        question TEXT NOT NULL,
        context TEXT,
        blocking BOOLEAN DEFAULT true,
        status VARCHAR(20) DEFAULT 'pending',  -- pending, resolved, dismissed
        resolution TEXT,
        resolved_by VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        resolved_at TIMESTAMPTZ
    );
    
    -- Feedback from human corrections
    CREATE TABLE feedback (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        task_id UUID REFERENCES tasks(id),
        feedback_type VARCHAR(20),          -- implicit_diff, explicit_tag
        field_path VARCHAR(255),            -- What was corrected
        original_value TEXT,
        corrected_value TEXT,
        tag VARCHAR(50),                    -- misclassified, missing_context, judgment_call
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Agent performance metrics
    CREATE TABLE agent_metrics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_type VARCHAR(50),
        task_type VARCHAR(50),
        period_start DATE,
        period_end DATE,
        tasks_completed INTEGER,
        tasks_failed INTEGER,
        avg_duration_seconds INTEGER,
        revision_rate DECIMAL(5,2),         -- % of tasks with human corrections
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

### TaxDome Integration Interface

    class TaxDomeClient:
        async def get_pending_tasks(self, assignee_email: str) -> List[TaxDomeJob]:
            """Fetch jobs assigned to the AI employee email."""
            pass
        
        async def update_job_status(self, job_id: str, status: str, notes: str) -> None:
            """Update job status in TaxDome."""
            pass
        
        async def get_client_info(self, client_id: str) -> TaxDomeClient:
            """Fetch client details from TaxDome."""
            pass
        
        async def create_task(self, client_id: str, template_id: str) -> TaxDomeJob:
            """Create a new task/job in TaxDome."""
            pass

### QuickBooks Online Integration Interface

    class QuickBooksClient:
        async def get_uncategorized_transactions(
            self, 
            company_id: str,
            start_date: date,
            end_date: date
        ) -> List[QBOTransaction]:
            """Fetch transactions needing categorization."""
            pass
        
        async def categorize_transaction(
            self,
            company_id: str,
            transaction_id: str,
            account_id: str,
            memo: str
        ) -> None:
            """Apply category to a transaction."""
            pass
        
        async def get_chart_of_accounts(self, company_id: str) -> List[QBOAccount]:
            """Fetch company's chart of accounts for categorization."""
            pass
        
        async def export_transactions_csv(
            self,
            company_id: str,
            start_date: date,
            end_date: date
        ) -> bytes:
            """Export transactions for batch processing."""
            pass

---

## Milestones

### Milestone 1: Foundation Complete

**Scope**: Project structure, database, API skeleton, skill loader, integration stubs.

**Commands**:

    cd rookie/backend
    source .venv/bin/activate
    python -m src.db.migrate
    uvicorn src.main:app --reload
    # In another terminal:
    curl http://localhost:8000/health

**Acceptance**: Server returns `{"status": "ok", "database": "connected", "redis": "connected"}`. Skill loader parses all files in `skills/` directory.

### Milestone 2: Personal Tax Agent MVP

**Scope**: Full Personal Tax Agent that can process a known test client and produce accurate work products.

**Commands**:

    pytest tests/agents/test_personal_tax.py -v
    python -m src.cli.run_task --task-type 1040_prep --client-id 1011 --year 2025

**Acceptance**: Agent produces Drake worksheet and preparer notes for test client 1011. Manual comparison to expected output shows >95% field accuracy.

### Milestone 3: Business Tax Agent

**Scope**: Business Tax Agent handling 1120-S with K-1 generation.

**Commands**:

    pytest tests/agents/test_business_tax.py -v
    python -m src.cli.run_task --task-type 1120s_prep --client-id [business_client] --year 2025

**Acceptance**: Agent produces business return worksheet and K-1 worksheets. K-1 data is formatted for consumption by Personal Tax Agent.

### Milestone 4: Bookkeeping Agent

**Scope**: Bookkeeping Agent in both API and batch modes.

**Commands**:

    # Batch mode
    python -m src.cli.categorize --mode batch --input transactions.csv --output categorized.csv
    
    # API mode (sandbox)
    python -m src.cli.categorize --mode api --company-id [qbo_sandbox_id]

**Acceptance**: Batch mode categorizes 100 transactions with >90% accuracy. API mode successfully reads and writes to QBO sandbox.

### Milestone 5: Checker Agent

**Scope**: Checker Agent that reviews prepared work and catches intentional errors.

**Commands**:

    # Prepare a return with intentional error
    python -m src.cli.run_task --task-type 1040_prep --client-id 1011 --inject-error w2_wages
    
    # Run checker
    python -m src.cli.run_task --task-type check_1040 --client-id 1011

**Acceptance**: Checker correctly identifies the injected error. Checker passes correctly prepared returns.

### Milestone 6: Monitoring Dashboard

**Scope**: Web UI showing real-time agent status, queue depth, escalations, and metrics.

**Commands**:

    cd rookie/monitoring/dashboard
    npm install
    npm run dev
    # Open http://localhost:3000

**Acceptance**: Dashboard displays live task status updates. Escalation queue is functional. Metrics charts render accurately.

---

## Revision Notes

(To be updated when plan is revised)

---

## Appendix A: Client Profile Schema

The full CLIENT_SCHEMA.md defines the structure for client profiles. Key sections:

- **IDENTIFICATION**: client_id, names, filing status, SSN last 4
- **CONTACT INFORMATION**: address, phone, email, preferences
- **HOUSEHOLD**: dependents with relationships and DOBs
- **INCOME SOURCES**: W-2, Schedule C, Schedule E, investments, other
- **DEDUCTIONS & CREDITS**: itemized/standard, key credits, retirement, education, healthcare
- **TAX PLANNING IMPLEMENTED**: historical strategies and outcomes
- **HISTORICAL SUMMARY**: 3-year return history, carryforwards, audit history
- **CLIENT PREFERENCES & QUIRKS**: communication style, responsiveness, document delivery
- **RED FLAGS / ATTENTION ITEMS**: issues requiring special care
- **PLANNING OPPORTUNITIES**: future optimization possibilities

---

## Appendix B: Drake Worksheet Field Mapping

The Drake worksheet maps to Drake Tax data entry screens. Common screens:

- **W2**: Wage and tax statement entry
- **1099**: Interest, dividends, NEC, misc
- **SCHC**: Schedule C self-employment
- **SCHE**: Schedule E rental
- **SCHD**: Schedule D capital gains (or 8949 import)
- **8862**: Premium tax credit reconciliation
- **DEP**: Depreciation schedules
- **K1P/K1S/K1F**: K-1 entry (partnership, S-corp, fiduciary)

Each worksheet row contains: Screen, Field, Value, Source, Confidence, Notes.

---

## Appendix C: LLM Prompt Strategy

Agents use structured prompting with these components:

1. **System prompt**: Agent identity, capabilities, constraints, firm context
2. **Skill file injection**: Full text of relevant skill files
3. **Client context**: Profile summary, prior year highlights, current year document list
4. **Task instruction**: Specific work to perform
5. **Output format specification**: JSON schema for structured output

Example system prompt fragment:

    You are the Personal Tax Agent for [Firm Name], an AI employee that prepares 
    individual tax returns. You work under human supervision and never make final 
    determinations on ambiguous tax positions.
    
    Your role is to:
    - Extract data from source documents accurately
    - Apply firm-specific rules from skill files
    - Flag uncertainties rather than guess
    - Produce work products a human CPA can efficiently review
    
    You must escalate to human when:
    - Encountering document types not in your training
    - Finding inconsistencies you cannot resolve
    - Facing tax positions requiring professional judgment
    
    Your output must always include confidence levels and source references.

---

## Appendix D: Feedback Loop Architecture

Learning from corrections happens through two mechanisms:

**Implicit Feedback (Always Active)**:
1. After human review, system diffs AI-produced Drake worksheet against final entered values
2. Differences are logged in `feedback` table with field paths
3. Periodic analysis identifies systematic error patterns
4. Error patterns inform skill file updates or prompt refinements

**Explicit Feedback (Optional)**:
When correcting AI work, reviewer can add tags:
- `misclassified`: AI put data in wrong category
- `missing_context`: AI lacked information it needed
- `judgment_call`: Correct answer required professional judgment
- `ai_correct`: Human changed but AI was actually right (edge case documentation)

Tags help prioritize improvement efforts: `misclassified` suggests skill file gaps, `missing_context` suggests context builder improvements, `judgment_call` defines escalation boundaries.

---

## Appendix E: Security Considerations

**Data Access**:
- Agents access only assigned client data during task execution
- Client folders use filesystem permissions; agent process runs as limited user
- Source documents never leave the system (vision API calls are to documents in controlled storage)

**Audit Trail**:
- All task state transitions logged with timestamps
- All LLM API calls logged (prompt hash, response hash, tokens, latency)
- All file reads/writes logged
- Activity log entries are immutable (append-only)

**PII Handling**:
- Full SSNs never stored; only last 4 digits in profiles
- Logs redact SSN patterns before persistence
- Client names in logs can be pseudonymized for external analysis

**API Key Security**:
- LLM API keys stored in environment variables, not code
- Integration credentials (TaxDome, QBO) use OAuth where available
- Secrets rotated on schedule defined in operations runbook

