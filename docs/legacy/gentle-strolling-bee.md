# Rookie: Comprehensive Technical Specification

**Version**: 1.0
**Date**: January 23, 2026
**Status**: Master Plan - Ready for Implementation

---

## Executive Summary

Rookie is an AI employee platform for CPA firms that prepares tax returns, categorizes transactions, and reconciles accounts. It operates as a virtual junior staff member within existing workflows (TaxDome), learns from CPA corrections, and produces professional work products ready for human review.

**Core Philosophy**: Treat AI exactly like a new employee — mistakes are expected, feedback is provided, performance improves over time. Human remains the final gate; AI earns trust through demonstrated accuracy.

---

## Part 1: System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ROOKIE PLATFORM                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Personal    │  │  Business    │  │  Bookkeeping │              │
│  │  Tax Agent   │  │  Tax Agent   │  │  Agent       │              │
│  │  (1040)      │  │  (1120/1065) │  │  (QBO)       │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                        │
│         └────────────┬────┴────────────────┘                        │
│                      │                                               │
│              ┌───────▼───────┐                                       │
│              │  Orchestrator │                                       │
│              │    Layer      │                                       │
│              └───────┬───────┘                                       │
│                      │                                               │
│    ┌─────────┬───────┴────────┬──────────┬─────────┐               │
│    │         │                │          │         │                │
│ ┌──▼──┐  ┌───▼───┐  ┌────────▼───┐  ┌───▼───┐  ┌──▼──┐           │
│ │Skill│  │Client │  │  Document  │  │Feedback│  │State│           │
│ │Store│  │Profile│  │ Processing │  │ Loop   │  │Store│           │
│ └─────┘  │ Store │  └────────────┘  └────────┘  └─────┘           │
│          └───────┘                                                  │
├─────────────────────────────────────────────────────────────────────┤
│                     EXTERNAL INTEGRATIONS                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │
│  │ TaxDome │  │  QBO    │  │  Drake  │  │ Storage │               │
│  │  API    │  │  API    │  │ Export  │  │ (GDrive)│               │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend Framework** | Python + FastAPI | Best AI/ML ecosystem, mature agent frameworks |
| **Primary Database** | PostgreSQL | Persistent state, ACID compliance, JSONB support |
| **Cache/Realtime** | Redis | Status updates, session caching, pub/sub for monitoring |
| **Vector Database** | pgvector | RAG over documents and skills (PostgreSQL extension) |
| **Document Processing** | LLM Vision (Claude/GPT-4V) | Multi-model extraction capability |
| **LLM Providers** | Claude, OpenAI GPT, Gemini | No lock-in, use best model per task |
| **Task Queue** | Celery + Redis | Async task execution, retry handling |
| **File Storage** | Google Drive API | Client document access (synced folders) |

### 1.3 Deployment Model

- **v1.0**: Single-firm deployment (no multi-tenancy)
- **Hosting**: Cloud infrastructure (AWS/GCP - TBD)
- **Interface**: Standalone web application + API
- **Scaling**: Horizontal scaling of agent instances during tax season

---

## Part 2: Multi-Agent System Design

### 2.1 Agent Taxonomy

```
┌───────────────────────────────────────────────────────────────┐
│                      AGENT HIERARCHY                           │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  ORCHESTRATOR (coordinates work, routes tasks)                │
│       │                                                        │
│       ├── PERSONAL TAX AGENT                                  │
│       │       ├── 1040 Preparer                               │
│       │       ├── Schedule A/B/C/D/E Handler                  │
│       │       └── Prior Year Comparator                       │
│       │                                                        │
│       ├── BUSINESS TAX AGENT                                  │
│       │       ├── 1120 Corporate Preparer                     │
│       │       ├── 1120-S S-Corp Preparer                      │
│       │       ├── 1065 Partnership Preparer                   │
│       │       └── K-1 Generator                               │
│       │                                                        │
│       ├── BOOKKEEPING AGENT                                   │
│       │       ├── Transaction Categorizer                     │
│       │       ├── Reconciliation Engine                       │
│       │       └── Month-End Processor                         │
│       │                                                        │
│       └── CHECKER AGENT (verification, not approval)          │
│               ├── Source Document Validator                   │
│               ├── Prior Year Variance Analyzer                │
│               └── Completeness Checker                        │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

### 2.2 Agent Responsibilities

#### Personal Tax Agent (Priority 1 - Build First)
- Load client profile and prior year return (PDF)
- Scan client folder for current year documents
- Extract data from W-2s, 1099s, K-1s using vision
- Execute 1040 preparation checklist
- Produce Drake worksheet (Excel format)
- Generate preparer notes with confidence levels
- Compare to prior year, flag significant changes

#### Business Tax Agent
- Handle 1120, 1120-S, 1065 returns
- Generate K-1 schedules for partners/shareholders
- Track basis across years
- Integrate with bookkeeping data

#### Bookkeeping Agent
- Categorize QuickBooks transactions
- Reconcile bank accounts
- Process month-end checklists
- Generate variance reports

#### Checker Agent
- Verify numbers against source documents
- Analyze variances from prior year
- Flag items without documented reasons
- **Cannot approve** — human is always final gate

### 2.3 Task Routing & Assignment

**Who assigns tasks?** CPA (or senior employee) explicitly assigns via TaxDome.

**Flow:**
1. CPA assigns task in TaxDome to "Rookie" employee
2. Rookie receives notification (API or email trigger)
3. Orchestrator routes to appropriate agent based on task type
4. Agent executes, produces artifacts
5. Task status updates in TaxDome
6. Human reviews, provides feedback

### 2.4 Error Recovery Philosophy

| Scenario | Handling |
|----------|----------|
| Agent crashes mid-task | **Start over from beginning** (no partial state) |
| Ambiguous situation | Escalate to human, wait for instructions |
| Human redirects mid-task | Confirm cancel, then follow new direction |
| API failure | Retry with exponential backoff, then escalate |

---

## Part 3: Data Architecture

### 3.1 Core Database Schema

```sql
-- Clients (append-only log pattern for history)
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(50) NOT NULL, -- Firm's client ID
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Client profile entries (append-only log)
CREATE TABLE client_profile_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    entry_timestamp TIMESTAMP DEFAULT NOW(),
    author_type VARCHAR(10) NOT NULL, -- 'human' or 'ai'
    author_id VARCHAR(100),
    entry_type VARCHAR(50) NOT NULL, -- 'identification', 'income_source', 'flag', etc.
    content JSONB NOT NULL,
    tax_year INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_profile_client_time ON client_profile_entries(client_id, entry_timestamp DESC);

