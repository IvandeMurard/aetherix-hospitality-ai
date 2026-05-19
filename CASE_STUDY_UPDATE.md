# Case Study Update — Hospitality Agentic Mesh Positioning

> **For Lovable / future me.** Copy-paste this entire document as a prompt to update the Aetherix case study on `ivandemurard.com`.

---

## Target files

Primary: `src/pages/Atherix.tsx`
Mirror (source-of-truth comment at top of the file): `public/atherix.md` and `public/llms-full.txt`
Possibly: `src/components/atherix/AetherixArchitectureDiagram.tsx` (verify no Qdrant references remain)

---

## Why this update

Aetherix has evolved architecturally. It is no longer positioned as a standalone "framework" but as the **F&B Execution Node** of a broader system: the **Hospitality Agentic Mesh** — a constellation of specialized AI agents communicating exclusively via MCP (Model Context Protocol).

The case study must reflect this new positioning while keeping the existing product narrative (warmth, hotel operations focus, human-in-the-loop). **Tone stays product/business-oriented — not technical.** Parallel narrative with the GitHub README (already updated, see `https://github.com/IvandeMurard/aetherix-hospitality-ai`).

## The Mesh — four nodes

| Node | Role | Status |
|------|------|--------|
| **Aetherix** | F&B Execution Node — forecast, staffing, memory, receipts | Live (staging) |
| **Tacet** | Sensory Node — environmental signals (weather, noise, public events) | Phase 3 |
| **Orchestrator** | Supervisory Agent — routes between nodes via MCP, applies hotel business rules | Phase 3 stub |
| **Anima** | Guest Context Node — relational memory (emotional, logistic, CRM) | Phase 4 |

Key principle: **MCP is the only interface.** No monolith. Each node has a strict bounded context. The whole system plugs into PMS Agent Hubs (Apaleo today, Mews next) like LEGO.

---

## Patches to apply

### Patch 1 — `PROJECT_INFO` constants (top of file)

Replace the entire array with:

```tsx
const PROJECT_INFO: { label: string; value: string; href?: string; wide?: boolean }[] = [
  { label: "Role", value: "Product Builder & AI Agent Designer (side project)" },
  { label: "Duration", value: "2026 – ongoing (validation phase)" },
  { label: "Team", value: "Solo architect & builder" },
  {
    label: "Repository",
    value: "GitHub Repository",
    href: "https://github.com/IvandeMurard/aetherix-hospitality-ai",
  },
  {
    label: "Context",
    value: "F&B Execution Node of the Hospitality Agentic Mesh — staffing, F&B forecasting, WhatsApp push, MCP-native",
    wide: true,
  },
  {
    label: "Current Status",
    value: "MCP Server v0 shipped · Staging live on Fly.io (Paris) · Apaleo OAuth + MCP read operational · Design partner pilot starting (Phase 3)",
    wide: true,
  },
  {
    label: "Mesh",
    value: "Aetherix (F&B) · Tacet (Sensory Node) · Orchestrator (Supervisory Agent) · Anima (Guest Context — Phase 4)",
    wide: true,
  },
];
```

**Why:** repo URL updated, "Companion" renamed to "Mesh" and lists all 4 nodes, Current Status reflects May 2026 reality, Context anchors Aetherix as "F&B Execution Node of the Mesh".

---

### Patch 2 — Hero subtitle paragraph

Find the `<p>` inside the hero (`data-reveal-child` with `--reveal-delay: 320ms`):

**Replace:**
```tsx
<p>
  Aetherix is an <Term id="agenticAi">agentic</Term> framework focused on hotel operations. It anticipates staffing, <Term id="fnb">F&B</Term>
  {" "}preparation, and resource needs in real time, reduces food waste and operational costs, and frees the
  human team to deliver exceptional guest experiences.
</p>
```

**With:**
```tsx
<p>
  Aetherix is the F&B Execution Node of the Hospitality Agentic <Term id="agenticAi">Mesh</Term>. It anticipates staffing, <Term id="fnb">F&B</Term>
  {" "}preparation, and resource needs in real time, reduces food waste and operational costs, and frees the
  human team to deliver exceptional guest experiences — while remaining callable by any other agent in your stack.
</p>
```

---

### Patch 3 — New section "Part of a Mesh"

Insert this section **after** the existing "Architecture" `<Reveal>` section (the one with `AetherixLayerStack`), and **before** `<SectionDivider label="The Vision" index="02" />`.

Add a new `SectionDivider`:
```tsx
<SectionDivider label="The Mesh" />
```

Then the section itself:

