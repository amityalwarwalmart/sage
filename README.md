# Marty Pricing Agent

> A **policy-driven, risk-tiered AI Pricing Agent** built inside **Marty**, Walmart Marketplace's existing in-Seller-Center assistant. Built for the Walmart Marketplace hackathon, May 2026.

**🎯 What it does:** Automates the boring, high-frequency pricing decisions sellers don't have time for (SPIP un-suppression, Buy Box match/beat, slow-mover markdowns) — while keeping every risky action behind a human-in-the-loop approval queue with full guardrails, reasoning, and one-click rollback.

**🧭 Where it lives:** As a new sub-item under **Pricing** in the Seller Center left nav. Conversational layer slides in from the right via Marty (matches the production Marty UX).

---

## 🪄 The 60-second pitch

Walmart Marketplace already has the ingredients — Repricer, Pricing Insights, Success Hub, Promotions, Pricing APIs. Sellers just don't have time to orchestrate them. Marty Pricing Agent does the orchestration:

| Tier | What it covers | What Marty does |
|---|---|---|
| 🟢 **Low risk** | SPIP un-suppress, Buy Box match within floor, beat-by-1¢, revert expired promo | **Auto-executes** within seller guardrails |
| 🟡 **Medium risk** | Pro Seller maintenance, >5% drops, slow-mover markdowns, fee-linked offers | **Bulk approval digest** — seller signs off in one click |
| 🔴 **High risk** | Below-cost, MAP violations, new SKU pricing, hero SKUs, bundles | **Always approve** — never silent |

**Trust is the moat.** Every action shows its market signal, every guardrail check is visible, the agent visibly refuses to act when guardrails would be violated, and a 3-stage rollout (**Shadow → Recommend → Autopilot**) gives sellers an on-ramp to trust the system.

---

## 📚 Strategic basis

This product was built directly from two foundational documents (included in `docs/`):

- **PRD** — `marketplace_pricing_agent_prd.md` (Pricing PM brief, with risk-tiered action model + 90-day MVP scope)
- **Deep research report** — `deep-research-report.md` (competitive scan: Amazon Automate, Shopify Sidekick, Alibaba AABA, Pokee, StoreClaw, Qeen, plus academic work on AI delegation)

Both docs converge on the same finding: **sellers want delegation, not more dashboards** — but only when intent is clear, stakes are contained, and reversal is easy. Every UI decision in this repo traces back to that principle.

---

## 🧱 Architecture

```
Seller Center shell (left nav · top bar · Marty orb)
└── Pricing (top-level)
    ├── Pricing insights / Automate pricing / Incentives / ...
    └── 🆕 Pricing Agent (powered by Marty)
        ├── /              · Agent overview      (mode banner + KPIs + tier breakdown + needs-approval preview)
        ├── /agent/inbox   · Agent inbox         (4 tabs · cohort/tier/action-type filters · bulk approve/reject)
        ├── /agent/action/{id} · Action detail   (market signal · reasoning · guardrails · simulation · approve/reject/rollback)
        ├── /agent/policy  · Policy & guardrails (4-step wizard + ongoing settings view)
        └── /agent/history · Action history      (timeline · per-row rollback)

Marty panel (slide-in right, anchored to the top-bar orb)
└── /marty/chat   · Intent-routed conversational layer
    └── /marty/action · Inline button actions (approve / reject / rollback / bulk approve / set mode)
```

**Stack:** Python 3.13 · FastAPI · HTMX · Tailwind (CDN) · Jinja2 · in-memory mock data (resets on restart, demo-friendly).

---

## 🛠️ Run it locally

```bash
# Clone
git clone https://github.com/amityalwarwalmart/sage.git
cd sage

# Set up venv (use uv if you have it, otherwise stdlib venv)
uv venv && source .venv/bin/activate
uv pip install fastapi 'uvicorn[standard]' jinja2 python-multipart \
  --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple \
  --allow-insecure-host pypi.ci.artifacts.walmart.com  # Walmart internal mirror

# Run
uvicorn app.main:app --host 127.0.0.1 --port 8910 --reload

# Open
open http://127.0.0.1:8910/
```

