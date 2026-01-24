# Rookie Discovery Interview

**Date**: January 23, 2026  
**Participants**: Project Lead, Claude (Interviewer)

---

## Executive Summary

This document captures the requirements gathering conversation for Rookie, an AI employee platform for CPA firms. The interview covered architecture decisions, integration requirements, workflow design, and implementation priorities across nine rounds of discussion.

---

## Round 1: Core Architecture & Trust Model

### Multi-Tenancy
**Q**: How isolated should firm-specific data be? What prevents cross-contamination of training data between firms?

**A**: Single-firm deployment initially. Multi-tenancy is not a v1 concern.

### Confidence Scoring
**Q**: How should the AI express uncertainty on journal entries and tax treatments?

**A**: Start with LLM-generated confidence levels, then develop firm-wide classification standards over time. The system will evolve as the AI becomes more integrated with firm operations.

### State Persistence
**Q**: How does the AI maintain context across different stages of a task?

**A**: This requires further research. The solution likely involves markdown files or a skill-based structure. Context should be task-oriented — the AI doesn't need to remember small talk, but must retain references to specific clients, treatments applied, and reasoning behind decisions.

### Trainability
**Q**: How does the AI learn from CPA feedback?

**A**: Manual feedback incorporated on a scheduled basis. The specific mechanism (RLHF, RAG, prompt engineering) remains to be determined.

### Failure Philosophy
**Q**: What happens when the AI makes mistakes?

**A**: Partial output with flags, then learn from corrections. The AI should be treated exactly like a new employee — mistakes are expected, feedback is provided, performance improves over time.

---

## Round 2: Firm Environment & Workflow

### Current Tech Stack
- **Tax Preparation**: Drake (desktop software)
- **Bookkeeping**: QuickBooks Online
- **Workflow Management**: TaxDome

### Document Ingestion
**Q**: How do client documents arrive?

**A**: Documents land in local folders synced to cloud storage (Google Drive or Dropbox), organized by client.

### Onboarding Model
**Q**: What resources does the AI need before working on a client?

**A**: For each client, maintain a living document that grows over years. This profile contains key information updated annually: tax details, preferences, issues encountered, resolutions applied. The AI reviews this document before starting work and updates it upon completion. Think of it as a continuously maintained client brief.

### Handoff Artifacts
**Q**: What does the AI produce when it finishes preparation?

**A**: The same artifacts a human associate would produce — work products that follow the firm's existing handoff conventions.

### Compliance Trail
**Q**: Who bears liability for AI-prepared work?

**A**: The CPA, not the AI. This mirrors the liability model for work prepared by junior employees. The CPA reviews and signs off; responsibility remains with the licensed professional.

### Client Segmentation
**Q**: Should the AI have tiered access to clients based on complexity?

**A**: Not important for v1.

---

## Round 3: Integration & Handoff Mechanics

### Drake Integration Strategy
**Q**: How should data flow into Drake Tax?

**A**: Preferred approach is Drake's import templates (CSV/Excel) or potentially RPA automation. The firm has full control over processes, so any approach is viable. The goal is finding the most reliable path, not necessarily the fastest.

### QuickBooks Version
**A**: QuickBooks Online (has API access).

### TaxDome Role
**Q**: How does the AI fit into TaxDome?

**A**: The AI operates as a virtual employee within TaxDome, assigned to tasks just like a junior staff member.

### Client Document Versioning
**Q**: How do you handle conflicts when both AI and humans update client notes?

**A**: Append-only log structure recommended. Each entry includes timestamp, author (human or AI), entry type, and content. No overwrites means no conflicts. Current state is derived by reading the log forward.

### Current Handoff Process
**Q**: What literally happens when an associate finishes work today?

**A**: TaxDome status change. The project moves to the next person in the workflow.

### Feedback Capture
**Q**: How do CPA corrections become training data?

**A**: Two-layer approach:
1. **Implicit**: Diff the AI's draft against the final submitted version to capture what changed
2. **Explicit**: Optional lightweight review tags when the CPA wants to explain why something was corrected (e.g., "misclassified", "missing context", "judgment call")

The explicit layer must be optional — requiring annotation for every edit guarantees it won't be used.

---

## Round 4: Context, Memory, and Task Decomposition

### Context Window Management
**Q**: Client profiles will grow over years. How do you prevent context overflow?

**A**: Retention policy limits profiles to the last 3 years of detailed information. Older data is archived. The profile itself is a summary template with key information, not an exhaustive record. Static information (name, DOB, address) doesn't change yearly; annual updates add minimal content.

### Task Granularity
**Q**: How detailed should task decomposition be?

**A**: The firm already has clear processes with checklists for each step: gather information, follow up with clients, prepare, check, review. These existing processes provide the decomposition structure.