```tsx
<section className="px-6 md:px-12 mb-12 md:mb-16">
  <div className="max-w-screen-2xl mx-auto">
    <div className="text-center mb-12 max-w-3xl mx-auto">
      <span className="font-label uppercase tracking-[0.25em] text-[10px] text-secondary">Part of a Mesh</span>
      <h2 className="font-headline italic text-3xl md:text-5xl text-primary mt-4 leading-tight">
        Aetherix does not orchestrate. It executes.
      </h2>
      <p className="text-on-surface-variant mt-6 leading-relaxed">
        The future of hotel tech is composable. Aetherix is one node of the Hospitality Agentic Mesh — a constellation of specialized AI agents communicating exclusively via MCP. Each node owns one domain with precision. A supervisory agent routes between them, applying your hotel's business rules. The result: a system that plugs into PMS Agent Hubs (Apaleo today, Mews next) like LEGO, rather than replacing them.
      </p>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto">
      <div className="p-6 bg-surface-container-low border border-secondary/30 rounded-2xl">
        <span className="font-label uppercase tracking-widest text-[10px] text-secondary">Live</span>
        <h3 className="font-headline italic text-xl text-primary mt-2 mb-3">Aetherix</h3>
        <p className="text-sm text-on-surface-variant leading-relaxed">F&B Execution Node — forecast, staffing, memory, receipts.</p>
      </div>
      <div className="p-6 bg-surface-container-low border border-outline-variant/20 rounded-2xl">
        <span className="font-label uppercase tracking-widest text-[10px] text-secondary">Phase 3</span>
        <h3 className="font-headline italic text-xl text-primary mt-2 mb-3">Tacet</h3>
        <p className="text-sm text-on-surface-variant leading-relaxed">Sensory Node — weather, noise, public events → structured signals.</p>
      </div>
      <div className="p-6 bg-surface-container-low border border-outline-variant/20 rounded-2xl">
        <span className="font-label uppercase tracking-widest text-[10px] text-secondary">Phase 3</span>
        <h3 className="font-headline italic text-xl text-primary mt-2 mb-3">Orchestrator</h3>
        <p className="text-sm text-on-surface-variant leading-relaxed">Supervisory Agent — routes between nodes, applies hotel business rules.</p>
      </div>
      <div className="p-6 bg-surface-container-low border border-outline-variant/20 rounded-2xl opacity-70">
        <span className="font-label uppercase tracking-widest text-[10px] text-secondary">Phase 4</span>
        <h3 className="font-headline italic text-xl text-primary mt-2 mb-3">Anima</h3>
        <p className="text-sm text-on-surface-variant leading-relaxed">Guest Context Node — relational memory: emotional state, flight delays, CRM history.</p>
      </div>
    </div>
  </div>
</section>
```

---

### Patch 4 — Reframe "Aetherix and Tacet" section

In the "Synergy with Tacet" section, find the centered intro block (`<div className="text-center mb-16">`):

**Replace title:**
```tsx
<h2 className="font-headline text-4xl md:text-5xl italic text-primary mb-6">Aetherix and Tacet</h2>
```
**With:**
```tsx
<h2 className="font-headline text-4xl md:text-5xl italic text-primary mb-6">Aetherix ↔ Tacet</h2>
```

**Replace the `<p>` below it:**
```tsx
<p className="text-on-surface-variant max-w-2xl mx-auto leading-relaxed">
  Aetherix reads internal context (<Term id="pms">PMS</Term>, occupancy, F&B, staffing).{" "}
  <Link to="/tacet" className="text-secondary border-b border-secondary/30 hover:border-secondary transition-colors">
    Tacet
  </Link>
  {" "}reads external context (street, weather, events). Together they form one predictive digital twin for the hotel.
</p>
```
**With:**
```tsx
<p className="text-on-surface-variant max-w-2xl mx-auto leading-relaxed">
  Two nodes of the same Mesh, two domains, one conversation via MCP. Aetherix reads <Term id="pms">PMS</Term>, occupancy, F&B, staffing — the property's internal operations.{" "}
  <Link to="/tacet" className="text-secondary border-b border-secondary/30 hover:border-secondary transition-colors">
    Tacet
  </Link>
  {" "}reads the world outside — weather, noise, public events. The Orchestrator combines both into a single decision: <em className="italic">if Tacet detects 65dB roadworks tomorrow morning, Aetherix adjusts staffing for the in-room breakfast surge it anticipates.</em>
</p>
```

Keep the two cards (Aetherix internal / Tacet external) as-is — they still work.

---

### Patch 5 — "Intelligent Anticipation" section

Find the `<p>` describing the four layers:

**Replace:**
```tsx
<p data-reveal-child style={{ ["--reveal-delay" as string]: "200ms" }} className="text-on-surface-variant max-w-2xl text-lg">
  Four layers, one recommendation. Prophet forecasts tomorrow's covers and shifts. Qdrant matches today against 495+ past scenarios. pgvector remembers what worked in <em className="italic">your</em> hotel. Claude Sonnet turns the whole picture into one plain-language call, pushed only when it matters, and callable by any other agent over <Term id="mcp">MCP</Term>.
</p>
```