-- Tasks assigned to agents
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(100), -- TaxDome task ID
    client_id UUID REFERENCES clients(id),
    task_type VARCHAR(50) NOT NULL, -- '1040_prep', 'bookkeeping', etc.
    agent_type VARCHAR(50) NOT NULL, -- 'personal_tax', 'business_tax', 'bookkeeping'
    status VARCHAR(20) DEFAULT 'pending',
    assigned_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_tasks_status ON tasks(status, agent_type);

-- Task artifacts (work products)
CREATE TABLE task_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    artifact_type VARCHAR(50) NOT NULL, -- 'drake_worksheet', 'preparer_notes', etc.
    file_path TEXT,
    content JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Feedback entries (for learning)
CREATE TABLE feedback_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    feedback_type VARCHAR(20) NOT NULL, -- 'implicit' or 'explicit'
    original_content JSONB,
    corrected_content JSONB,
    diff_summary TEXT,
    review_tags JSONB, -- ['misclassified', 'missing_context', 'judgment_call']
    reviewer_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Skill files (versioned)
CREATE TABLE skill_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    effective_date DATE NOT NULL,
    content TEXT NOT NULL, -- Markdown/YAML skill definition
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(skill_name, version)
);

-- Agent execution logs
CREATE TABLE agent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    agent_type VARCHAR(50),
    log_level VARCHAR(10), -- 'info', 'warning', 'error'
    message TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_agent_logs_task ON agent_logs(task_id, created_at);
```

### 3.2 Vector Storage (pgvector)

```sql
-- Document embeddings for RAG
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    document_type VARCHAR(50),
    document_year INTEGER,
    file_path TEXT,
    chunk_index INTEGER,
    content TEXT,
    embedding vector(1536), -- OpenAI ada-002 dimension
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_doc_embeddings ON document_embeddings USING ivfflat (embedding vector_cosine_ops);

-- Skill embeddings for semantic routing
CREATE TABLE skill_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skill_files(id),
    content TEXT,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3.3 Redis Keys Structure

```
# Task status (real-time monitoring)
task:{task_id}:status         -> JSON {status, progress_pct, current_step}
task:{task_id}:heartbeat      -> TIMESTAMP (agent liveness)

# Agent status
agent:{agent_type}:active     -> SET of active task_ids
agent:{agent_type}:queue      -> LIST of pending task_ids

# Client profile cache (3-year window)
client:{client_id}:profile    -> JSON (computed from append-log)
client:{client_id}:documents  -> SET of document paths

# Rate limiting
llm:api:{provider}:tokens     -> INT (token counter with TTL)
```

---

## Part 4: Client Profile System

### 4.1 Profile Schema (CLIENT_SCHEMA.md Reference)

```yaml
client_profile:
  # Core Identification
  identification:
    client_id: string
    full_name: string
    ssn_last4: string
    dob: date
    filing_status: enum [single, mfj, mfs, hoh, qw]

  # Contact Information
  contact:
    primary_phone: string
    email: string
    preferred_contact: enum [phone, email, text]
    best_contact_time: string

  # Address
  address:
    street: string
    city: string
    state: string
    zip: string
    county: string
    school_district: string  # For state returns

  # Household
  household:
    spouse:
      name: string
      ssn_last4: string
      dob: date
      occupation: string
    dependents:
      - name: string
        ssn_last4: string
        dob: date
        relationship: string
        months_lived_with: integer

  # Income Sources (append-only, year-tagged)
  income_sources:
    - type: enum [w2, 1099_misc, 1099_nec, 1099_int, 1099_div, k1, rental, business]
      payer_name: string
      approximate_amount: decimal
      years_present: list[integer]
      notes: string

  # Deductions & Credits History
  deductions:
    itemizes: boolean
    typical_items:
      - category: string
        typical_amount: decimal
        documentation_notes: string

  # Tax Planning History
  planning:
    estimated_payments: boolean
    withholding_strategy: string
    planning_opportunities_identified: list[string]

  # Historical Return Summary (last 3 years)
  return_history:
    - year: integer
      agi: decimal
      total_tax: decimal
      refund_or_owed: decimal
      notable_items: list[string]

  # Client Preferences
  preferences:
    communication_style: string
    deadline_sensitivity: enum [early_filer, standard, extension_typical]
    document_delivery: enum [organized, scattered, needs_reminder]

  # Red Flags & Special Situations
  red_flags:
    - description: string
      identified_date: date
      resolution: string

  # Planning Opportunities
  opportunities:
    - description: string
      potential_savings: decimal
      discussed_with_client: boolean
```

### 4.2 Profile Management Rules

1. **Retention**: Last 3 years of detailed data; older years archived to summary
2. **Static vs Dynamic**: Identification/contact rarely change; income/deductions annual
3. **Conflict Resolution**: Append-only log eliminates merge conflicts
4. **Pre-Task Loading**: Agent reads profile before starting any work
5. **Post-Task Update**: Agent appends relevant updates upon completion

