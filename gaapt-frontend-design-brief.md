# GAAPT Frontend Design Brief

## Project Overview

**GAAPT** (GAAP + GPT) is an AI-powered "second brain" for CPA firms. It preserves institutional knowledge, accelerates staff onboarding, and proactively surfaces deadlines and opportunities.

**Target users:** CPAs and accounting staff at small-to-mid-size firms (5-50 people)

**Core value proposition:** "Your firm's knowledge shouldn't retire when your partners do."

---

## Current Interface State (v2.1)

The current implementation has four main screens. The foundation is solid but lacks depth and the "magical" feeling that would make CPAs love it.

### Current: Chat Page

**What exists:**
- Left sidebar with navigation (Chat, Dashboard, Clients, Review Queue)
- Starred and Recent conversation lists in sidebar
- Main area shows personalized greeting: "Good morning, Sarah"
- Subheading: "Here's what needs your attention today"
- "Needs Attention" card section with 3 alert items:
  - "3 documents need review" (Brown Medical, Johnson Corp extraction errors)
  - "Q4 estimated tax deadline in 5 days" (Johnson Manufacturing Corp - $456,750 due)
  - "1031 identification deadline Jan 15" (Garcia Real Estate Holdings - 45-day rule)
- "Continue Where You Left Off" section with 2 recent conversation cards
- Chat input at bottom: "Ask about clients, tax strategies, or firm knowledge..."
- Notification bell with badge (2) in sidebar
- User profile at bottom: "Sarah Chen, Senior CPA"

**What's good:**
- Proactive alerts with specific deadlines and dollar amounts
- Personalized greeting with context
- Recent conversations for continuity
- Clean, professional aesthetic

**What's missing:**
- Clicking alerts doesn't do anything yet
- No calendar integration for today's meetings
- Suggestion cards are static, not contextual to what's actually happening
- No keyboard shortcuts

### Current: Dashboard Page

**What exists:**
- Header: "Dashboard" with subtitle "Upload documents and monitor your knowledge base"
- Stats row with 6 cards:
  - 1,236 Total Documents
  - 1,198 Processed (green checkmark icon)
  - 38 Processing (blue sync icon)
  - 2 Needs Review (orange warning icon)
  - 1 Failed (red X icon)
  - +127 This Month (trend arrow)
- Upload Documents section with drag-drop zone
  - "Drag and drop files here, or click to browse"
  - "Select files" button
  - "Supports PDF, DOCX, XLSX, TXT up to 50MB"
- Processing Queue sidebar showing 4 items:
  - 2024_Form_1120S_... → "Extracting data" (with spinner)
  - Q4_Financials_J... → "Parsing document" (with progress bar)
  - Depreciation_Schedule_2... → "Queued"
  - Engagement_Letter_An... → "Complete" (green check)
  - "View all →" link
- Recent Activity section with timestamped items:
  - "Uploaded 3 documents for Brown Medical Group" (10 min ago)
  - "Processed Johnson Corp quarterly financials" (25 min ago)
  - "Extracted depreciation data from Smith LLC returns" (1 hour ago)
  - "Chat Answered question about Garcia 1031 exchange" (2 hours ago)
- Knowledge Base section showing document counts by category:
  - Tax Returns: 234 docs
  - Financial Statements: 156 docs
  - Engagement Letters: 89 docs
  - Correspondence: 312 docs

**What's good:**
- Clear processing status with actual stage names (not just "Processing")
- Needs Review and Failed counts are visible
- Real-time queue visibility
- Activity feed shows what's happening

**What's missing:**
- Clicking Needs Review/Failed stats should navigate to Review Queue
- No client association shown during upload
- No estimated time for processing
- Knowledge Base categories aren't clickable

### Current: Clients Page

**What exists:**
- Header: "Clients" with subtitle "Manage your client roster and access client information"
- "+ Add Client" button (top right, navy blue)
- Search bar: "Search clients by name, contact, or EIN..."
- Filter dropdown: "All Status"
- Client table with columns: CLIENT, STATUS, DOCUMENTS, LAST ACTIVITY
- Each row shows:
  - Document icon
  - Client name (bold)
  - Entity type badge below name (colored pills):
    - LLC (blue)
    - C-Corp (teal)
    - Trust (purple)
    - S-Corp (blue)
    - Partnership (orange)
  - Status badge (green "Active" or yellow "Prospect")
  - Document count with icon
  - Last activity timestamp
