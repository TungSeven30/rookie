# Rookie

**Your AI junior accountant. Eager, thorough, and always ready for feedback.**

Rookie is an AI employee platform for CPA firms. Not a chatbot. Not an assistant. An actual employee that prepares tax returns, categorizes transactions, and produces work products indistinguishable from junior staff output.

Think of it like hiring a new associate — except this one doesn't need health insurance, works weekends without complaining, and genuinely enjoys reconciling bank statements.

---

## Philosophy

**Treat AI like a new employee.**

Rookie starts with simple tasks and earns trust through accuracy. First 10 returns? Reviewed line by line. Next 50? Spot-checked. Eventually? Only exceptions need attention.

The system is designed around a simple truth: CPAs are liable for the work, not the AI. Rookie prepares. Humans approve. That's non-negotiable.

---

## What Rookie Actually Does

| Agent | Capabilities |
|-------|--------------|
| **Personal Tax** | 1040 preparation, Schedule C/E, QBI deductions, ACA reconciliation |
| **Business Tax** | 1120/1120-S/1065, K-1 generation, basis tracking |
| **Bookkeeping** | Transaction categorization, bank reconciliation, month-end close |
| **Checker** | Cross-references source docs, flags variances, validates calculations |

Each agent has focused skill files — markdown docs with step-by-step instructions, firm-specific rules, and escalation triggers. Like an employee handbook, but one that's actually read.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Rookie Core                        │
├─────────────┬─────────────┬─────────────┬──────────────┤
│ Personal Tax│ Business Tax│ Bookkeeping │   Checker    │
│    Agent    │    Agent    │    Agent    │    Agent     │
├─────────────┴─────────────┴─────────────┴──────────────┤
│                   Orchestration Layer                   │
│         (Task Queue • State Machine • Dispatcher)       │
├─────────────────────────────────────────────────────────┤
│                    Integration Layer                    │
│            (Drake • QuickBooks • TaxDome)               │
├─────────────────────────────────────────────────────────┤
│                      Data Layer                         │
│      (PostgreSQL • Redis • Client Profiles • Skills)    │
└─────────────────────────────────────────────────────────┘
```

**Tech Stack:**
- Python 3.11+ / FastAPI
- PostgreSQL + pgvector
- Redis (caching, real-time status)
- Claude, GPT, Gemini (multi-provider, no vendor lock-in)

---

## How It Works

**1. Task Assignment**  
CPA assigns work through TaxDome (or directly). Rookie picks it up like any employee would.

**2. Context Assembly**  
Agent loads client profile, relevant skill files, source documents, and prior year data.

**3. Execution**  
Agent follows skill file instructions, extracts data via vision API, applies tax logic, produces artifacts.

**4. Output**  
Drake-ready worksheet + preparer notes. Everything a reviewer needs to verify the work.

**5. Feedback Loop**  
Corrections are captured (implicit diff + optional explicit tags) and inform future improvements.

---

## Demo Quickstart (Production-Ready)

This demo is built for real use with simple personal tax prep (W-2, 1099-INT/DIV/NEC).
It uses API-key auth, durable job storage, and file storage via local disk or S3.

### Prerequisites
- Python 3.11+
- `uv` installed
- PostgreSQL running
- Redis running
- Node.js 18+ (for the demo UI)

### 1) Configure environment

Create a `.env` file from `.env.example` and set the required values:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rookie
REDIS_URL=redis://localhost:6379/0
DEMO_API_KEY=your-demo-key
DEFAULT_STORAGE_URL=/tmp/rookie-demo
OUTPUT_DIR=/tmp/rookie-output
MAX_UPLOAD_BYTES=52428800
ALLOWED_UPLOAD_TYPES=application/pdf,image/jpeg,image/png,image/jpg
DEMO_RETENTION_DAYS=7
```

If you want S3 storage:
```
DEFAULT_STORAGE_URL=s3://your-bucket/rookie-demo
```
Make sure AWS credentials are available in the environment.

### 2) Install backend dependencies
```
uv sync
```

### 3) Initialize the database
Run migrations (if this is your first run):
```
uv run alembic upgrade head
```

### 4) Start the API
```
uv run uvicorn src.main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

### 5) Start the demo UI
```
cd frontend
npm install
VITE_DEMO_API_KEY=your-demo-key npm run dev
```

Open `http://localhost:5173` in a browser.

### 6) Use the demo
1. Upload W-2 and 1099 files (PDF/JPG/PNG).
2. Start processing.
3. Watch progress in the UI.
4. Download outputs:
   - Drake worksheet (Excel)
   - Preparer notes (Markdown)

### Optional: API usage (curl)

Upload:
```
curl -X POST "http://127.0.0.1:8000/api/demo/upload" \
  -H "X-Demo-Api-Key: your-demo-key" \
  -F "files=@/path/to/w2.pdf" \
  -F "files=@/path/to/1099int.jpg" \
  -F "client_name=Demo Client" \
  -F "tax_year=2024" \
  -F "filing_status=single"
```

Start processing:
```
curl -X POST "http://127.0.0.1:8000/api/demo/process/<job_id>" \
  -H "X-Demo-Api-Key: your-demo-key"
```

Check status:
```
curl -X GET "http://127.0.0.1:8000/api/demo/status/<job_id>" \
  -H "X-Demo-Api-Key: your-demo-key"
```