### Skill Architecture
**Q**: How should domain expertise be organized?

**A**: Multiple specialized agents. One agent for personal tax, one for business tax, one for bookkeeping. Each agent has focused skills within its domain.

### Scalability Model
**Q**: How does the system handle tax season volume spikes?

**A**: Horizontal scaling — spin up more agent instances as needed, similar to how Claude Code handles concurrent tasks.

---

## Round 5: Multi-Agent Orchestration

### Task Routing
**Q**: Who decides which agent handles a task?

**A**: The CPA (or senior employee) assigns tasks explicitly. Agents are assigned to jobs before beginning work, just like human staff assignments in TaxDome.

### Error Recovery
**Q**: What happens if an agent crashes mid-task?

**A**: Start over from the beginning. If the agent fails mid-execution, the task restarts fresh. No partial state recovery — simpler and more reliable.

### Human Interrupts
**Q**: How does a CPA redirect an AI mid-task?

**A**: The CPA confirms whether to cancel the current task. The AI doesn't continue speculatively after receiving conflicting instructions.

### Agent-to-Agent Communication
**Q**: How do agents hand off to each other?

**A**: Email summary or structured notes documenting what was completed and where artifacts are located. Initially, humans explicitly direct transitions between agents.

### Monitoring Approach
**Q**: How do humans observe AI work in progress?

**A**: A custom status webpage providing more granular detail than TaxDome's native views. The interface should let a CPA see exactly where an AI is in a project — like asking an employee "where are you at with that return?"

### Cost Sensitivity
**Q**: How important is LLM cost optimization?

**A**: Invest now, optimize later. For context: a staff accountant's salary is the benchmark. AI operational costs are acceptable if they deliver staff-equivalent output.

### Validation Strategy
**Q**: How do you verify the AI isn't making mistakes before production?

**A**: Start with simple returns. Have AI and human prepare the same return in parallel, then compare outputs. The CPA will proceed slowly, checking AI work more carefully than they would check a new employee's work. 

Training methodology mirrors human onboarding: new employees prepare returns based on prior year workpapers and compare their output to the final filed product. The AI uses the same approach.

---

## Round 6: Workspace & Artifact Structure

### Meeting Notes Integration
**Q**: How do CPA meeting notes feed into client profiles?

**A**: The CPA already records client meetings and has AI summarize them into meeting notes. The CPA can then direct the AI to extract profile-relevant information from those notes — updating specific fields rather than dumping raw meeting content.

### Task Execution Sequence
**Q**: Walk through what happens when an agent starts a 1040 preparation.

**A**: 
1. Load client profile
2. Load relevant skill file (Personal Tax 1040)
3. Scan client folder for current year documents
4. Extract data from source documents using vision
5. Execute preparation checklist
6. Produce artifacts (Drake worksheet, preparer notes)
7. Compare to prior year return and flag significant changes

### Prior Year Reference Format
**Q**: What format is the prior year return available in?

**A**: Final PDF is the source of truth.

### Checker Role
**Q**: Could AI eventually perform the checker function?

**A**: Start with AI as preparer only. However, AI may excel at checking — verifying numbers match source documents, flagging unexpected changes, ensuring inputs are correct. The checker role involves comparing the final result against expected outcomes based on prior years and client profile. Human reviewer remains the final gate regardless.

### Escalation Protocol
**Q**: What happens when the AI encounters something it can't resolve?

**A**: Escalate to human, then wait for instructions. If other tasks are available, move on to those while waiting. The AI doesn't guess on ambiguous situations.

### Client Communication
**Q**: Can the AI contact clients directly?

**A**: Not initially. All client communication routes through human reviewers first. The AI can draft emails for human approval and sending.

### Profile Schema
**A**: Provided CLIENT_SCHEMA.md with comprehensive structure including: identification, contact info, household, income sources, deductions/credits, tax planning history, historical return summary, client preferences, red flags, and planning opportunities.

---

## Round 7: Skill Files & Work Products

### Meeting Note → Profile Sync
**Q**: How does meeting note content become profile updates?

**A**: CPA directs the summarizing AI to identify profile-relevant information. The AI extracts specific updates matching the profile schema rather than appending raw meeting content.

### Prior Year Comparison Timing
**Q**: When does prior year comparison happen in the workflow?

**A**: After preparation, as a verification step. The comparison flags whether changes are significant and whether there's a documented reason for them.

### Checker Mechanics
**Q**: What does "checking" actually involve?

**A**: Verify numbers against source documents. Ensure inputs are correct. Look at the final result — if there are significant changes from prior year without obvious explanation, investigate. For straightforward returns (income up slightly, no major life changes), the tax outcome should be predictable. Complex returns require more thorough checking.

