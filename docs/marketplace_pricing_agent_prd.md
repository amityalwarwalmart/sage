# Marketplace Pricing Agent (within Marty)

**Owner:** Pricing Product Lead, Seller Center | **Audience:** Pricing PM + Eng | **Status:** Draft PRD

---

## 1. Problem
Marketplace sellers lose Buy Box, get SPIP-suppressed, and miss Pro Seller competitiveness because effective pricing reactions require speed and competitive data they can't match manually. Static recommendations see **~80% drop-off** in the US. The existing Seller Center Repricer is configure-once, rule-based, and has no closed loop (no scheduling, profit calc, or outcome analytics). Sellers need delegation, not more dashboards.

## 2. Hypothesis
Sellers will delegate pricing decisions when (a) cost of inaction is high, (b) the optimal action is data-derivable, and (c) guardrails bound the worst case. The real drivers are **speed and asymmetric information**, not tedium. SMBs want delegation; sophisticated sellers want approval workflows + transparency. The Pricing Agent ships **as a capability inside Marty** (not a standalone shingle) and orchestrates the existing Repricer + Price Guidance surfaces.

## 3. Goals & Success Metrics
- SPIP-driven suppression time: **hours → <15 min** for opted-in SKUs
- **+X% Buy Box win rate** for agent-managed SKUs vs holdout control (target set post-shadow)
- **50% reduction** in Pro Seller badge churn driven by price competitiveness
- **60%+ adoption** among sellers with >100 SKUs within 12 months
- **NPS ≥ 60** among active users; **<2%** rollback/dispute rate on auto-actions

## 4. Non-Goals
- New agent shingle (lives inside Marty)
- Replacing the Repricer (we orchestrate it)
- Algorithmic pricing for net-new SKUs (no price history → high risk)
- Cross-marketplace pricing (Amazon, eBay)

## 5. Risk-Tiered Action Model (core IP)

| Tier | Examples | Default Behavior |
|---|---|---|
| Low (Auto) | SPIP un-suppression, match competitor within floor, beat-by-1¢ for Buy Box, revert expired promo | Auto-execute, notify after |
| Medium (Bulk Approve) | Pro Seller badge competitiveness across many SKUs, >5% margin-impacting drops, slow-mover markdowns | Collated daily digest with 1-click bulk approve/reject |
| High (Always Approve) | Below-cost, MAP violations, new SKU pricing, strategic repositioning, bundle pricing | Agent recommends only; seller approves |

## 6. Seller Trust & Guardrails (non-negotiable)
- Per-SKU and per-category **floor / ceiling / min-margin**
- **Velocity caps** (max N changes / SKU / day)
- **Shadow mode** (simulate 2 weeks, show counterfactual)
- Full **audit log** + plain-English reasoning trace per action
- **One-click rollback** (single action or batch)
- **Global kill switch** + per-tier kill switch
- **Opt-in by SKU bucket**; default OFF
- Outcome reporting: Δ GMV, Δ margin, Δ Buy Box win rate vs counterfactual

## 7. MVP Scope (90 days)
1. **SPIP auto-un-suppression** (Low tier) — single highest-value use case
2. **Buy Box match/beat within seller floor** (Low tier)
3. **Bulk approval digest** in Marty chat for Medium-tier actions
4. **Shadow mode, audit log, rollback**
5. **Native Marty integration** — e.g., chat: *"Show me what the agent did today"*

## 8. Phase 2 (6 months)
Pro Seller badge maintenance · promo lifecycle automation · slow-mover markdowns · Partner API for custom agent rules.

## 9. Edge Cases
- Competitor price flicker → velocity cap + dampening window
- Cost data missing/stale → block Low-tier auto; route to High tier
- Floor breach attempt → reject, log, surface in digest
- Repricer conflict (existing rule contradicts agent action) → agent defers, flags
- WFS vs SFS shipping cost deltas → tier-specific margin calc (see Open Qs)

## 10. Dependencies & Assumptions
- Seller Center Repricer API (write path), SPIP signal feed, Price Guidance data, Buy Box telemetry, Marty chat surface + tool-calling runtime, Element LLM gateway
- Assumes Marty's orchestration layer supports tiered approval UX and durable action queues

## 11. Open Questions
- [Eng] Share Merlinor's orchestration backbone or fork US-side?
- [Analytics] Attribution methodology — Δ GMV vs underlying market shifts (synthetic control? holdout?)
- [Ops] WFS vs SFS — different shipping-cost risk profiles for margin calc?
- [Eng/Finance] LLM choice + cost per active seller / month at scale?

## 12. Competitive Wedge
Amazon Automate = rules only. Feedvisor = paid 3P add-on. Shopify Sidekick = advice only. Alibaba AABA = limited action. Walmart wins by shipping **native, free, tiered-autonomy** pricing inside Marty with the strictest guardrails in the market — **trust as the moat**.