---

## Part 5: Integration Specifications

### 5.1 TaxDome Integration

**Option A: API Integration (Preferred)**
```python
# TaxDome Webhook Handler
@app.post("/webhooks/taxdome/task-assigned")
async def handle_task_assigned(payload: TaxDomeTaskPayload):
    """
    Triggered when CPA assigns task to Rookie in TaxDome.
    """
    task = Task(
        external_id=payload.task_id,
        client_id=resolve_client(payload.client_id),
        task_type=map_task_type(payload.job_template),
        agent_type=route_to_agent(payload.job_template),
        status="pending"
    )
    await db.save(task)
    await task_queue.enqueue(task)
    return {"status": "accepted"}

# TaxDome Status Updates
async def update_taxdome_status(task: Task, status: str):
    await taxdome_client.update_job_status(
        job_id=task.external_id,
        status=map_to_taxdome_status(status),
        notes=generate_status_notes(task)
    )
```

**Option B: Email Trigger (Fallback)**
- Rookie assigned dedicated email address
- Email parser extracts task details
- Less real-time but simpler setup

### 5.2 QuickBooks Online Integration

```python
# QBO Client (OAuth 2.0)
class QBOClient:
    def __init__(self, realm_id: str, access_token: str):
        self.base_url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}"
        self.headers = {"Authorization": f"Bearer {access_token}"}

    async def get_transactions(
        self,
        start_date: date,
        end_date: date
    ) -> list[Transaction]:
        """Fetch transactions for categorization."""
        query = f"""
        SELECT * FROM Transaction
        WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'
        """
        response = await self._query(query)
        return [Transaction.from_qbo(t) for t in response]

    async def get_accounts(self) -> list[Account]:
        """Fetch chart of accounts for reconciliation."""
        response = await self._get("/account")
        return [Account.from_qbo(a) for a in response["QueryResponse"]["Account"]]

    async def update_transaction_category(
        self,
        txn_id: str,
        category_id: str
    ):
        """Update transaction categorization."""
        # Batch updates via CSV import (fallback if API rate limited)
        pass
```

### 5.3 Drake Tax Integration

**Phase 1: Worksheet Export (v1.0)**
```python
# Drake Worksheet Generator
class DrakeWorksheetGenerator:
    """
    Generates Excel worksheet formatted for Drake data entry.
    Maps to Drake screen fields for manual entry.
    """

    FIELD_MAPPING = {
        # Form 1040 Main
        "1040_line1": "Wages (W-2 Box 1)",
        "1040_line2a": "Tax-exempt interest",
        "1040_line2b": "Taxable interest",
        "1040_line3a": "Qualified dividends",
        "1040_line3b": "Ordinary dividends",
        # ... complete mapping
    }

    def generate(self, prepared_data: PreparedReturn) -> bytes:
        """
        Returns Excel file bytes ready for download.
        Format: Screen-by-screen entry guide with source references.
        """
        wb = openpyxl.Workbook()

        # Sheet 1: Entry Summary
        ws_summary = wb.active
        ws_summary.title = "Entry Summary"
        self._add_summary_sheet(ws_summary, prepared_data)

        # Sheet 2: Detailed by Form
        ws_detail = wb.create_sheet("Form Details")
        self._add_form_details(ws_detail, prepared_data)

        # Sheet 3: Source References
        ws_sources = wb.create_sheet("Sources")
        self._add_source_references(ws_sources, prepared_data)

        return self._to_bytes(wb)
```

**Phase 2: Direct XML Import (Future)**
- Research GruntWorx XML schema
- Generate compliant XML for automated import
- Requires proven accuracy before automation

### 5.4 Google Drive Integration

```python
# Document Scanner
class ClientDocumentScanner:
    """
    Scans client folder structure:
    /ClientID_Name/Year/documents
    """

    def __init__(self, drive_service, base_folder_id: str):
        self.drive = drive_service
        self.base = base_folder_id

    async def get_client_documents(
        self,
        client_id: str,
        tax_year: int
    ) -> list[Document]:
        """Retrieve all documents for client's tax year."""
        folder_path = f"{client_id}/{tax_year}"
        files = await self._list_folder(folder_path)

        documents = []
        for file in files:
            doc = Document(
                name=file["name"],
                mime_type=file["mimeType"],
                path=file["path"],
                modified_time=file["modifiedTime"]
            )
            # Classify document type using vision
            doc.document_type = await self._classify_document(doc)
            documents.append(doc)

        return documents
```

---

## Part 6: Document Processing Pipeline

### 6.1 Vision-Based Extraction

```python
# Document Extractor
class DocumentExtractor:
    """
    Uses LLM vision to extract structured data from tax documents.
    """

    DOCUMENT_PROMPTS = {
        "W2": """
            Extract all fields from this W-2:
            - Box 1: Wages
            - Box 2: Federal tax withheld
            - Box 3: Social Security wages
            - Box 4: Social Security tax withheld
            ... (all boxes)

            Return JSON with confidence scores per field.
        """,
        "1099-INT": """...""",
        "1099-DIV": """...""",
        "K-1": """...""",
    }

    async def extract(
        self,
        document: Document,
        document_type: str
    ) -> ExtractionResult:
        """
        Extract structured data with confidence scores.
        """
        prompt = self.DOCUMENT_PROMPTS[document_type]
        image_data = await self._load_document_image(document)

        response = await self.llm.vision_extract(
            image=image_data,
            prompt=prompt,
            response_format="json"
        )

        return ExtractionResult(
            document=document,
            extracted_data=response["data"],
            confidence_scores=response["confidence"],
            extraction_notes=response.get("notes", [])
        )
```

### 6.2 Confidence Scoring