### Drake Integration Research
**A**: Research confirmed Drake supports:
- GruntWorx integration (OCR → organized PDF → XML import for data population)
- Excel/CSV imports for Schedule D/8949 trades
- Manual data entry from structured worksheets

**Recommended approach**: AI produces a structured Drake worksheet (Excel format mapping to Drake screens). Human enters data using the worksheet as a guide. This is most controllable, easiest to verify, and doesn't require reverse-engineering GruntWorx's XML schema. Graduate to direct XML generation once accuracy is proven.

---

## Round 8: Implementation Details

### Checker Agent Authority
**Q**: Can the Checker agent approve work?

**A**: No. Human reviewer is always the final gate. Checker can approve or flag, but the determination doesn't matter because a human must still sign off.

### Skill File Versioning
**Q**: How do skill files handle tax law changes?

**A**: Version numbers and effective dates. Tax law doesn't change rapidly — annual updates are manageable and controlled.

### Multi-Year Handling
**Q**: How does the AI handle clients with multiple years in progress simultaneously?

**A**: AI can see across years. Client folder structure: `ClientID_Name/Year/documents`. Each year's work is distinct, but the AI has visibility into all years for context.

### Preparer Notes Structure
**A**: Confirmed structure:
- Summary (AGI, total tax, refund/owed, prior year comparison)
- Data sources used (documents with confidence levels)
- Flags/questions (items requiring reviewer attention)
- Assumptions made (and reasoning)
- Suggested review focus areas

Format varies by work type (business review vs. individual), but principles remain: human-readable, concise, organized. Goal is helping checker and reviewer get oriented quickly.

### Trust Graduation
**Q**: What milestones build trust in AI output?

**A**: AI is evolving rapidly. By the time formal graduation criteria matter, the landscape may look completely different. Focus on building correctly now; trust frameworks will emerge from operational experience.

---

## Round 9: Technical Implementation

### First Agent Priority
**Q**: Which agent to build first?

**A**: Personal Tax for initial testing, but build all agents in parallel. They share common infrastructure and can learn from each other's development.

### LLM Selection
**A**: No constraints. Use Claude, OpenAI (GPT), and Gemini as appropriate. API calls for now (not self-hosted).

### Tech Stack
**A**: Claude Code and Codex will assist with implementation. Preferred approach: build it right with future-proofing, no shortcuts.

**Recommended stack**:
- Python with FastAPI (best AI/ML ecosystem, mature agent frameworks)
- PostgreSQL for persistent state
- Redis for caching and real-time status
- Vector DB (pgvector or similar) for RAG over documents and skills

### Document Processing
**A**: LLM vision capabilities for document extraction. This work connects to GAAPT (the firm's existing AI platform), which already handles document classification and extraction.

### Interface Model
**A**: Standalone application or chat interface. The AI operates independently, not embedded within other tools.

### Monitoring UI
**A**: Plan for a granular status dashboard, but implementation timing is flexible. Start with TaxDome status tracking and add custom monitoring when needed.

### Timeline Priority
**A**: Optimize for correctness. Build it right. Speed is secondary to quality.

### Security/Compliance
**A**: Formalize later. Current requirement: don't leak client PII. SOC 2 and formal compliance frameworks come after core functionality is proven.

### TaxDome Integration
**A**: Either use TaxDome's API directly or assign the AI employee an email address for task notifications. Both approaches are viable.

### QuickBooks Integration
**A**: Direct API access if possible, with CSV batch processing as fallback. Support both modes.

### Project Independence
**A**: Treat Rookie as an independent project, not integrated with GAAPT initially. Cleaner development, easier testing, integration comes later.

### Spec Scope
**A**: Master plan covering all agents. Not just MVP — the full vision.

---

## Key Design Decisions Summary

| Decision | Rationale |
|----------|-----------|
| Single-firm first | Reduces complexity, proves value before multi-tenancy |
| Treat AI like new employee | Natural mental model for trust, training, and error tolerance |
| Append-only client logs | Eliminates merge conflicts, provides audit trail |
| Drake worksheet output | Most controllable, easiest to verify before automation |
| Multi-agent specialization | Clear responsibility boundaries, focused skill files |
| Human remains final gate | Maintains professional liability model, builds trust gradually |
| Build it right | Long-term maintainability over short-term speed |

---

## Open Items for Future Resolution

1. Specific RLHF/RAG mechanism for incorporating CPA feedback
2. Detailed GruntWorx XML schema (if pursuing direct Drake import)
3. Formal security and compliance requirements
4. Multi-firm architecture (when ready to scale)
5. Mobile/voice interface requirements

---

*Document generated from discovery session, January 23, 2026*

