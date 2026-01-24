# Rookie Website Design Brief

**Project Owner**: You're looking at him **Status**: Execute this

---

## Brand Position

Rookie is the first AI that actually *does* accounting work instead of just talking about it. We're not another SaaS dashboard. We're a digital employee.

**Core tension we're playing with**: Confident about what we do, humble about what we are. The name "Rookie" is intentional - we're not pretending AI is a senior partner. It's a new hire that earns trust.

**Tone**: Professional but not corporate. Smart but not smug. A bit irreverent without being unprofessional. Think "the competent friend who also makes you laugh."

**We are NOT**:

- Enterprise software aesthetic (no blue gradients and handshake stock photos)
- Startup bro energy (no "disrupting" or "revolutionizing")
- Generic AI hype (no glowing brains, neural networks, robot hands)

---

## Site Structure

### Pages Required

**1. Home**

- Hero with clear value prop: "Your AI junior accountant"
- The problem (talent shortage, burnout, turnover)
- The solution (actual work output, not chatbot answers)
- Trust model overview (earns responsibility like any new hire)
- CTA to waitlist/demo

**2. How It Works**

- Visual workflow: assign → prepare → review → feedback → improve
- What Rookie produces (worksheets, preparer notes, categorized transactions)
- The "earning trust" progression (heavy review → spot checks → exception-only)
- Integration points (TaxDome, Drake, QuickBooks)

**3. For CPA Firms** (primary audience page)

- Pain points we solve (staffing, turnover, tax season hell)
- Economics comparison (junior hire vs Rookie)
- Security/compliance positioning
- Specific use cases by work type

**4. About/Philosophy**

- Why "Rookie" as a name
- Human-in-the-loop commitment (CPAs remain liable, AI prepares)
- The team (when ready)

**5. Waitlist/Contact**

- Simple form: firm name, email, firm size, pain level (1-10)
- No sales call pressure - "we'll reach out when we're ready for you"

---

## Design Direction

### Visual Identity

**Color palette**:

- Primary: Something unexpected. Not blue (every fintech), not green (every accounting app). Consider warm neutrals with one bold accent - maybe a confident amber/gold or an unexpected coral.
- Support with clean whites, warm grays
- Dark mode optional but not required

**Typography**:

- Headlines: Something with character. Slightly condensed or geometric. Not boring, not wacky.
- Body: Clean, readable, professional. Think Inter, Söhne, or similar.
- Consider a subtle monospace accent for technical elements

**Imagery approach**:

- Absolutely no stock photos of people in suits shaking hands
- No floating dashboards, no AI brains
- Consider: clean illustrations, subtle animations, maybe actual screenshots of output artifacts
- If showing "AI at work" - show the *output* (clean worksheets), not robots

**Overall feel**:

- Modern but warm
- Confident but approachable
- Like a really well-designed productivity tool, not a corporate brochure

### Key Visual Elements to Design

1. **The "trust progression" graphic** - showing how supervision decreases as accuracy increases
2. **Workflow diagram** - how a task flows from assignment to completion
3. **Comparison visual** - junior hire vs Rookie (not a cringe chart, something clever)
4. **Output samples** - actual examples of what Rookie produces (can be mock data)

---

## Messaging Hierarchy

### Headline options to test:

- "Your AI junior accountant" (current favorite)
- "All the effort, none of the drama"
- "The junior who never calls in sick"
- "Finally, AI that does the work"

### Supporting copy themes:

1. **It's not a chatbot** - emphasize actual work output vs Q&A
2. **Earns trust over time** - realistic expectations, not magic promises
3. **You stay in control** - human review required, CPA remains liable
4. **Knowledge that stays** - client profiles compound, no turnover loss

### Phrases to use:

- "Prepares, not suggests"
- "Work products, not chat responses"
- "Earns responsibility"
- "Your firm's knowledge, retained"

### Phrases to absolutely avoid:

- "Revolutionary" / "Disrupting"
- "Powered by AI" (weak sauce)
- "Digital transformation"
- "Leverage" as a verb
- "Best-in-class"
- Any promise of replacing CPAs

---

## Technical Requirements

**Build approach**:

- Static site preferred (Next.js, Astro, whatever ships fast)
- No CMS needed initially - we'll iterate in code
- Deploy on Vercel/Netlify/Cloudflare

**Performance**:

- Sub-2-second load time
- Mobile-first responsive
- Core Web Vitals green across the board

**Forms**:

- Waitlist form → wherever we're collecting leads (Notion, Airtable, whatever)
- Keep it stupid simple

**Analytics**:

- Plausible or Fathom (privacy-respecting)
- No need for enterprise analytics bloat

---

## What Success Looks Like

A CPA partner lands on this site at 11pm during tax season, exhausted, skeptical of AI promises, and:

1. Immediately understands what Rookie does (not another chatbot)
2. Sees themselves in the problem description
3. Gets the "new employee" mental model instantly
4. Feels like this was built by people who understand accounting
5. Joins the waitlist without feeling like they're signing up for sales harassment

---

## Deliverables Expected

1. **Moodboard/direction** (3 options)
2. **Wireframes** for all 5 pages
3. **High-fidelity designs** for approved direction
4. **Component library** for future expansion
5. **Deployed site** with working waitlist form

---

## Timeline

You tell me what's realistic. I'd rather have excellent in 4 weeks than mid in 2.

---

## Final Note

The CPA market is drowning in generic software marketing. Every tool promises to "streamline workflows" and "boost productivity."

Rookie's website should feel different - like it was made by people who've actually seen the inside of a CPA firm during busy season. Grounded. Real. Maybe even a little funny.

Make something we'd be proud to show firms. Make something that doesn't look like every other B2B SaaS landing page.

Now go build it.