```python
@dataclass
class ConfidenceLevel:
    HIGH = "high"      # >90% confident, proceed automatically
    MEDIUM = "medium"  # 70-90%, proceed with flag
    LOW = "low"        # <70%, escalate for human review

class ConfidenceEvaluator:
    """
    Evaluates extraction confidence based on:
    1. LLM self-reported confidence
    2. Cross-document validation
    3. Prior year comparison
    4. Reasonableness checks
    """

    def evaluate(
        self,
        extraction: ExtractionResult,
        client_profile: ClientProfile,
        prior_year: Optional[ReturnData]
    ) -> ConfidenceAssessment:

        factors = []

        # LLM confidence
        llm_conf = extraction.confidence_scores.get("overall", 0.5)
        factors.append(("llm_self_report", llm_conf))

        # Cross-validation (does employer name match W-2 to prior year?)
        if prior_year:
            match_score = self._compare_employers(extraction, prior_year)
            factors.append(("employer_match", match_score))

        # Reasonableness (wages within expected range?)
        if client_profile.income_sources:
            reasonableness = self._check_reasonableness(
                extraction,
                client_profile
            )
            factors.append(("reasonableness", reasonableness))

        overall = self._weighted_average(factors)

        return ConfidenceAssessment(
            level=self._to_level(overall),
            score=overall,
            factors=factors,
            flags=self._generate_flags(factors)
        )
```

---

## Part 7: Workflow Engine

### 7.1 Task Execution Flow

```python
# Agent Base Class
class BaseAgent:
    """Base class for all Rookie agents."""

    async def execute(self, task: Task) -> TaskResult:
        """
        Standard execution flow for all agents.
        """
        try:
            # 1. Load context
            client = await self.load_client_profile(task.client_id)
            documents = await self.scan_client_documents(task)
            skill = await self.load_skill_file(task.task_type)

            # 2. Execute preparation
            result = await self.prepare(
                task=task,
                client=client,
                documents=documents,
                skill=skill
            )

            # 3. Generate artifacts
            artifacts = await self.generate_artifacts(result)

            # 4. Prior year comparison
            comparison = await self.compare_prior_year(result, client)

            # 5. Update client profile
            await self.update_client_profile(client, result)

            # 6. Update task status
            await self.complete_task(task, artifacts, comparison)

            return TaskResult(success=True, artifacts=artifacts)

        except RecoverableError as e:
            await self.handle_error(task, e)
            raise
        except Exception as e:
            # Unrecoverable - fail task, notify humans
            await self.fail_task(task, e)
            raise

    @abstractmethod
    async def prepare(self, **kwargs) -> PreparedData:
        """Agent-specific preparation logic."""
        pass
```

### 7.2 1040 Preparation Workflow

```python
class PersonalTaxAgent(BaseAgent):
    """Agent for preparing individual 1040 returns."""

    async def prepare(
        self,
        task: Task,
        client: ClientProfile,
        documents: list[Document],
        skill: SkillFile
    ) -> PreparedReturn:
        """
        1040 preparation following firm's checklist.
        """
        prepared = PreparedReturn(client=client, tax_year=task.tax_year)

        # Step 1: Document extraction
        for doc in documents:
            extraction = await self.extractor.extract(doc, doc.document_type)
            prepared.add_extraction(extraction)

        # Step 2: Income aggregation
        prepared.income = self.aggregate_income(prepared.extractions)

        # Step 3: Deduction calculation
        prepared.deductions = await self.calculate_deductions(
            client=client,
            extractions=prepared.extractions,
            skill=skill
        )

        # Step 4: Credit evaluation
        prepared.credits = await self.evaluate_credits(
            client=client,
            prepared=prepared,
            skill=skill
        )

        # Step 5: Tax calculation
        prepared.tax = self.calculate_tax(prepared)

        # Step 6: Generate flags
        prepared.flags = self.generate_flags(prepared, client)

        return prepared
```

### 7.3 Preparer Notes Structure

```python
@dataclass
class PreparerNotes:
    """
    Human-readable notes accompanying prepared work.
    """

    # Summary
    summary: ReturnSummary  # AGI, total tax, refund/owed, YoY comparison

    # Data sources used
    sources: list[DataSource]  # Documents with confidence levels

    # Items requiring attention
    flags: list[Flag]  # Questions, concerns, unusual items

    # Assumptions made
    assumptions: list[Assumption]  # With reasoning

    # Suggested review focus
    review_focus: list[str]  # Priority areas for checker/reviewer

    def to_markdown(self) -> str:
        """Format as markdown for human consumption."""
        return f"""
# Preparer Notes: {self.summary.client_name} - {self.summary.tax_year}

## Summary
- **AGI**: ${self.summary.agi:,.2f}
- **Total Tax**: ${self.summary.total_tax:,.2f}
- **Refund/(Owed)**: ${self.summary.refund_or_owed:,.2f}
- **Prior Year Comparison**: {self.summary.yoy_comparison}

## Data Sources
{self._format_sources()}

## Flags & Questions
{self._format_flags()}

## Assumptions Made
{self._format_assumptions()}

## Suggested Review Focus
{self._format_review_focus()}
        """
```

---

## Part 8: Feedback & Learning System

### 8.1 Two-Layer Feedback Capture