**With:**
```tsx
<p data-reveal-child style={{ ["--reveal-delay" as string]: "200ms" }} className="text-on-surface-variant max-w-2xl text-lg">
  Four layers, one recommendation. Prophet forecasts tomorrow's covers and shifts. pgvector recalls how similar days played out across <em className="italic">your</em> property's history. HiveMemory adds anonymized patterns from peer hotels in the same segment. Claude Sonnet — with Gemini and GPT on fallback — turns the whole picture into one plain-language call, pushed only when it matters, and callable by any other agent over <Term id="mcp">MCP</Term>.
</p>
```

A few lines below, find the "Proactive Messaging" card's `<p>`:

**Replace:**
```tsx
<p className="text-on-surface-variant leading-relaxed">
  Recommendations land where teams already work: WhatsApp first, with explainable reasoning attached. Apaleo OAuth gives read access, an outbound MCP server lets orchestration agents call Aetherix directly.
</p>
```

**With:**
```tsx
<p className="text-on-surface-variant leading-relaxed">
  Recommendations land where teams already work: WhatsApp first, with explainable reasoning attached. Apaleo OAuth gives read access. The MCP Server v0 is live — three atomic tools, multi-tenant by design, ready for orchestration agents and the Apaleo Agent Hub.
</p>
```

And the caption right below it:

**Replace:** `Apaleo PMS, MCP callable, WhatsApp delivery`
**With:** `Apaleo MCP · MCP Server v0 live · WhatsApp delivery · Fly.io Paris`

---

### Patch 6 — FAQ array

Replace the entire `FAQ` constant with:

```tsx
const FAQ = [
  {
    q: "What stage is Aetherix currently at?",
    a: "MCP Server v0 is shipped. Staging is live on Fly.io (Paris). The backtest harness is built and the first real-world MAPE measurement is pending — it will run on design partner data in Phase 3, currently starting.",
  },
  {
    q: "Is this already deployed in production hotels?",
    a: "Not yet. We are in technical validation and onboarding the first design partner on Apaleo prod (Phase 3).",
  },
  {
    q: "What is the role of the human team?",
    a: "Humans stay firmly in the loop for strategic decisions. Aetherix proposes, never decides alone.",
  },
  {
    q: "How does it integrate with existing hotel systems?",
    a: "Through Apaleo PMS (OAuth2 + MCP) today, Mews next. WhatsApp for delivery. MCP for inbound agent calls. No new dashboard to learn.",
  },
  {
    q: "What is the Hospitality Agentic Mesh?",
    a: "An architecture of specialized AI agents — Aetherix (F&B), Tacet (environmental), Anima (guest context, Phase 4) — orchestrated by a supervisory agent. They communicate via MCP only, with no monolithic dependencies. Each node has a strict bounded context, making the whole system composable and PMS-agnostic.",
  },
  {
    q: "How does Aetherix relate to Tacet?",
    a: "Both are nodes of the Hospitality Agentic Mesh. Aetherix reads internal context (PMS, occupancy, F&B, staffing). Tacet reads external context (weather, noise, public events). They communicate exclusively via MCP, never as a monolith.",
  },
];
```

---

### Patch 7 — "Explore the Platform" GitHub link

Find the `<a href="https://github.com/IvandeMurard/Hospitality-Operations-Agentic-AI-B2B" ...>` in the "Explore the Platform" section.

**Replace href with:** `https://github.com/IvandeMurard/aetherix-hospitality-ai`

---

## Mirror files

After updating `src/pages/Atherix.tsx`, apply the equivalent factual updates (no JSX needed) to:
- `public/atherix.md`
- `public/llms-full.txt`

The source-of-truth comment at the top of the TSX file mandates this synchronization.

## Diagram component

Open `src/components/atherix/AetherixArchitectureDiagram.tsx` and verify:
- No more references to **Qdrant** (replaced by pgvector + HiveMemory)
- No more "**495+ patterns**" hardcoded number
- Mention of **Fly.io (Paris)** as deployment context (optional, for parallelism with the GitHub README)
- LLM block shows **Claude Sonnet (primary) / Gemini · GPT (fallback)** via the `LLMProvider` abstraction

If the diagram is image-based, no edit needed — flag it for a redraw later.

---

## Validation checklist

- [ ] PROJECT_INFO updated (repo URL, status, Mesh row)
- [ ] Hero subtitle mentions "F&B Execution Node of the Mesh"
- [ ] New "Part of a Mesh" section visible with 4 cards
- [ ] Aetherix ↔ Tacet section reframed (MCP, Orchestrator scenario)
- [ ] Anticipation section: Qdrant removed, HiveMemory + fallback added
- [ ] "MCP Server v0 is live" replaces "in progress"
- [ ] FAQ has 6 questions, includes Mesh question
- [ ] GitHub link points to `aetherix-hospitality-ai`
- [ ] Mirror files (`public/atherix.md`, `public/llms-full.txt`) synced
- [ ] No claim of MAPE results (no real-world measurement yet)