The app comes pre-seeded with **14 pricing actions** across all 3 risk tiers using **real SKUs from production Seller Center screenshots** (Garnier, Davidoff, Pilot G2, Hot Wheels, Fuji Instax, Burberry, Mederma, Minwax, Dr. Brown's).

State is in-memory — restart the server to reset for a fresh demo run.

---

## 🎬 Demo script

See **[`DEMO.md`](DEMO.md)** for the full 60-second walkthrough. Quick version:

1. **Open `/`** — agent overview with mode banner, KPIs, tier breakdown, needs-approval preview
2. **Toggle the mode banner** (Shadow → Recommend → Autopilot) — watch the page state shift
3. **Click the purple Marty orb top-right** → slide-in panel opens
4. **Type "Show me what you did today"** → daily digest with inline approve buttons + bulk-approve-all
5. **Type "Why did you drop Garnier?"** → market signal + reasoning + guardrail check + inline rollback button
6. **Type "What's my biggest risk?"** → surfaces the blocked Dr. Brown's bottles (below-cost guardrail saved them)
7. **Click any "✓ Approve" button in chat** → action approves for real, audit log captures the event
8. **Type "Switch to autopilot"** → confirmation with warning callout → confirm → mode banner updates on the overview page

---

## 🗂️ Project structure

```
app/
├── main.py                          ← FastAPI entrypoint + router wiring
├── data/
│   ├── marty.py                     ← Current data layer (PricingAction, SellerPolicy, MarketSignal, etc.)
│   └── mock.py                      ← Legacy Sage data (kept for evolutionary history; not wired in)
├── routers/
│   ├── agent_overview.py            ← / (the dashboard)
│   ├── agent_inbox.py               ← /agent/inbox (triage)
│   ├── agent_action.py              ← /agent/action/{id} (explanation panel)
│   ├── agent_policy.py              ← /agent/policy + /agent/policy/setup/1..4 (wizard)
│   ├── agent_history.py             ← /agent/history (audit timeline)
│   └── marty_chat.py                ← /marty/chat + /marty/action (conversational layer)
├── templates/
│   ├── base.html                    ← Seller Center shell + Marty panel
│   ├── agent_overview.html
│   ├── agent_inbox.html
│   ├── agent_action.html
│   ├── agent_policy.html
│   ├── agent_policy_wizard.html
│   └── agent_history.html
└── templates_env.py                 ← Jinja env + custom filters

docs/
├── seller-center-action-inventory.confluence.txt  ← qa-kitten's 68-action risk classification
└── walmart-vs-amazon-gap-analysis.md              ← Why Walmart wins vs Amazon Seller Assistant

DEMO.md                              ← Scripted 60-second walkthrough
README.md                            ← You are here
```

---

## 🧠 Design decisions (the "why")

| Decision | Why |
|---|---|
| **Lives inside Marty, not a new shingle** | Sellers already trust Marty for Q&A. Bolting agency onto a trusted surface beats launching a new one. (Matches Amazon's Seller Assistant pattern.) |
| **Pricing-only scope (v1)** | The PRD calls for orchestrating existing Walmart primitives, not boiling the ocean. Pricing has the clearest signals, fastest feedback loops, and most measurable upside. |
| **Risk-tiered action model is core IP** | Every other agent in the market is rules-only (Amazon Automate, Walmart Repricer) or advice-only (Shopify Sidekick). Walmart wins by being the first to ship **explicit tiers tied to autonomy levels**, all visible. |
| **Mode staging (Shadow → Recommend → Autopilot)** | Direct from research: "delegation rises when intent is clear, stakes are contained, and reversal is easy." Shadow mode lets sellers verify behavior before granting authority. |
| **"Blocked by guardrail" is a first-class state** | Most agents hide their refusals. Surfacing them is the strongest trust signal — *"I almost did this, here's why I didn't"*. |
| **One-click rollback on every executed action** | Trust = reversibility. If the seller can undo anything in one click, the perceived risk of approving drops dramatically. |
| **Real SKUs from screenshots, not fake** | "Garnier Nutrisse" hits differently than "Product A". Grounded demo data is 10x more believable. |
| **Bulk approve in chat** | PRD §7 explicitly: *"Bulk approval digest in Marty chat for Medium-tier actions"* — implemented exactly as specced. |
| **In-memory mock data** | Hackathon, not production. No DB layer to maintain. Demo resets cleanly on restart. |

---

## 📈 Commit history (the story arc)

```
v0.8  Marty Wave C  — Conversational chat with inline actions
v0.7  Marty Wave B  — The three surfaces (inbox, action, policy)
v0.6  Marty Wave A  — Strategy pivot per PRD + research
v0.5  Sage v0.5     — Onboarding flow + setup-scan
v0.4  Sage v0.4     — Workspace dashboard (Amazon-inspired)
v0.3  Sage v0.3     — Native Seller Center shell + price guardrails
v0.2  Sage v0.2     — Plain-English redesign for non-technical sellers
v0.1  Sage v0.1     — AI Marketplace Manager hackathon demo
docs                — Seller Center action inventory & risk classification
```

The repo evolved from a broad "AI Marketplace Manager" (Sage v0.1–0.5) to a focused, PRD-aligned **Pricing Agent inside Marty** (v0.6–0.8). Each commit tells one focused story. Walk the diffs to see the design evolve.

---

## 🚦 What's NOT in v1 (intentional)

| Not in scope | Why | When it'd come back |
|---|---|---|
| Cross-marketplace pricing (Amazon, eBay) | PRD §4 non-goal | Phase 3+ |
| New SKU pricing (auto) | No price history → high risk | Phase 3 with Element/Bedrock pricing model |
| Real LLM | Mock intent router is enough to prove the UX. Swap in Element later. | First production milestone |
| Database persistence | Demo-friendly to reset on restart | First real seller pilot |
| Action attribution model (Δ GMV vs market shifts) | PRD §11 open question | Post-MVP with synthetic control |

---

## 🐶 Built with

[Code Puppy](https://puppy.walmart.com) 🐶 — Walmart's open-source AI coding agent. Source data + design synthesis done collaboratively with [qa-kitten](https://puppy.walmart.com/marketplace) 🐱 for the gap analysis vs Amazon Seller Assistant.

---

## 📄 License

Internal Walmart hackathon project. All product names and screenshots are property of Walmart Inc.