```python
class FeedbackCapture:
    """
    Captures CPA corrections for learning.

    Layer 1 (Implicit): Diff AI draft against final submitted version
    Layer 2 (Explicit): Optional tags explaining corrections
    """

    async def capture_implicit(
        self,
        task: Task,
        ai_output: PreparedReturn,
        final_output: PreparedReturn
    ):
        """
        Automatically diff AI work against final version.
        """
        diff = self.compute_diff(ai_output, final_output)

        if diff.has_changes:
            feedback = FeedbackEntry(
                task_id=task.id,
                feedback_type="implicit",
                original_content=ai_output.to_json(),
                corrected_content=final_output.to_json(),
                diff_summary=diff.summary
            )
            await self.db.save(feedback)

    async def capture_explicit(
        self,
        task: Task,
        correction: Correction,
        tags: list[str]
    ):
        """
        Optional: CPA explains why correction was made.

        Tags: ['misclassified', 'missing_context', 'judgment_call',
               'tax_law_update', 'client_specific']
        """
        feedback = FeedbackEntry(
            task_id=task.id,
            feedback_type="explicit",
            original_content=correction.original,
            corrected_content=correction.corrected,
            review_tags=tags,
            reviewer_id=correction.reviewer_id
        )
        await self.db.save(feedback)
```

### 8.2 Learning Integration (Future)

```python
# Placeholder for learning mechanism
# Options to evaluate:
# 1. Prompt engineering (incorporate feedback into system prompts)
# 2. RAG over feedback corpus
# 3. Fine-tuning (when data volume sufficient)
# 4. RLHF (most complex, highest quality)

class LearningEngine:
    """
    Scheduled incorporation of CPA feedback.
    Specific mechanism TBD based on data patterns.
    """

    async def process_feedback_batch(
        self,
        since: datetime
    ) -> LearningUpdate:
        """
        Process accumulated feedback.
        Run on schedule (weekly or after significant volume).
        """
        entries = await self.db.get_feedback_since(since)

        # Analyze patterns
        patterns = self.analyze_patterns(entries)

        # Generate learning updates
        updates = self.generate_updates(patterns)

        # Apply to skill files or prompts
        await self.apply_updates(updates)

        return LearningUpdate(
            entries_processed=len(entries),
            patterns_identified=patterns,
            updates_applied=updates
        )
```

---

## Part 9: Monitoring & Status Dashboard

### 9.1 Real-Time Status API

```python
# Status Endpoints
@app.get("/api/status/tasks")
async def get_task_status(
    status: Optional[str] = None,
    agent_type: Optional[str] = None
) -> list[TaskStatus]:
    """
    Get current task statuses for monitoring dashboard.
    More granular than TaxDome's native views.
    """
    tasks = await db.query_tasks(status=status, agent_type=agent_type)

    return [
        TaskStatus(
            task_id=t.id,
            client_name=t.client.name,
            task_type=t.task_type,
            agent_type=t.agent_type,
            status=t.status,
            progress_pct=await redis.get(f"task:{t.id}:progress"),
            current_step=await redis.get(f"task:{t.id}:current_step"),
            started_at=t.started_at,
            estimated_completion=t.estimated_completion
        )
        for t in tasks
    ]

@app.get("/api/status/agents")
async def get_agent_status() -> list[AgentStatus]:
    """
    Get status of all agent instances.
    """
    agents = ["personal_tax", "business_tax", "bookkeeping", "checker"]

    return [
        AgentStatus(
            agent_type=agent,
            active_tasks=await redis.scard(f"agent:{agent}:active"),
            queue_depth=await redis.llen(f"agent:{agent}:queue"),
            last_heartbeat=await redis.get(f"agent:{agent}:heartbeat")
        )
        for agent in agents
    ]
```

### 9.2 Dashboard UI Requirements

```
┌────────────────────────────────────────────────────────────────┐
│                    ROOKIE MONITOR                               │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AGENT STATUS                           QUEUE DEPTH            │
│  ┌─────────────────────────────┐       ┌──────────────────┐   │
│  │ Personal Tax: 3 active      │       │ 12 pending       │   │
│  │ Business Tax: 1 active      │       │ 4 in progress    │   │
│  │ Bookkeeping: 2 active       │       │ 28 completed     │   │
│  │ Checker: 0 active           │       │ today            │   │
│  └─────────────────────────────┘       └──────────────────┘   │
│                                                                 │
│  ACTIVE TASKS                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Client         │ Task        │ Progress │ Step          │   │
│  │ Smith, John    │ 1040 Prep   │ 75%      │ Calculating   │   │
│  │ ABC Corp       │ 1120-S      │ 30%      │ Extracting    │   │
│  │ Johnson LLC    │ Bookkeeping │ 90%      │ Reconciling   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  FLAGS REQUIRING ATTENTION                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ! Smith - Large YoY variance in wages ($15k decrease)   │   │
│  │ ! Garcia - Missing 1099-DIV (expected from Vanguard)   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Part 10: Security & Compliance

### 10.1 Security Requirements (v1.0)

| Requirement | Implementation |
|-------------|----------------|
| **PII Protection** | No client PII in AI training; data stays in firm systems |
| **Audit Trail** | Full logging of all agent actions in `agent_logs` table |
| **Access Control** | Role-based access; agents access only assigned clients |
| **Encryption** | TLS in transit; encryption at rest for database |
| **API Security** | OAuth 2.0 for external integrations; API key rotation |

### 10.2 Compliance Roadmap (Post-v1.0)

- **SOC 2 Type I**: Q3 2026 (after core functionality proven)
- **SOC 2 Type II**: Q4 2026
- **State-specific compliance**: As needed per firm location

### 10.3 Data Retention

```python
class DataRetentionPolicy:
    """
    Data retention aligned with tax record requirements.
    """

    # Client profile: 3 years detailed, then summary
    PROFILE_DETAIL_YEARS = 3

    # Completed tasks: 7 years (IRS audit window)
    TASK_RETENTION_YEARS = 7

    # Agent logs: 1 year (operational)
    LOG_RETENTION_YEARS = 1

    # Feedback entries: 3 years (learning purposes)
    FEEDBACK_RETENTION_YEARS = 3
