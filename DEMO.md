# Demo Script — Marty Pricing Agent

> **Time budget:** ~3 minutes (or 60 seconds in "hero mode" — see end).
> **Audience:** Walmart Marketplace product/eng leadership or hackathon judges.
> **Setup:** `uvicorn app.main:app --port 8910` then open http://127.0.0.1:8910/

---

## 🎬 The 3-minute walkthrough

### Beat 1 — "Look familiar?" (15 sec)

> *"This is Seller Center. You'll notice the top-bar Marty orb on the right — that's the existing Marty AI assistant Walmart already ships. You'll also notice a new item in the left nav: **Pricing → Pricing Agent**. That's what we built."*

🎯 **Show:** The page at `/`. Point at the Marty orb (top right) and the left-nav highlight (Pricing → Pricing Agent).

---

### Beat 2 — The mode banner (15 sec)

> *"At the top: a mode banner. The agent has 3 states — Shadow, Recommend, Autopilot — that map directly to a trust on-ramp. Sellers start in Shadow ('watch me, don't trust me yet'), graduate to Recommend ('queue everything'), and eventually Autopilot ('handle the boring stuff yourself')."*

🎯 **Click:** Recommend → Autopilot. Watch the banner color shift and the tagline change.

---

### Beat 3 — The risk-tiered action model (20 sec)

> *"Here's our core IP: a risk-tiered action model. Every pricing decision the agent makes is tagged Low, Medium, or High. Low risk is auto-executable — SPIP un-suppression, Buy Box match within your floor. Medium is bulk-approve — Pro Seller maintenance, slow-mover markdowns. High is always-approve — below-cost, MAP violations, hero SKUs."*

🎯 **Show:** The "Risk-tiered action model" card on the overview, then the KPI strip above it.

---

### Beat 4 — Trust mechanic: visible refusal (20 sec)

> *"Look at this — **'Blocked by your guardrails.'** Dr. Brown's bottles. A competitor dropped to $6.99. To match, I'd have to break TWO of your guardrails — the price floor AND the cost floor. So I refused, and I'm telling you I refused. That's the trust mechanic."*

🎯 **Click:** The Dr. Brown's row → lands on `/agent/action/...`. Show the two 🛑 blocked guardrails.

---

### Beat 5 — The agent inbox (25 sec)

> *"Click into the inbox. Four tabs: Needs Approval, Auto-executed, Blocked, Dismissed. Filter by cohort, by risk tier, by action type. And — for medium-tier bulk work — multi-select rows and **approve them in one click**. This is how a seller with 30,000 SKUs actually keeps up."*

🎯 **Navigate:** `/agent/inbox`. Click the cohort dropdown, then the tier chips. Select 2 rows → "✓ Approve selected".

---

### Beat 6 — Explanation panel (30 sec)

> *"Click any action and you get the full explanation panel. Market signal — what competitor changed, when. Reasoning narrative in plain English. Every guardrail check — pass or fail. Simulation: 'If you approve, this happens, ~90% chance you win Buy Box, reversible in 1 click.' And then the action button."*

🎯 **Click:** Garnier action (the auto-executed SPIP unsuppress). Walk through the 4 sections.

---

### Beat 7 — Marty chat (30 sec)

> *"Now the fun part. Click the Marty orb."*

🎯 **Click:** Marty orb (top right). Panel slides in.

> *"I'm going to ask Marty 4 things back-to-back."*

🎯 **Type:** `Show me what you did today`
- Daily digest appears: stat strip, recent auto-executions, pending actions, bulk-approve button.

🎯 **Type:** `Why did you drop Garnier?`
- Market signal panel, reasoning, all guardrails passed, **inline rollback button**.

🎯 **Type:** `What's my biggest risk right now?`
- Surfaces the blocked Dr. Brown's bottles with a card preview.

🎯 **Type:** `Switch to autopilot`
- Confirmation card with yellow warning ("I'll start auto-executing immediately") → click **"Yes, switch to Autopilot"**.

> *"And the mode banner on the overview page now reads Autopilot."*

🎯 **Click:** Back to `/` to confirm the mode banner switched.

---

### Beat 8 — The wrap (15 sec)

> *"To recap: Walmart sellers already have Repricer, Pricing Insights, Success Hub, Promotions. They don't need more dashboards — they need delegation. Marty Pricing Agent ships native, free, tiered-autonomy pricing inside the surface sellers already trust, with **the strictest guardrails in the market**. Trust is the moat."*

---

## ⚡ The 60-second "hero mode" (for impatient audiences)

Run **only** beats 4, 6, 7, 8:

1. *"This is the agent's overview. Notice 'Blocked by your guardrails' — the agent visibly refuses to take an action that would break a seller rule."* (10s)
2. *"Click any action and you get the full explanation panel: market signal, reasoning, guardrail check, simulation, approve/rollback."* (15s)
3. *"Now Marty chat. 'Show me what you did today' — daily digest in chat. 'Why did you drop Garnier?' — market signal + reasoning + rollback button. 'Switch to autopilot' — mode change with safety confirmation. All actions execute for real."* (25s)
4. *"Walmart wins by shipping native, free, tiered-autonomy pricing with the strictest guardrails. Trust is the moat."* (10s)

---

## 🧪 If a judge asks…

**Q: How is this different from Walmart Repricer?**
A: Repricer is a rules engine — you set min/max and it reacts. The Pricing Agent is an **orchestrator** — it reads Repricer state, SPIP signals, Buy Box telemetry, Success Hub recommendations, inventory levels, and fee-linked offers, then proposes the right action across all of them with explicit risk tiering. Repricer is one of the tools Marty calls.

**Q: How is this different from Amazon's Seller Assistant?**
A: Amazon's is broad (catalog/inventory/compliance/pricing) and feels like a help-bot with action capabilities bolted on. Ours is **focused on pricing with explicit risk tiers and Shadow mode** — meaning sellers can verify the agent's behavior before granting authority. Amazon doesn't have visible refusal or mode staging. See `docs/walmart-vs-amazon-gap-analysis.md` for the full breakdown.

**Q: What's the real LLM doing here?**
A: Mock-LLM (regex intent routing) for the demo — proves the UX. Production would swap in **Element + Pydantic AI** with the same intent set as the system prompt. The interface contract is already shaped.

**Q: How do you measure success?**
A: PRD §3 metrics: SPIP suppression time (hours → <15 min), Buy Box win-rate uplift vs holdout, 50% reduction in Pro Seller churn from price competitiveness, 60%+ adoption among 100+ SKU sellers, NPS ≥60, <2% rollback rate.

**Q: What about MAP/MSRP and below-cost edge cases?**
A: Both are HIGH-tier always-approve actions per PRD §5. The data model has `cost`, `floor_price`, `ceiling_price` per SKU + `respect_map` / `respect_msrp` toggles on the policy. The Hot Wheels MAP-violation case is in the seeded demo data — click it to see the blocked guardrail in action.

**Q: Why does this live inside Marty instead of being its own shingle?**
A: Two reasons. (1) Sellers already trust Marty for Q&A — bolting agency onto a trusted surface beats launching a new one. (2) Marty's the right home for the conversational layer (digests, "why did you do X?", bulk approve in chat) — keeping it cohesive avoids confusion.

---

## 🔄 Reset between demos

Just restart the server:

```bash
pkill -f "uvicorn app.main:app"
uvicorn app.main:app --port 8910 &
```

All state is in-memory. Fresh data every time.