- Sample clients visible:
  - Smith & Associates LLC - Active - 47 docs - 2 hours ago
  - Johnson Manufacturing Corp (C-Corp) - Active - 89 docs - Yesterday
  - Williams Family Trust (Trust) - Active - 23 docs - 3 days ago
  - Brown Medical Group (S-Corp) - Active - 156 docs - 1 hour ago
  - Davis Construction Inc (C-Corp) - Active - 78 docs - Yesterday
  - Garcia Real Estate Holdings (LLC) - Active - 234 docs - 5 hours ago
  - Miller Tech Solutions (S-Corp) - Active - 45 docs - Last week
  - Wilson & Partners LLP (Partnership) - Active - 112 docs - 2 days ago
  - Anderson Consulting Group (LLC) - Prospect - 0 docs - New prospect

**What's good:**
- Entity type badges with color coding
- Prospect vs Active status differentiation
- Document counts give sense of client size
- Search and filter available

**What's missing:**
- No client detail page when you click a row
- Entity type colors are too similar (several shades of blue)
- No alerts/flags shown per client (e.g., "deadline in 5 days")
- No quick actions on hover
- Can't see key contacts or upcoming deadlines from list view

### Current: Review Queue Page

**What exists:**
- Header: "Review Queue" with subtitle "Verify AI-extracted data before it enters your knowledge base"
- Stats row with 4 cards:
  - 0 Pending Review (orange clock icon)
  - 0 In Review (blue eye icon)
  - 0 Approved Today (green check icon)
  - 0 Rejected Today (red X icon)
- Tab filters: All | Pending | In Review | Approved | Rejected
- Main content area shows loading spinner (empty state)

**What's good:**
- Clear workflow states
- Metrics visible at top
- Tab-based filtering

**What's missing:**
- No actual review UI exists yet
- No document cards with extracted data
- No side-by-side view of original vs extracted
- No field-level editing capability
- No keyboard shortcuts for approve/reject
- Empty state just shows spinner, no helpful message

### Current: Global Elements

**Sidebar navigation:**
- GAAPT logo (navy "A" mountain peak icon)
- "+ New chat" button (navy, full width)
- Chat (icon)
- Dashboard (icon)
- Clients (icon)
- Review Queue (icon) with red badge showing "3"
- Collapsible sections: STARRED, RECENT
- Notifications (bell icon with red "2" badge)
- Settings (gear icon)
- User profile: Avatar, "Sarah Chen", "Senior CPA"