```

---

## Part 11: Development Phases

### Phase 1: Foundation (4 weeks)
**Goal**: Core infrastructure with database, API skeleton, basic agent framework

**Plans**:
- 01-01: Database schema + migrations
- 01-02: FastAPI project structure + config
- 01-03: Redis setup + task queue foundation
- 01-04: Base agent class + task execution flow
- 01-05: Client profile service

**Verification**: Can create client, queue task, execute stub agent

### Phase 2: Document Processing (3 weeks)
**Goal**: Vision-based document extraction with confidence scoring

**Plans**:
- 02-01: Google Drive integration
- 02-02: Document classifier (W-2, 1099, K-1 detection)
- 02-03: Vision extraction pipeline
- 02-04: Confidence scoring engine

**Verification**: Upload sample W-2, get structured JSON with confidence

### Phase 3: Personal Tax Agent (4 weeks)
**Goal**: Functional 1040 preparation agent

**Plans**:
- 03-01: 1040 skill file + checklist
- 03-02: Income aggregation logic
- 03-03: Deduction calculator
- 03-04: Tax computation engine
- 03-05: Drake worksheet generator
- 03-06: Preparer notes generator
- 03-07: Prior year comparison

**Verification**: Prepare simple W-2 return, produce correct worksheet

### Phase 4: TaxDome Integration (2 weeks)
**Goal**: Full workflow integration with TaxDome

**Plans**:
- 04-01: TaxDome webhook receiver
- 04-02: Status update sender
- 04-03: Task assignment flow

**Verification**: Assign task in TaxDome → Rookie processes → Status updates

### Phase 5: Feedback System (2 weeks)
**Goal**: Capture and store CPA corrections

**Plans**:
- 05-01: Implicit diff capture
- 05-02: Explicit tag interface
- 05-03: Feedback storage + analysis

**Verification**: Make correction, see feedback stored

### Phase 6: Monitoring Dashboard (2 weeks)
**Goal**: Real-time visibility into agent operations

**Plans**:
- 06-01: Status API endpoints
- 06-02: Dashboard UI (basic)
- 06-03: Flag notification system

**Verification**: View active tasks, progress, flags in browser

### Phase 7: Business Tax Agent (4 weeks)
**Goal**: 1120/1120-S/1065 preparation capability

**Plans**:
- 07-01: Business tax skill files
- 07-02: K-1 generation logic
- 07-03: Basis tracking
- 07-04: Business worksheet generator

**Verification**: Prepare simple business return, generate K-1s

### Phase 8: Bookkeeping Agent (3 weeks)
**Goal**: QuickBooks transaction categorization and reconciliation

**Plans**:
- 08-01: QBO API integration
- 08-02: Transaction categorizer
- 08-03: Reconciliation engine
- 08-04: Month-end processor

**Verification**: Categorize month of transactions, reconcile bank

### Phase 9: Checker Agent (2 weeks)
**Goal**: Automated verification before human review

**Plans**:
- 09-01: Source document validator
- 09-02: Variance analyzer
- 09-03: Completeness checker

**Verification**: Run checker on prepared return, get flag report

---

## Part 12: Appendices

### Appendix A: Client Profile Schema (Complete Reference)

```yaml
# Full CLIENT_SCHEMA.md content
# See Section 4.1 for complete schema

