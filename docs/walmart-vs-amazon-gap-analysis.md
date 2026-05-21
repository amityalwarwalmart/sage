# Walmart Seller Center vs. Amazon Seller Assistant — Gap Analysis

> Built by **qa-kitten 🐱** for the Sage hackathon. Date: 2026-05-21.
>
> **Methodology note:** Live Seller Center access blocked by corp sysproxy +
> incomplete MFA login. Synthesis built from Marketplace Learn docs (via
> Google snippets), third-party seller-tool blogs (Aura, CedCommerce,
> SPCTEK, EHP, Brandwoven, Maxmerce), corporate.walmart.com announcements,
> and qa-kitten's prior full enumeration of the Seller Center IA.

## Executive Summary

Walmart's Seller Center today is largely a **reporting + manual-action tool**
with one bright spot (Success Hub's Gen-AI listing editor, Apr 2026). It has:
- **Zero** conversational AI for sellers
- **Zero** auto-drafted appeals
- **Zero** proactive forecasting alerts
- **No** unified live-tile workspace

Amazon's Seller Assistant covers 5 of 6 agentic capabilities. **Walmart covers ~1.5 of 6.**
Sage has a wide-open runway.

## Capability comparison

| # | Capability | Walmart? | Gap vs Amazon | Sage Opportunity |
|---|---|---|---|---|
| 1 | 🩺 Account Health (proactive + suggested fixes) | **Partial** | Static dashboards, no narrative, no drafted actions | HIGH — Home health card + opp-1007 |
| 2 | 📦 Demand forecasting + restock alerts | **Partial** | No native "stockout in N days", manual reorder | HIGH — opp-1009 |
| 3 | ⚖️ Compliance / appeal drafting | **No** | 100% manual writing; cottage industry of consultants exists | HIGH (HITL) — opp-1008 |
| 4 | ✨ Enhance My Listing (in-flow Gen AI) | **Partial** | Lives in Success Hub silo, not in Catalog editor | MEDIUM — Sage already covers this |
| 5 | 📰 Seller News in context | **Partial** | Broadcast only, not personalized to seller's catalog | MEDIUM — Home "What's new" widget |
| 6 | 🖼️ Unified visual workspace | **No** | Data scattered across 5+ pages; Growth Opps is just links | HIGH — `/workspace` page |

## Bonus findings

- **Sparky** = shopper-side only (walmart.com). **No seller-side conversational AI exists.**
- **Success Hub** is rule-based personalized suggestions, not conversational AI.
- **Repricer** is rules-based automation, not an agent. No narrative reasoning. Sage differentiates by *explaining* repricing decisions.
- **Walmart-unique features to lean into** (not gaps — differentiators):
  - Pro Seller badge with **transparent** thresholds (Amazon's Featured Seller is opaque)
  - Listing Quality Dashboard with explicit per-item scores
  - WFS Cross-Border + MCS for international
  - Walmart Connect (DSP + Sponsored + Brand Shop) integrated with Sales Rewards & Attribution
  - Voice of Seller feedback channel
  - Search Insights with competitive query data

## 🏆 Top 3 builds for hackathon (impact × ease)

### 🥇 #1 — `/workspace` page (6-tile live dashboard)
- **Tiles:** Health, Inventory, Compliance, Sales Velocity, Ads ROAS, Search Rank
- **Why:** Best demo screen. Walmart has *nothing* like this. 5-second value prop.
- **Effort:** ~45 min

### 🥈 #2 — opp-1008: Compliance appeals (auto-drafted, HITL)
- **What:** 3 mock items got flagged. Sage drafted appeals. Seller reviews & sends.
- **Why:** Highest seller pain-point. Strongest "agent saves my business" story. Shows Sage has *governance* (HIGH risk = HITL).
- **Effort:** ~30 min

### 🥉 #3 — opp-1007: Account Health card on Home + opportunity
- **What:** "Reply rate slipping — fix it before Friday, I drafted 8 replies."
- **Why:** Anchors Sage as **proactive**. Pulsing health ring is striking. Connects Pro Seller badge (Walmart-unique) to $ value.
- **Effort:** ~30 min

**Skip for hackathon:** opp-1009 restock (good but mock-y), inline Enhance My Listing (Walmart already has it — less differentiator).

## 🎬 Recommended demo flow (~60 seconds)

1. Open on `/workspace` → red Compliance tile catches eye
2. Click → land on opp-1008 with 3 drafted appeals
3. Show one appeal — "Sage wrote this for you"
4. "Approve & send" → return to workspace
5. Compliance tile turns green ✅