**Visual style:**
- Primary color: Navy blue (#1e3a5f)
- Background: White/light gray
- Cards: White with subtle shadows
- Status colors: Green (success), Orange/Yellow (warning), Red (error), Blue (info)
- Font: Clean sans-serif
- Icons: Outlined style, consistent weight

---

## The User

### Primary Persona: Mid-Level CPA (3-10 years experience)

**A typical day:**
- 8:15am — Check what's urgent before the day starts
- 9:00am — Client call they almost forgot about, scrambling for context
- 10:30am — Junior staff interrupts with a question about S-corp elections
- 11:00am — Processing documents a client finally sent
- 2:00pm — "When is the Garcia 1031 deadline again?"
- 4:30pm — Partner asks "where are we on the Johnson estimated payments?"
- 6:00pm — Trying to remember what they were doing before the interruptions

**Emotional state:** Constantly context-switching. Mildly anxious about dropping balls. Protective of focus time. Skeptical of new tools but desperate for help.

**What they value:** Speed. Accuracy. Not looking stupid in front of clients. Going home on time.

### Secondary Persona: Junior Staff (0-3 years)

**Their challenge:** They don't know what they don't know. Every task requires asking someone.

**What they need:** Instant answers to "how do we do X?" and "what's the deal with this client?"

### Tertiary Persona: Partner (15+ years)

**Their challenge:** Time is their scarcest resource. They're interrupted constantly.

**What they need:** Confidence that the team has what they need without asking them.

---

## Design Principles

### 1. Time-to-information under 3 seconds

Every click that doesn't get them closer to an answer is a failure. Question → answer should feel instant.

### 2. Senior colleague, not database

Databases show data. A good colleague says "hey, you have that Garcia call in 20 minutes — want me to pull together what's changed?" The UI should embody proactive intelligence.

### 3. Context is everything

CPAs don't think in "documents" and "clients" as separate concepts. They think in situations: "the Henderson estate thing" or "that equipment purchase Smith is doing." Support this mental model.

### 4. Respect the anxiety

CPAs are professionally paranoid about deadlines and errors. The interface should soothe anxiety by making it clear what needs attention and what's under control.

### 5. Interruptibility is a feature

They will get pulled away mid-task constantly. Remember where they were. Surface recent context. Let them resume without cognitive load.

---

## Target State: 10/10 Interface

### Chat / Home Page — Target State

**Purpose:** Answer "what do I need to know right now?" and provide instant access to firm knowledge.

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  Good morning, Sarah                        Wed, Jan 15     │
│  Here's what needs your attention today.                    │
│                                                             │
│  ┌─ NEEDS ACTION ──────────────────────────────────────┐   │
│  │                                                     │   │
│  │  🔴 3 documents need review            [Review →]   │   │
│  │     Brown Medical W-2 · Johnson 1099               │   │
│  │                                                     │   │
│  │  🟡 Q4 estimated payment — 5 days       [Details →] │   │
│  │     Johnson Manufacturing · $456,750 due Jan 20    │   │
│  │                                                     │   │
│  │  🟡 1031 identification deadline        [Details →] │   │
│  │     Garcia Real Estate · 45-day rule expires Jan 20│   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ TODAY'S SCHEDULE ──────────────────────────────────┐   │
│  │                                                     │   │
│  │  10:30am  Williams Family Trust                     │   │
│  │           Quarterly review call                     │   │
│  │           [Prepare briefing →]                      │   │
│  │                                                     │   │
│  │  2:00pm   Anderson Consulting (New Client)          │   │
│  │           Intake meeting                            │   │
│  │           [View prospect info →]                    │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ CONTINUE WHERE YOU LEFT OFF ───────────────────────┐   │
│  │                                                     │   │
│  │  📄 Smith LLC depreciation analysis      yesterday  │   │
│  │  📄 Brown Medical retirement planning    yesterday  │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  💬 Ask about clients, deadlines, tax strategies... │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ SUGGESTED ─────────────────────────────────────────┐   │
│  │  "Prepare for Williams meeting"                     │   │
│  │  "What documents are missing for Brown Medical?"    │   │
│  │  "Summarize Garcia 1031 status"                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Key improvements from current:**
- Clicking any alert opens contextual chat pre-loaded with that topic
- "Prepare briefing" generates meeting prep in <5 seconds
- Today's Schedule section (calendar integration)
- Suggested prompts are dynamic based on actual current situations
- Empty state for "Needs Action": "All caught up — nothing urgent right now ✓"

**Interactions:**
- Alerts are sorted by urgency, not recency
- Hover on alert shows quick preview
- Keyboard: `1`, `2`, `3` to jump to alert items
- `⌘K` opens command palette from anywhere

---

### Client 360 Page — Target State (NEW)

**Purpose:** Everything about one client on one screen. This is the money screen — CPAs live here before any client interaction.

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Clients                                          │
│                                                             │
│  ┌─ HEADER ────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  Garcia Real Estate Holdings                        │   │
│  │  LLC · Real Estate · Client since 2019              │   │
│  │                                                     │   │
│  │  [💬 Ask GAAPT]  [📋 Meeting Prep]  [✏️ Edit]       │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ ALERTS ─────────────────────┐  ┌─ KEY INFO ────────┐   │
│  │                              │  │                   │   │
│  │  🟡 1031 deadline in 5 days  │  │  EIN: **-***7892  │   │
│  │     45-day identification    │  │  Year End: Dec 31 │   │
│  │                              │  │  Partner: Mike R. │   │
│  │  🟡 Missing document         │  │  Manager: Sarah C.│   │
│  │     2024 K-1 from Sunset LP  │  │                   │   │
│  │                              │  │  📞 Maria Garcia  │   │
│  └──────────────────────────────┘  │  (512) 555-0123   │   │
│                                    └───────────────────┘   │
│  ┌─ ENTITY STRUCTURE ──────────────────────────────────┐   │
│  │                                                     │   │
│  │    Garcia Holdings LLC (parent)                     │   │
│  │        ├── Sunset Apartments LP (45%)               │   │
│  │        ├── Downtown Retail LLC (100%)               │   │
│  │        └── Garcia 1031 QI Trust                     │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ RECENT ACTIVITY ──────┐  ┌─ OPEN ITEMS ────────────┐   │
│  │                        │  │                         │   │
│  │  Today   3 docs added  │  │  ☐ 1031 property IDs    │   │
│  │  Jan 12  Q4 estimates  │  │  ☐ Review projections   │   │
│  │  Jan 8   Call re: 1031 │  │  ☐ Collect Sunset K-1   │   │
│  │  Dec 15  Year-end plan │  │  ☐ Finalize elections   │   │
│  │                        │  │                         │   │
│  │  [View all →]          │  │  [+ Add item]           │   │
│  └────────────────────────┘  └─────────────────────────┘   │
│                                                             │
│  ┌─ DOCUMENTS ─────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  Tax Returns (12)  K-1s (8)  Financials (23)       │   │
│  │  Correspondence (45)  Planning Memos (6)            │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ ASK ABOUT THIS CLIENT ─────────────────────────────┐   │
│  │                                                     │   │
│  │  What was our depreciation strategy for Downtown?   │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Key features:**
- Entity structure visualization (CPAs think in hierarchies)
- Client-scoped chat input at bottom
- One-click meeting prep generation
- Open items list that persists (checkable)
- Quick copy EIN (masked until hover)
- "What's changed since last visit" capability
- Key contact with click-to-call

**Critical:** The client-scoped "Ask GAAPT" input is prominent. "What was that depreciation issue?" should just work with context.

---

### Chat Conversation — Target State

**Purpose:** Natural language access to everything in the knowledge base.

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  Smith LLC Depreciation                              [···]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ YOU ───────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  What depreciation method did we use for Smith's    │   │
│  │  equipment purchase last year?                      │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ GAAPT ─────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  For Smith & Associates' $50,000 equipment          │   │
│  │  purchase in March 2024, we used Section 179        │   │
│  │  expensing for the full amount.                     │   │
│  │                                                     │   │
│  │  The decision was based on:                         │   │
│  │  • Net income projected over $50k (requirement met) │   │
│  │  • Client preferred immediate deduction vs MACRS    │   │
│  │  • Equipment qualified as §179 property             │   │
│  │                                                     │   │
│  │  ┌─ SOURCES ──────────────────────────────────┐    │   │
│  │  │  📄 Smith 2024 Return - Equipment Schedule │    │   │
│  │  │  📄 Smith Planning Memo - March 2024       │    │   │
│  │  └────────────────────────────────────────────┘    │   │
│  │                                                     │   │
│  │  Want me to pull up the original planning memo?     │   │
│  │                                                     │   │
│  │  [Yes, show memo]  [Draft update memo]              │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Ask a follow-up...                            [↑]  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Critical features:**
- **Source citations are mandatory.** Every factual claim links to the document.
- Suggested follow-up actions in responses
- Quick action buttons contextual to the answer
- Context persistence — if viewing Garcia client page and ask "what about their 1031?" GAAPT knows who "their" refers to

---

### Review Queue — Target State

**Purpose:** Verify AI-extracted data before it enters the knowledge base.

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  Review Queue                                 3 need review │
│  Verify AI-extracted data before it enters your knowledge   │
│                                                             │
│  ┌─ STATS ─────────────────────────────────────────────┐   │
│  │  🟡 3 Pending    👁 1 In Review    ✓ 12 Today    ✗ 0 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [All]  [Pending]  [In Review]  [Approved]  [Rejected]     │
│                                                             │
│  ┌─ DOCUMENT (Expanded) ───────────────────────────────┐   │
│  │                                                     │   │
│  │  W-2 · Brown Medical Group               ⚠️ Review  │   │
│  │  Uploaded 2 hours ago · Confidence: 73%             │   │
│  │                                                     │   │
│  │  ┌─ EXTRACTED ────────┐  ┌─ ORIGINAL ───────────┐  │   │
│  │  │                    │  │                      │  │   │
│  │  │  Employer:         │  │  ┌────────────────┐  │  │   │
│  │  │  Brown Medical ✓   │  │  │                │  │  │   │
│  │  │                    │  │  │  [Document     │  │  │   │
│  │  │  EIN:              │  │  │   preview      │  │  │   │
│  │  │  74-3829173 ✓      │  │  │   image]       │  │  │   │
│  │  │                    │  │  │                │  │  │   │
│  │  │  Wages:            │  │  └────────────────┘  │  │   │
│  │  │  $127,450 ⚠️        │  │                      │  │   │
│  │  │  └ OCR unclear     │  │  [🔍 Zoom] [↻ Rotate]│  │   │
│  │  │    [Edit]          │  │                      │  │   │
│  │  │                    │  │                      │  │   │
│  │  │  Fed Withholding:  │  │                      │  │   │
│  │  │  $28,200 ✓         │  │                      │  │   │
│  │  │                    │  │                      │  │   │
│  │  └────────────────────┘  └──────────────────────┘  │   │
│  │                                                     │   │
│  │  [✓ Approve] [✏️ Edit Fields] [✗ Reject]   ⌘⏎ / ⌘⌫ │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ DOCUMENT (Collapsed) ──────────────────────────────┐   │
│  │  1099-INT · Johnson Corp                 ⚠️ Review  │   │
│  │  Low confidence on payer name                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ DOCUMENT (Collapsed) ──────────────────────────────┐   │
│  │  K-1 · Garcia Real Estate                ⚠️ Review  │   │
│  │  Partner allocation differs from prior year by 15%  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Key features:**
- Side-by-side: extracted data vs original document image
- Field-level confidence indicators with explanations
- Click any field to edit inline
- Keyboard shortcuts: `A` to approve, `R` to reject, `E` to edit
- Document preview with zoom and rotate
- Collapsed cards show why review is needed

**Empty state:** "All caught up — no documents need review right now. ✓"

---

### Dashboard — Target State

**Purpose:** Document processing hub and system health overview.

**Improvements from current:**
- Clicking "Needs Review" or "Failed" cards navigates to Review Queue with filter applied
- Processing queue shows estimated time remaining
- Upload area allows client pre-selection: "Upload for: [Select client ▾]"
- Auto-detect client from document content when possible
- Real-time status updates via WebSocket (no refresh needed)
- Knowledge Base categories are clickable → opens search filtered to that type

---

### Clients List — Target State

**Improvements from current:**
- Clicking a row opens Client 360 detail page
- Entity type colors more distinct:
  - LLC: Blue
  - C-Corp: Teal
  - S-Corp: Purple
  - Partnership: Orange
  - Trust: Green
  - Individual: Gray
- Alert indicators per client row (🟡 = upcoming deadline, 🔴 = overdue item)
- Hover shows mini-preview card with key contacts and next deadline
- "Prospects" can be a separate tab or filter, more prominent

---

## Interaction Patterns

### 1. Progressive Disclosure

Don't show everything at once. Client cards show summary → click for detail. Documents show status → expand for extracted fields.

### 2. Contextual Actions

Every piece of information should have a relevant action:
- Deadline → "Ask GAAPT about this"
- Client name → "View details"
- Document → "View source"
- Dollar amount → "How was this calculated?"

### 3. Keyboard-First for Power Users

```
⌘K          Global search / command palette
⌘N          New chat
⌘/          Focus chat input
G then H    Go to Home
G then C    Go to Clients
G then D    Go to Dashboard
G then R    Go to Review Queue
A           Approve (in review queue)
R           Reject (in review queue)
E           Edit (in review queue)
```

### 4. Remember Everything

- Last viewed client
- Scroll position when returning to pages
- Draft messages not yet sent
- Collapsed/expanded card states
- Filter and sort preferences

---

## Visual Design Direction

### Color System

| Color | Usage | Hex |
|-------|-------|-----|
| Navy (Primary) | Buttons, links, sidebar, logo | #1e3a5f |
| White | Backgrounds, cards | #ffffff |
| Light Gray | Page backgrounds, borders | #f5f5f5 |
| Green | Success, complete, active | #10b981 |
| Amber/Orange | Warning, attention, deadlines | #f59e0b |
| Red | Error, failed, critical | #ef4444 |
| Blue | Info, processing | #3b82f6 |
| Purple | Trust entity type, special | #8b5cf6 |
| Teal | C-Corp entity type | #14b8a6 |

### Typography

- **Font family:** Inter, SF Pro, or similar clean sans-serif
- **Base size:** 16px minimum (CPAs stare at numbers all day)
- **Headings:** Semi-bold, clear hierarchy
- **Numbers:** Tabular figures for alignment (critical for financial data)
- **Monospace:** For EINs, account numbers, code

### Density

- Medium-high density is acceptable — CPAs are used to Excel
- Use whitespace strategically to group related items
- Show more info if it reduces clicks

### Motion & Feedback

- Subtle, purposeful animations
- Loading states feel like "working" not "broken"
- Success animations provide satisfaction (document approved ✓)
- Skeleton loaders instead of spinners where possible

---

## What "Magical" Looks Like

The difference between 8/10 and 10/10 is anticipation.

**8/10:** User asks "what's the Smith depreciation situation?" and gets a good answer.

**10/10:** User opens Smith client page and GAAPT says "You asked about equipment depreciation yesterday — they decided to proceed with Section 179. Want me to draft the memo?"

**8/10:** Deadline alerts show up in a list.

**10/10:** 3 days before deadline, GAAPT appears: "Garcia 1031 identification deadline is in 3 days. They've identified 2 properties so far. Want me to summarize the options you discussed?"

**8/10:** Document processing shows progress.

**10/10:** When processing finishes, GAAPT says "Processed the Brown Medical W-2. Wages are $12k higher than last year — probably that promotion from the planning memo. Flag it?"

---

## Success Metrics

The interface is 10/10 when:

1. **New staff are useful in days, not months** — They ask GAAPT instead of interrupting seniors
2. **Meeting prep takes 30 seconds, not 30 minutes** — One click, instant context
3. **Nothing falls through the cracks** — Deadlines surfaced before they're urgent
4. **Senior staff get time back** — Routine questions handled by AI
5. **CPAs voluntarily use it** — Not because they're told to, because it helps

---

## Implementation Priority

### Phase 1: Core Depth
1. Client 360 detail page (the money screen)
2. Review Queue document cards with field editing
3. Alert click → contextual chat flow
4. Search with real results and source citations

### Phase 2: Polish
5. Skeleton loaders throughout
6. Keyboard shortcuts
7. Empty states with guidance
8. Entity type color refinement

### Phase 3: Magic
9. Meeting prep generator
10. Proactive chat suggestions based on context
11. "What's changed" comparisons
12. Real-time WebSocket updates

---

## Appendix: Component Inventory

### Cards
- Alert card (with severity indicator, action link)
- Client row (list view)
- Client preview (hover card)
- Document card (processing status)
- Review document card (expandable, with extracted data)
- Conversation card (recent/starred)
- Stat card (number + label + icon)

### Forms
- Chat input (with attachment, suggestions)
- Search input (with filters)
- Document upload zone
- Field editor (inline, for review queue)

### Navigation
- Sidebar (collapsible on mobile)
- Tabs (for filtering)
- Breadcrumbs (for detail pages)
- Command palette (⌘K)

### Feedback
- Toast notifications
- Loading skeletons
- Progress indicators
- Empty states
- Error states

---

*End of Design Brief*