client_profile:
  version: "1.0"

  identification:
    client_id: string        # Firm's internal ID
    external_ids:
      taxdome_id: string
      qbo_id: string
    full_name: string
    legal_name: string       # If different from full_name
    ssn_last4: string        # Last 4 digits only
    dob: date
    filing_status: enum
      - single
      - married_filing_jointly
      - married_filing_separately
      - head_of_household
      - qualifying_widow(er)

  contact:
    primary_phone: string
    secondary_phone: string
    email: string
    preferred_contact_method: enum [phone, email, text, portal]
    best_contact_time: string
    timezone: string

  address:
    type: enum [primary, mailing]
    street_line_1: string
    street_line_2: string
    city: string
    state: string            # 2-letter code
    zip: string
    county: string           # For local taxes
    school_district: string  # For state returns
    moved_during_year: boolean
    prior_address:           # If moved
      street: string
      city: string
      state: string
      zip: string
      moved_date: date

  household:
    spouse:
      name: string
      ssn_last4: string
      dob: date
      occupation: string
      employer: string
      has_own_income: boolean
      files_separately: boolean
    dependents:
      - name: string
        ssn_last4: string
        dob: date
        relationship: enum [child, parent, sibling, other]
        months_lived_with: integer  # 0-12
        is_student: boolean
        is_disabled: boolean
        gross_income: decimal       # If any
        provides_own_support_pct: decimal  # 0-100

  income_sources:
    # Append-only, year-tagged
    - source_id: uuid
      type: enum
        - w2_wages
        - 1099_nec           # Independent contractor
        - 1099_misc          # Other income
        - 1099_int           # Interest
        - 1099_div           # Dividends
        - 1099_b             # Brokerage
        - 1099_r             # Retirement distribution
        - 1099_ssa           # Social Security
        - k1_partnership
        - k1_scorp
        - k1_estate_trust
        - rental_income
        - business_income    # Schedule C
        - capital_gains
        - other
      payer_name: string
      payer_ein: string
      approximate_annual_amount: decimal
      frequency: enum [annual, monthly, quarterly, irregular]
      first_year: integer
      last_year: integer     # null if ongoing
      notes: string
      document_pattern: string  # "Fidelity 1099-DIV"

  deductions_credits:
    itemizes_typically: boolean
    standard_or_itemized_history:
      - year: integer
        type: enum [standard, itemized]
        total: decimal

    common_itemized:
      - category: enum
          - mortgage_interest
          - property_taxes
          - state_income_taxes
          - charitable_cash
          - charitable_noncash
          - medical_expenses
          - investment_interest
          - casualty_loss
          - unreimbursed_employee
          - other
        typical_annual_amount: decimal
        documentation_location: string
        notes: string

    credits_typically_claimed:
      - credit_type: enum
          - child_tax_credit
          - child_care_credit
          - education_credit
          - retirement_savings_credit
          - energy_credit
          - foreign_tax_credit
          - other
        typical_amount: decimal
        qualifying_details: string

  tax_planning:
    estimated_payments:
      makes_estimated_payments: boolean
      federal_quarterly_amount: decimal
      state_quarterly_amount: decimal
      payment_method: string

    withholding_strategy:
      target: enum [slight_refund, break_even, slight_owed]
      notes: string

    retirement_contributions:
      - account_type: enum [401k, ira_traditional, ira_roth, sep, simple]
        annual_contribution: decimal
        employer_match: decimal
        notes: string

    planning_opportunities_identified:
      - opportunity: string
        potential_savings: decimal
        discussed_with_client: boolean
        client_response: string
        date_identified: date

  return_history:
    # Last 3 years detailed, older summarized
    - year: integer
      filing_status: string
      agi: decimal
      taxable_income: decimal
      total_tax: decimal
      total_payments: decimal
      refund_or_owed: decimal
      effective_tax_rate: decimal
      notable_items:
        - description: string
          amount: decimal
          form_line: string
      extension_filed: boolean
      audit_flag: boolean
      amended: boolean

  preferences:
    communication_style: enum
      - brief_and_direct
      - detailed_explanations
      - visual_learner
      - needs_reminders
    deadline_sensitivity: enum
      - early_filer           # Before March 1
      - standard              # March-April 15
      - extension_typical     # Usually files extension
    document_organization: enum
      - highly_organized
      - mostly_organized
      - needs_help
      - scattered
    portal_usage: enum
      - tech_savvy
      - needs_guidance
      - prefers_paper
    meeting_preference: enum
      - in_person
      - video_call
      - phone
      - email_only

  red_flags:
    # Items requiring special attention
    - flag_id: uuid
      category: enum
        - audit_history
        - complex_situation
        - frequent_amendments
        - late_documents
        - communication_issue
        - payment_issue
        - compliance_risk
        - other
      description: string
      identified_date: date
      identified_by: string
      severity: enum [low, medium, high]
      resolution: string
      resolved_date: date

  opportunities:
    # Proactive planning items
    - opportunity_id: uuid
      category: enum
        - retirement_optimization
        - income_timing
        - entity_structure
        - deduction_bunching
        - tax_loss_harvesting
        - estate_planning
        - charitable_giving
        - education_planning
        - other
      description: string
      potential_annual_savings: decimal
      complexity: enum [simple, moderate, complex]
      discussed_with_client: boolean
      client_interested: boolean
      implementation_status: enum
        - not_discussed
        - discussed_declined
        - discussed_considering
        - in_progress
        - implemented
      notes: string

  # Metadata
  profile_metadata:
    created_at: timestamp
    created_by: string
    last_updated: timestamp
    last_updated_by: string
    profile_version: string
    retention_years: integer     # How long to keep detailed data
```

### Appendix B: Error Handling Matrix

| Error Type | Detection | Handling | Escalation |
|------------|-----------|----------|------------|
| **API Timeout** | Request timeout | Retry 3x with backoff | Log, continue with cached data if available |
| **API Auth Failure** | 401/403 response | Refresh token, retry | Notify admin, pause agent |
| **Document Parse Failure** | Vision extraction returns null | Log, flag document | Include in preparer notes |
| **Low Confidence Extraction** | Confidence < 70% | Flag for review | Add to flags section |
| **Missing Expected Document** | Pattern matching fails | Log missing doc | Include in preparer notes |
| **Calculation Mismatch** | Cross-check fails | Log variance | Flag for reviewer |
| **Database Error** | Connection/query failure | Retry, then fail task | Restart task from beginning |
| **Agent Crash** | Process dies | Task marked failed | Restart fresh (no partial state) |
| **Human Redirect** | Interrupt received | Confirm cancel | Wait for new instructions |

### Appendix C: LLM Provider Configuration

```python
# Multi-provider LLM configuration
LLM_CONFIG = {
    "providers": {
        "anthropic": {
            "models": {
                "claude-3-5-sonnet": {
                    "use_for": ["document_extraction", "tax_analysis"],
                    "context_window": 200000,
                    "cost_per_1k_input": 0.003,
                    "cost_per_1k_output": 0.015
                },
                "claude-3-5-haiku": {
                    "use_for": ["classification", "simple_extraction"],
                    "context_window": 200000,
                    "cost_per_1k_input": 0.0008,
                    "cost_per_1k_output": 0.004
                }
            }
        },
        "openai": {
            "models": {
                "gpt-4o": {
                    "use_for": ["vision_extraction", "complex_reasoning"],
                    "context_window": 128000,
                    "cost_per_1k_input": 0.005,
                    "cost_per_1k_output": 0.015
                }
            }
        },
        "google": {
            "models": {
                "gemini-1.5-pro": {
                    "use_for": ["document_processing", "long_context"],
                    "context_window": 1000000,
                    "cost_per_1k_input": 0.00125,
                    "cost_per_1k_output": 0.005
                }
            }
        }
    },

    "routing": {
        "document_classification": "claude-3-5-haiku",
        "w2_extraction": "gpt-4o",           # Best vision
        "1099_extraction": "gpt-4o",
        "k1_extraction": "claude-3-5-sonnet", # Complex reasoning
        "tax_calculation": "claude-3-5-sonnet",
        "preparer_notes": "claude-3-5-sonnet",
        "prior_year_comparison": "gemini-1.5-pro"  # Long context
    }
}
```

### Appendix D: Skill File Template

```markdown
# Skill: 1040 Individual Tax Preparation

**Version**: 2026.1
**Effective Date**: 2026-01-01
**Agent**: personal_tax