Get results:
```
curl -X GET "http://127.0.0.1:8000/api/demo/results/<job_id>" \
  -H "X-Demo-Api-Key: your-demo-key"
```

Download files:
```
curl -X GET "http://127.0.0.1:8000/api/demo/download/<job_id>/worksheet" \
  -H "X-Demo-Api-Key: your-demo-key" -o drake_worksheet.xlsx

curl -X GET "http://127.0.0.1:8000/api/demo/download/<job_id>/notes" \
  -H "X-Demo-Api-Key: your-demo-key" -o preparer_notes.md
```

---

## Client Profile System

Each client has a living profile stored as an append-only log in the database,
with a derived current-state view. Detailed entries are retained for the last
3 years; older years are summarized.

Client documents follow a standard folder structure:

```
clients/1011_Nguyen_Ethan/
└── 2025/
    ├── source_docs/     # W-2s, 1099s, K-1s
    ├── workpapers/      # Rookie's artifacts
    └── final/           # Reviewed & approved
```

Profiles follow a defined schema: income sources, deduction patterns, filing
history, red flags, planning opportunities. The AI knows the client before
starting work — just like a returning staff member would.

---

## Skill Files

Skill files are the institutional knowledge layer. Versioned YAML with
effective dates and explicit escalation rules:

```yaml
metadata:
  name: "Schedule E Preparation"
  version: "2025.1"
  effective_date: "2025-01-01"
  agent: "personal_tax"
  applicable_forms: ["Schedule E", "Form 8582"]

checklist:
  - id: "rental_income_inventory"
    description: "Verify all rental income documents received"
    required: true
  - id: "expense_validation"
    description: "Validate expenses and allocation"
    required: true

decision_rules:
  - condition: "personal_use_days > 14"
    action: "flag_for_review"
    reason: "Mixed-use property requires reviewer attention"

escalation_triggers:
  - "missing_required_document"
  - "conflicting_information"
```

Tax law changes? Update the skill file with a new effective date. The agent knows which rules apply to which tax year.

---

## Output Artifacts

**Drake Worksheet** (Excel)
| Screen | Field | Value | Source | Confidence | Notes |
|--------|-------|-------|--------|------------|-------|
| W2 | Wages (Box 1) | 122,698.00 | Kim_W2_AllHealth.pdf | HIGH | Matches profile |
| Sch C | Gross Receipts | 28,450.00 | Bank statements + 1099-NEC | HIGH | Cash basis |

**Preparer Notes** (Markdown)
- Summary with AGI, tax, refund estimates
- Data sources with confidence levels
- Flags for reviewer attention
- Assumptions made and reasoning
- Prior year comparison highlights

---

## Integrations

| System | Method | Status |
|--------|--------|--------|
| **Drake Tax** | Worksheet → manual entry (v1), evaluate XML import later | In use (demo workflow) |
| **QuickBooks Online** | REST API for transaction read/write | Planned |
| **TaxDome** | API for task management, status updates | In progress (webhook + status API scaffold) |

---

## Roadmap

- [x] Architecture design
- [x] Client profile schema
- [x] Skill file structure
- [ ] **Phase 0**: Golden Path MVP (single known-good 1040)
- [x] **Phase 1**: Foundation + observability
  - [x] FastAPI with health endpoint
  - [x] PostgreSQL + Redis connections
  - [x] Structured JSON logging with correlation IDs
  - [x] Request context middleware
  - [x] Unit tests with mocked dependencies
- [x] **Phase 2**: Core framework
  - [x] Task Dispatcher with agent routing
  - [x] State Machine (pending → assigned → in_progress → completed/failed/escalated)
  - [x] Circuit Breaker (5-fail threshold, 30s recovery)
  - [x] Skill Engine (YAML parsing, version selection)
  - [x] Client Profile Manager (append-only log)
  - [x] Context Builder for agent execution
  - [x] Hybrid Search (pgvector + BM25 with RRF fusion)
- [x] **Phase 3**: Personal Tax Agent (simple returns)
- [x] **Phase 4**: Personal Tax Agent (complex returns)
- [ ] **Phase 5**: Review infrastructure (in progress)
  - [x] Checker Agent core logic + review API endpoints
  - [x] Feedback capture APIs (implicit diff + explicit tags)
  - [x] Status/dashboard APIs (task progress, agent activity, queue + flags)
  - [x] TaxDome integration API scaffold (assignment webhook + status sync)
  - [ ] Frontend dashboard and WCAG 2.1 AA validation
  - [ ] End-to-end TaxDome integration validation in non-mock environment
- [ ] **Phase 6**: Business Tax Agent
- [ ] **Phase 7**: Bookkeeping Agent
- [ ] **Phase 8**: Production hardening

---

## Why "Rookie"?

Because that's exactly what it is. An eager new hire that:

- Starts with simple tasks
- Expects feedback on every piece of work
- Learns from corrections
- Gradually earns more responsibility
- Never pretends to know more than it does

The name is a feature, not a bug. It sets the right expectations.

---

## License

MIT

---

## Contributing

Not open for external contributions yet. This is an internal tool for a specific CPA firm. Open-sourcing the architecture docs for transparency and potential future collaboration.

---

*Built with unhealthy amounts of caffeine and Claude.*