## Overview

This skill guides preparation of Form 1040 Individual Income Tax Returns.

## Prerequisites

- Client profile loaded
- Current year documents scanned
- Prior year return available (PDF)

## Checklist

### Step 1: Document Inventory
- [ ] Verify all expected income documents received
- [ ] Cross-reference to prior year sources
- [ ] Flag missing documents

### Step 2: Income Extraction
- [ ] Extract W-2 data (all employers)
- [ ] Extract 1099-INT/DIV data
- [ ] Extract 1099-NEC/MISC data
- [ ] Extract K-1 data (if applicable)
- [ ] Calculate total income

### Step 3: Deduction Analysis
- [ ] Compare standard vs itemized
- [ ] If itemizing: calculate Schedule A
- [ ] Apply above-the-line deductions (HSA, student loan, etc.)

### Step 4: Credit Evaluation
- [ ] Child Tax Credit eligibility
- [ ] Child Care Credit eligibility
- [ ] Education Credits eligibility
- [ ] Other applicable credits

### Step 5: Tax Computation
- [ ] Apply tax brackets
- [ ] Calculate AMT if applicable
- [ ] Net Investment Income Tax check
- [ ] Self-employment tax if applicable

### Step 6: Payments & Refund
- [ ] Sum withholdings (W-2 Box 2)
- [ ] Add estimated payments
- [ ] Calculate refund or balance due

### Step 7: Prior Year Comparison
- [ ] Compare AGI (flag >10% variance)
- [ ] Compare total tax (flag >10% variance)
- [ ] Compare refund/owed (flag sign change)
- [ ] Document reasons for significant changes

### Step 8: Output Generation
- [ ] Generate Drake worksheet
- [ ] Generate preparer notes
- [ ] Compile flags and questions

## Output Specifications

### Drake Worksheet
- Excel format
- One sheet per major form/schedule
- Each row: Field name, Value, Source document, Confidence

### Preparer Notes
- Summary section (key metrics + YoY)
- Sources section (documents used)
- Flags section (items for attention)
- Assumptions section (with reasoning)
- Review focus section (priority areas)

## Tax Law Notes (2026)

- Standard deduction: $14,600 (single), $29,200 (MFJ)
- Child Tax Credit: $2,000 per qualifying child
- [Additional 2026-specific items]

## Common Flags

- Large variance from prior year without documentation
- Missing expected income source
- Deduction significantly different from typical
- Filing status change
- New dependent or dependent aged out
```

### Appendix E: API Endpoint Reference

```yaml
# Rookie API v1.0

openapi: 3.0.0
info:
  title: Rookie API
  version: 1.0.0

paths:
  # Client Management
  /api/clients:
    get:
      summary: List clients
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
        - name: offset
          in: query
          schema:
            type: integer
    post:
      summary: Create client
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ClientCreate'

  /api/clients/{client_id}:
    get:
      summary: Get client details
    patch:
      summary: Update client

  /api/clients/{client_id}/profile:
    get:
      summary: Get computed client profile (3-year window)
    post:
      summary: Add profile entry (append-only)

  # Task Management
  /api/tasks:
    get:
      summary: List tasks
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [pending, in_progress, completed, failed]
        - name: agent_type
          in: query
          schema:
            type: string
    post:
      summary: Create task

  /api/tasks/{task_id}:
    get:
      summary: Get task details

  /api/tasks/{task_id}/artifacts:
    get:
      summary: List task artifacts

  /api/tasks/{task_id}/artifacts/{artifact_id}:
    get:
      summary: Download artifact

  # Status & Monitoring
  /api/status/tasks:
    get:
      summary: Real-time task status

  /api/status/agents:
    get:
      summary: Agent status overview

  /api/status/queue:
    get:
      summary: Queue depth and health

  # Webhooks
  /webhooks/taxdome/task-assigned:
    post:
      summary: TaxDome task assignment webhook

  /webhooks/taxdome/status-changed:
    post:
      summary: TaxDome status change webhook

  # Feedback
  /api/feedback:
    get:
      summary: List feedback entries
    post:
      summary: Submit explicit feedback

components:
  schemas:
    ClientCreate:
      type: object
      required:
        - external_id
        - full_name
      properties:
        external_id:
          type: string
        full_name:
          type: string
        # ... additional fields

    TaskCreate:
      type: object
      required:
        - client_id
        - task_type
      properties:
        client_id:
          type: string
          format: uuid
        task_type:
          type: string
          enum: [1040_prep, 1120_prep, bookkeeping]
        tax_year:
          type: integer
        priority:
          type: string
          enum: [low, normal, high]
```

---

## Part 13: Success Metrics

### 13.1 Trust Graduation Milestones

| Milestone | Metric | Target |
|-----------|--------|--------|
| **Initial Testing** | Returns prepared in parallel (AI + human) | 10 returns |
| **Supervised Prep** | Returns with full review | 50 returns |
| **Spot-Check Mode** | Returns with spot-check only | 200 returns |
| **Flag-Based Review** | Review only flagged items | 500+ returns |

### 13.2 Quality Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Extraction Accuracy** | % of fields correctly extracted | >95% |
| **Calculation Accuracy** | % of tax calculations correct | >99% |
| **Flag Precision** | % of flags that required attention | >80% |
| **Flag Recall** | % of issues caught by flags | >95% |
| **Revision Rate** | % of returns requiring correction | <10% |

### 13.3 Efficiency Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Prep Time** | Time from start to worksheet complete | <30 min avg |
| **Review Time Saved** | Reduction in CPA review time | >50% |
| **Throughput** | Returns processed per day | Scale with demand |

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Claude | Initial comprehensive specification |

---

*This specification is self-contained. Any competent agent (Claude Code, Codex, or human) can pick it up and execute without external context.*
