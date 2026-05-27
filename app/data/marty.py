"""
Marty Pricing Agent — data model aligned to the PRD + deep research report.

Lives alongside the legacy mock.py module. New pricing-only surfaces read
from THIS module; the old surfaces can continue to read mock.py during the
transition.

Core concepts (per PRD §5 + research report):
- AgentMode: shadow | recommend | autopilot (rollout staging)
- ActionType: the specific PRD-blessed action (spip_unsuppress, buybox_match,
  slow_mover_markdown, pro_seller_maintain, map_violation_review, etc.)
- RiskTier: low | medium | high (low = auto, medium = bulk approve, high = always approve)
- PricingAction: a single proposed price move with full provenance
- SellerPolicy: goals + guardrails (the seller's intent the agent executes)
- Cohort: SKU bucket the seller has opted in
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

# --- Type aliases ---

AgentMode = Literal["shadow", "recommend", "autopilot"]
RiskTier = Literal["low", "medium", "high"]
ActionStatus = Literal[
    "auto_executed",   # Low-tier, agent already did it (autopilot mode only)
    "needs_approval",  # Medium or High tier, waiting for seller
    "approved",        # Seller approved, queued or executed
    "rejected",        # Seller rejected
    "dismissed",       # Seller dismissed
    "shadow_logged",   # Shadow mode: would-have-acted, didn't
    "blocked",         # Guardrail blocked it
]
ActionType = Literal[
    "spip_unsuppress",          # LOW — un-suppress an SPIP-suppressed SKU within floor
    "buybox_match",             # LOW — match competitor within floor
    "buybox_beat_by_cent",      # LOW — beat by $0.01 within floor
    "expired_promo_revert",     # LOW — revert price after promo end
    "pro_seller_maintain",      # MEDIUM — keep PCS above 75% threshold
    "margin_impact_drop",       # MEDIUM — >5% margin-impacting drop
    "slow_mover_markdown",      # MEDIUM — markdown on aged inventory
    "fee_linked_incentive",     # MEDIUM — accept reduced-referral-fee offer
    "below_cost_review",        # HIGH — agent thinks it should drop below cost
    "map_violation_review",     # HIGH — MAP/MSRP boundary
    "new_sku_pricing",          # HIGH — net-new SKU
    "hero_sku_repositioning",   # HIGH — touching a hero SKU
    "bundle_pricing",           # HIGH — bundle / strategic
    "repricer_enrollment",      # MEDIUM — enroll items in Walmart Repricer (1.28% baseline today)
]
GoalKey = Literal["protect_margin", "maximize_buybox", "liquidate_aged", "price_stability"]
CohortKey = Literal["all_enrolled", "hero_skus", "fee_linked", "inventory_risk", "price_risk", "new_skus", "repricer_not_enrolled"]

# --- Static lookups (used by templates) ---

ACTION_TYPE_META: dict[str, dict[str, str]] = {
    "spip_unsuppress":         {"label": "SPIP un-suppression",        "tier": "low",    "icon": "🔓"},
    "buybox_match":            {"label": "Buy Box match",              "tier": "low",    "icon": "🎯"},
    "buybox_beat_by_cent":     {"label": "Beat Buy Box by 1¢",         "tier": "low",    "icon": "💸"},
    "expired_promo_revert":    {"label": "Revert expired promo",       "tier": "low",    "icon": "⏪"},
    "pro_seller_maintain":     {"label": "Pro Seller maintenance",     "tier": "medium", "icon": "⭐"},
    "margin_impact_drop":      {"label": "Margin-impacting drop",      "tier": "medium", "icon": "📉"},
    "slow_mover_markdown":     {"label": "Slow-mover markdown",        "tier": "medium", "icon": "🐢"},
    "fee_linked_incentive":    {"label": "Fee-linked incentive",       "tier": "medium", "icon": "💵"},
    "below_cost_review":       {"label": "Below-cost review",          "tier": "high",   "icon": "⚠️"},
    "map_violation_review":    {"label": "MAP/MSRP review",            "tier": "high",   "icon": "🛑"},
    "new_sku_pricing":         {"label": "New SKU pricing",            "tier": "high",   "icon": "🆕"},
    "hero_sku_repositioning":  {"label": "Hero SKU repositioning",     "tier": "high",   "icon": "🏆"},
    "bundle_pricing":          {"label": "Bundle pricing",             "tier": "high",   "icon": "📦"},
    "repricer_enrollment":     {"label": "Enroll in Repricer",         "tier": "medium", "icon": "⚡"},
}

TIER_META: dict[str, dict[str, str]] = {
    "low":    {"label": "Low",    "behavior": "Auto",          "tone_class": "tier-low",    "swatch": "🟢"},
    "medium": {"label": "Medium", "behavior": "Bulk approve",  "tone_class": "tier-med",    "swatch": "🟡"},
    "high":   {"label": "High",   "behavior": "Always approve","tone_class": "tier-high",   "swatch": "🔴"},
}

MODE_META: dict[str, dict[str, str]] = {
    "shadow": {
        "label": "Shadow",
        "tagline": "Watch only — I log what I would do without changing prices.",
        "color": "bg-wmgray-160 text-white",
    },
    "recommend": {
        "label": "Recommend",
        "tagline": "I queue everything for your approval — even low-risk actions.",
        "color": "bg-spark-100 text-spark-140",
    },
    "autopilot": {
        "label": "Autopilot",
        "tagline": "I auto-execute low-risk actions within your guardrails. Medium & high still need your sign-off.",
        "color": "bg-wmblue-100 text-white",
    },
}

# --- Domain models ---

@dataclass
class Cohort:
    """A bucket of SKUs the seller has opted in (or excluded)."""
    key: CohortKey
    label: str
    description: str
    sku_count: int
    enrolled: bool = False
    excluded: bool = False  # always-ask cohorts


@dataclass
class SellerPolicy:
    """The seller's intent — what the agent is allowed to execute."""
    # Goals (multi-select, prioritized)
    goals: list[GoalKey] = field(default_factory=lambda: ["maximize_buybox", "protect_margin"])
    # Hard guardrails
    min_margin_pct: int = 15           # never below 15% margin
    max_daily_movement_pct: int = 10   # never move a single SKU >10% per day
    max_actions_per_sku_per_day: int = 3
    respect_map: bool = True           # never drop below MAP
    respect_msrp: bool = True
    promo_blackout_dates: list[str] = field(default_factory=list)  # ISO dates
    # Cohorts
    cohorts: list[Cohort] = field(default_factory=list)
    # Mode
    mode: AgentMode = "shadow"
    # Approval flags
    auto_approve_below_usd: float = 500.0
    require_approval_for_hero: bool = True
    require_approval_for_new_skus: bool = True
    setup_complete: bool = False
    setup_step: int = 1  # 1..4


@dataclass
class MarketSignal:
    """The 'what changed in the market' that triggered an action."""
    competitor_name: str  # "Best Lawn Co" or "External site"
    competitor_price: float
    your_price: float
    buybox_winner: str  # "you" | "competitor" | "no_one"
    pcs_impact_pts: float  # impact on Price Competitiveness Score
    signal_age_minutes: int


@dataclass
class GuardrailCheck:
    """One guardrail the action was checked against."""
    name: str
    result: Literal["pass", "blocked", "n/a"]
    detail: str


@dataclass
class PricingAction:
    """A single proposed (or executed) price move."""
    id: str
    sku: str
    item_name: str
    item_image_emoji: str
    action_type: ActionType
    risk_tier: RiskTier
    status: ActionStatus
    cohort: CohortKey
    # The change
    current_price: float
    proposed_price: float
    floor_price: float | None
    ceiling_price: float | None
    cost: float | None
    # Provenance
    market_signal: MarketSignal | None
    reason_oneliner: str       # "Competitor 'X' dropped to $8.47 — losing Buy Box"
    reason_detail: str         # multi-sentence narrative
    guardrails_checked: list[GuardrailCheck]
    # Outcomes
    expected_gmv_lift_usd: float
    expected_margin_delta_usd: float
    confidence: int            # 0..100
    # Provenance
    created_at: datetime
    executed_at: datetime | None = None
    reverted: bool = False
    revert_reason: str = ""

    # --- Derived properties ---

    @property
    def action_label(self) -> str:
        return ACTION_TYPE_META[self.action_type]["label"]

    @property
    def action_icon(self) -> str:
        return ACTION_TYPE_META[self.action_type]["icon"]

    @property
    def tier_meta(self) -> dict[str, str]:
        return TIER_META[self.risk_tier]

    @property
    def price_delta_usd(self) -> float:
        return self.proposed_price - self.current_price

    @property
    def price_delta_pct(self) -> float:
        if self.current_price <= 0:
            return 0.0
        return (self.proposed_price - self.current_price) / self.current_price * 100

    @property
    def margin_pct(self) -> float | None:
        if self.cost and self.proposed_price > 0:
            return (self.proposed_price - self.cost) / self.proposed_price * 100
        return None

    @property
    def age_label(self) -> str:
        delta = datetime.now() - self.created_at
        if delta < timedelta(minutes=60):
            return f"{int(delta.total_seconds() // 60)}m ago"
        if delta < timedelta(hours=24):
            return f"{int(delta.total_seconds() // 3600)}h ago"
        return f"{delta.days}d ago"

    @property
    def all_guardrails_passed(self) -> bool:
        return all(g.result != "blocked" for g in self.guardrails_checked)


@dataclass
class AgentRunStat:
    """Snapshot of the agent's performance — drives the dashboard hero KPIs."""
    actions_proposed_24h: int
    actions_auto_executed_24h: int
    actions_needing_approval: int
    actions_blocked_24h: int
    gmv_protected_usd_7d: float
    gmv_uplift_usd_7d: float
    buybox_wins_added_7d: int
    pcs_delta_7d: float
    hours_saved_estimate_7d: float
    last_check_minutes_ago: int


# --- Seeding ---

_id_counter = itertools.count(2000)

def _aid() -> str:
    return f"act-{next(_id_counter)}"


def _seed_cohorts() -> list[Cohort]:
    return [
        Cohort("all_enrolled", "All Repricer-enrolled items", "Items already enrolled in Walmart Repricer", 423, enrolled=True),
        Cohort("price_risk",    "Price-competitive risk",     "Items where you're losing Buy Box to a small price gap", 187, enrolled=True),
        Cohort("inventory_risk","Inventory-risk SKUs",        "Items >12 months old or with stockout risk", 1054, enrolled=False),
        Cohort("fee_linked",    "Fee-linked offers",          "Items with active reduced-referral-fee opportunities", 64, enrolled=False),
        Cohort("hero_skus",     "Hero SKUs",                  "Your top-revenue items — never auto-changed", 12, excluded=True),
        Cohort("new_skus",      "New SKUs (<30 days)",        "Recently launched items — pricing needs human judgment", 31, excluded=True),
        Cohort("repricer_not_enrolled", "Not in Repricer yet", "Items not yet enrolled in Walmart Repricer — currently 98.72% of your catalog", 36562, enrolled=False),
    ]


def _seed_policy() -> SellerPolicy:
    p = SellerPolicy()
    p.cohorts = _seed_cohorts()
    return p


POLICY: SellerPolicy = _seed_policy()


def _gc_pass(name: str, detail: str) -> GuardrailCheck:
    return GuardrailCheck(name=name, result="pass", detail=detail)


def _gc_block(name: str, detail: str) -> GuardrailCheck:
    return GuardrailCheck(name=name, result="blocked", detail=detail)


def _seed_actions() -> list[PricingAction]:
    """Seed ~24 pricing actions across all tiers & action types.

    Lifted directly from the screenshot SKUs to feel grounded.
    """
    now = datetime.now()
    actions: list[PricingAction] = []

    # ============================================================
    # LOW TIER — Auto-executable (or shadow-logged depending on mode)
    # ============================================================

    # SPIP un-suppression — the PRD's single highest-value MVP use case
    actions.append(PricingAction(
        id=_aid(),
        sku="MERC-WFS-1127217",
        item_name="Garnier Nutrisse Ultra Color Nourishing Hair Color",
        item_image_emoji="💇",
        action_type="spip_unsuppress",
        risk_tier="low",
        status="auto_executed",
        cohort="price_risk",
        current_price=10.00, proposed_price=9.47,
        floor_price=8.50, ceiling_price=15.00, cost=6.20,
        market_signal=MarketSignal("External site", 9.49, 10.00, "competitor", -2.3, 8),
        reason_oneliner="SPIP-suppressed for being $0.51 above external lowest price.",
        reason_detail=(
            "Garnier Nutrisse was suppressed by SPIP at 09:42 because it was priced $0.51 above the lowest "
            "external offer ($9.49). I matched within your floor of $8.50, restoring visibility. Suppressed "
            "items see ~92% drop in conversion, so each minute of suppression matters."
        ),
        guardrails_checked=[
            _gc_pass("Floor", "Floor $8.50 — proposed $9.47 is $0.97 above"),
            _gc_pass("Min margin 15%", "Margin at proposed price: 34.5%"),
            _gc_pass("Max daily movement 10%", "Move: -5.3%"),
            _gc_pass("MAP", "No MAP set"),
        ],
        expected_gmv_lift_usd=1842.0, expected_margin_delta_usd=-160.0, confidence=96,
        created_at=now - timedelta(minutes=4), executed_at=now - timedelta(minutes=3),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="FBAS-PLOTSNLBG27",
        item_name="Pilot G2 Premium Gel Roller Pen, Fine Point (12-pack)",
        item_image_emoji="🖊️",
        action_type="buybox_match",
        risk_tier="low",
        status="auto_executed",
        cohort="all_enrolled",
        current_price=10.42, proposed_price=9.98,
        floor_price=8.99, ceiling_price=14.00, cost=6.10,
        market_signal=MarketSignal("Office-Depot-Match", 9.98, 10.42, "competitor", -1.2, 12),
        reason_oneliner="Office Depot dropped to $9.98 — matched within floor.",
        reason_detail=(
            "Office Depot's offer dropped from $10.39 → $9.98 at 09:14, taking Buy Box. I matched at $9.98 "
            "(your floor is $8.99). 1,247 page views on this SKU in the past 7 days, so reclaiming the "
            "Buy Box has a high payoff."
        ),
        guardrails_checked=[
            _gc_pass("Floor", "Floor $8.99"),
            _gc_pass("Min margin 15%", "Margin: 38.9%"),
            _gc_pass("Max daily movement 10%", "Move: -4.2%"),
        ],
        expected_gmv_lift_usd=612.0, expected_margin_delta_usd=-44.0, confidence=94,
        created_at=now - timedelta(minutes=12), executed_at=now - timedelta(minutes=11),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="PEPE-M2020",
        item_name="Davidoff Cool Water Eau de Toilette for Men, 4.2 oz",
        item_image_emoji="🧴",
        action_type="buybox_beat_by_cent",
        risk_tier="low",
        status="needs_approval",  # shadow mode → goes to approval
        cohort="all_enrolled",
        current_price=35.56, proposed_price=33.23,
        floor_price=28.00, ceiling_price=45.00, cost=22.50,
        market_signal=MarketSignal("Fragrance.com", 33.24, 35.56, "competitor", -3.1, 6),
        reason_oneliner="Fragrance.com at $33.24 — beat by 1¢ to take Buy Box.",
        reason_detail=(
            "Fragrance.com is the current Buy Box winner at $33.24. Beating by $0.01 typically wins back "
            "Buy Box within 90 seconds on this SKU based on past 30-day data. You're $9.23 above your floor."
        ),
        guardrails_checked=[
            _gc_pass("Floor", "Floor $28.00"),
            _gc_pass("Min margin 15%", "Margin: 32.3%"),
            _gc_pass("Max daily movement 10%", "Move: -6.5%"),
        ],
        expected_gmv_lift_usd=1610.0, expected_margin_delta_usd=-186.0, confidence=91,
        created_at=now - timedelta(minutes=24),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="CPCS-WFS-BFMMTS",
        item_name="Burberry Brit For Men Eau de Toilette, 3.3 oz",
        item_image_emoji="🧴",
        action_type="buybox_match",
        risk_tier="low",
        status="auto_executed",
        cohort="all_enrolled",
        current_price=36.81, proposed_price=34.97,
        floor_price=30.00, ceiling_price=48.00, cost=24.00,
        market_signal=MarketSignal("Sephora-Marketplace", 34.97, 36.81, "competitor", -2.0, 18),
        reason_oneliner="Sephora at $34.97 — matched.",
        reason_detail="Matched competitor at $34.97. Within all guardrails.",
        guardrails_checked=[
            _gc_pass("Floor", "Floor $30.00"),
            _gc_pass("Min margin 15%", "Margin: 31.4%"),
        ],
        expected_gmv_lift_usd=1455.0, expected_margin_delta_usd=-130.0, confidence=93,
        created_at=now - timedelta(minutes=42), executed_at=now - timedelta(minutes=41),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="EMRY-WFS-1367853",
        item_name="Minwax Polycrylic Protective Finish, Clear Satin Quart",
        item_image_emoji="🪵",
        action_type="expired_promo_revert",
        risk_tier="low",
        status="auto_executed",
        cohort="all_enrolled",
        current_price=11.74, proposed_price=13.87,
        floor_price=10.00, ceiling_price=15.00, cost=7.20,
        market_signal=None,
        reason_oneliner="Memorial Day promo ended at midnight — reverted to base price.",
        reason_detail="Your scheduled Memorial Day promo (May 26-27) ended at 23:59. Reverted to original $13.87.",
        guardrails_checked=[
            _gc_pass("Promo schedule", "Promo expired 8h 14m ago"),
            _gc_pass("Max daily movement 10%", "Revert to pre-promo price — exempt"),
        ],
        expected_gmv_lift_usd=0, expected_margin_delta_usd=400.0, confidence=100,
        created_at=now - timedelta(hours=8), executed_at=now - timedelta(hours=8),
    ))

    # ============================================================
    # MEDIUM TIER — Bulk approve digest
    # ============================================================

    actions.append(PricingAction(
        id=_aid(),
        sku="MULTI-1",
        item_name="247 listings · Price-competitiveness cohort",
        item_image_emoji="⭐",
        action_type="pro_seller_maintain",
        risk_tier="medium",
        status="needs_approval",
        cohort="price_risk",
        current_price=0, proposed_price=0,  # bulk action
        floor_price=None, ceiling_price=None, cost=None,
        market_signal=None,
        reason_oneliner="Your PCS is 65.29% — 9.71pts below the 75% Pro Seller benchmark.",
        reason_detail=(
            "Your Price Competitiveness Score is sitting at 65.29% vs the 75% Pro Seller benchmark. "
            "Matching suggested prices on 247 high-impact items would lift PCS by an estimated 14.8 pts "
            "— pushing you well past the badge threshold. All within seller floors. Bulk approve to "
            "send to Repricer as a batch."
        ),
        guardrails_checked=[
            _gc_pass("All 247 items within floors", "0 violations"),
            _gc_pass("Daily velocity cap", "Avg -3.4% per SKU — under 10% cap"),
            _gc_pass("Hero SKU exclusion", "0 hero SKUs included"),
            _gc_pass("Min margin 15%", "All ≥ 18.2%"),
        ],
        expected_gmv_lift_usd=18400.0, expected_margin_delta_usd=-2100.0, confidence=88,
        created_at=now - timedelta(minutes=42),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="MULTI-2",
        item_name="1,054 listings · Inventory-risk cohort",
        item_image_emoji="🐢",
        action_type="slow_mover_markdown",
        risk_tier="medium",
        status="needs_approval",
        cohort="inventory_risk",
        current_price=0, proposed_price=0,
        floor_price=None, ceiling_price=None, cost=None,
        market_signal=None,
        reason_oneliner="1,054 WFS items older than 12 months — 18% markdown clears ~$157K.",
        reason_detail=(
            "1,054 items have been sitting in WFS for 12+ months and are accruing long-term storage "
            "fees. A blended 18% markdown is projected to liquidate ~$157K of GMV within 30 days. "
            "Items can be filtered/edited before bulk-approving. Recommended only for inventory_risk cohort."
        ),
        guardrails_checked=[
            _gc_pass("Min margin 15%", "Average margin after markdown: 19.7%"),
            _gc_pass("MAP", "0 MAP-protected items included"),
            _gc_pass("Hero SKU exclusion", "0 hero SKUs included"),
        ],
        expected_gmv_lift_usd=157000.0, expected_margin_delta_usd=22400.0, confidence=82,
        created_at=now - timedelta(hours=2),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="MULTI-3",
        item_name="64 listings · Fee-linked offers",
        item_image_emoji="💵",
        action_type="fee_linked_incentive",
        risk_tier="medium",
        status="needs_approval",
        cohort="fee_linked",
        current_price=0, proposed_price=0,
        floor_price=None, ceiling_price=None, cost=None,
        market_signal=None,
        reason_oneliner="Walmart is offering 50% off referral fees on 64 of your items if you drop price ≤5%.",
        reason_detail=(
            "Walmart Marketplace is running a fee-linked incentive: 50% reduction on referral fees for 30 days "
            "if you cut price ≤5% on eligible items. 64 of your SKUs qualify. Net margin impact after fee "
            "reduction is +$8,200 over 30 days. Requires opting in per-item."
        ),
        guardrails_checked=[
            _gc_pass("Min margin 15%", "All items remain ≥ 16.8%"),
            _gc_pass("Max daily movement 10%", "All drops ≤5%"),
            _gc_pass("Fee-linked cohort opt-in", "⚠️ Cohort currently NOT enrolled — approval will enroll"),
        ],
        expected_gmv_lift_usd=12300.0, expected_margin_delta_usd=8200.0, confidence=85,
        created_at=now - timedelta(hours=4),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="MERC-WFS-1698826",
        item_name="Mederma Advanced Scar Gel, 1.76 oz",
        item_image_emoji="🩹",
        action_type="margin_impact_drop",
        risk_tier="medium",
        status="needs_approval",
        cohort="all_enrolled",
        current_price=37.98, proposed_price=33.50,
        floor_price=30.00, ceiling_price=45.00, cost=22.00,
        market_signal=MarketSignal("Amazon-3P", 33.49, 37.98, "competitor", -2.8, 22),
        reason_oneliner="Competitor at $33.49 — match needs an 11.8% drop (above 10% velocity cap).",
        reason_detail=(
            "Amazon 3P dropped to $33.49 — winning Buy Box. Matching would require an 11.8% drop, just "
            "above your 10% daily velocity cap. I'm queuing for approval since this exceeds the auto-action "
            "threshold by 1.8 pts. Margin remains healthy (34.3%)."
        ),
        guardrails_checked=[
            _gc_pass("Floor", "Floor $30.00"),
            _gc_pass("Min margin 15%", "Margin: 34.3%"),
            _gc_block("Max daily movement 10%", "Move would be -11.8% — exceeds cap by 1.8pts. Needs override."),
        ],
        expected_gmv_lift_usd=2940.0, expected_margin_delta_usd=-340.0, confidence=84,
        created_at=now - timedelta(minutes=55),
    ))

    # ============================================================
    # HIGH TIER — Always approve
    # ============================================================

    actions.append(PricingAction(
        id=_aid(),
        sku="PETR-FDC16806250",
        item_name="Fuji 16806250 Instax Mini 11 Camera, Lilac Purple",
        item_image_emoji="📷",
        action_type="hero_sku_repositioning",
        risk_tier="high",
        status="needs_approval",
        cohort="hero_skus",
        current_price=134.76, proposed_price=109.00,
        floor_price=95.00, ceiling_price=145.00, cost=78.00,
        market_signal=MarketSignal("Amazon", 109.99, 134.76, "competitor", -6.4, 3),
        reason_oneliner="Hero SKU. Amazon at $109.99 — needs your sign-off before I touch this.",
        reason_detail=(
            "Fuji Instax Mini 11 is one of your 12 hero SKUs (>$50K monthly GMV). Amazon is "
            "consistently $25 below you and has been winning Buy Box for 11 of the last 14 days. "
            "Matching at $109 would reclaim ~80% Buy Box share but represents a 19.1% drop. "
            "Hero SKU changes always require your approval per your policy."
        ),
        guardrails_checked=[
            _gc_pass("Floor", "Floor $95.00"),
            _gc_pass("Min margin 15%", "Margin: 28.4%"),
            _gc_block("Hero SKU rule", "Always-ask cohort"),
            _gc_block("Max daily movement 10%", "Move: -19.1% — exceeds cap"),
        ],
        expected_gmv_lift_usd=12450.0, expected_margin_delta_usd=-2100.0, confidence=78,
        created_at=now - timedelta(hours=3),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="MATL-WFS-C4982",
        item_name="Hot Wheels 1:64 Scale Premium Collector Set",
        item_image_emoji="🚗",
        action_type="map_violation_review",
        risk_tier="high",
        status="needs_approval",
        cohort="all_enrolled",
        current_price=6.31, proposed_price=5.49,
        floor_price=5.00, ceiling_price=10.00, cost=3.20,
        market_signal=MarketSignal("Target-Marketplace", 5.49, 6.31, "competitor", -1.4, 9),
        reason_oneliner="Target at $5.49 — but MAP is $5.99. I won't act without your call.",
        reason_detail=(
            "Target.com is undercutting at $5.49, but the manufacturer MAP is $5.99. Matching would "
            "violate MAP and likely trigger a brand warning. I can either (a) match at $5.99 (the MAP "
            "floor — won't take Buy Box), (b) flag the MAP violation to the brand, or (c) do nothing. "
            "Recommend option (b)."
        ),
        guardrails_checked=[
            _gc_pass("Floor", "Floor $5.00"),
            _gc_pass("Min margin 15%", "Margin: 41.7%"),
            _gc_block("MAP", "MAP is $5.99 — proposed $5.49 violates MAP"),
        ],
        expected_gmv_lift_usd=720.0, expected_margin_delta_usd=-90.0, confidence=72,
        created_at=now - timedelta(hours=6),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="NEW-SKU-088",
        item_name="Acme Pro Series Cordless Drill (just launched)",
        item_image_emoji="🔧",
        action_type="new_sku_pricing",
        risk_tier="high",
        status="needs_approval",
        cohort="new_skus",
        current_price=89.99, proposed_price=79.99,
        floor_price=None, ceiling_price=None, cost=52.00,
        market_signal=MarketSignal("3 similar listings", 82.50, 89.99, "no_one", 0.0, 60),
        reason_oneliner="No price history. I won't auto-price net-new SKUs.",
        reason_detail=(
            "This SKU launched 11 days ago. No conversion history, no Buy Box telemetry. I see 3 similar "
            "competitor listings averaging $82.50. My best guess is $79.99 to undercut and build velocity, "
            "but new-SKU pricing is high-risk — always your call."
        ),
        guardrails_checked=[
            _gc_pass("Min margin 15%", "Margin: 35.0%"),
            _gc_block("New SKU rule", "Always-ask cohort"),
        ],
        expected_gmv_lift_usd=0, expected_margin_delta_usd=0, confidence=55,
        created_at=now - timedelta(hours=18),
    ))

    actions.append(PricingAction(
        id=_aid(),
        sku="FBAS-MERCFBA55143",
        item_name="Dr. Brown's Natural Flow Anti-Colic Bottles, 8 oz, 3-pack",
        item_image_emoji="🍼",
        action_type="below_cost_review",
        risk_tier="high",
        status="blocked",
        cohort="all_enrolled",
        current_price=10.00, proposed_price=6.99,
        floor_price=7.50, ceiling_price=14.00, cost=7.20,
        market_signal=MarketSignal("Buy-Buy-Baby", 6.99, 10.00, "competitor", -4.2, 14),
        reason_oneliner="Match would require $6.99 — below your $7.20 cost AND $7.50 floor.",
        reason_detail=(
            "Buy Buy Baby is at $6.99. Matching would push you below cost ($7.20) AND below your floor "
            "($7.50). I refused to take the action. Recommend either raising your floor to accept Buy Box "
            "loss, or escalating to brand."
        ),
        guardrails_checked=[
            _gc_block("Floor", "Floor $7.50 — proposed $6.99 violates floor by $0.51"),
            _gc_block("Cost", "Cost $7.20 — proposed $6.99 is BELOW cost"),
        ],
        expected_gmv_lift_usd=0, expected_margin_delta_usd=0, confidence=98,
        created_at=now - timedelta(hours=5),
    ))

    # A few more dismissed/historical actions for the dismissed tab
    actions.append(PricingAction(
        id=_aid(),
        sku="HISTORICAL-1",
        item_name="Real Techniques Everyday Eye Brushes, 8-piece Set",
        item_image_emoji="💄",
        action_type="buybox_match",
        risk_tier="low",
        status="rejected",
        cohort="all_enrolled",
        current_price=17.47, proposed_price=16.50,
        floor_price=14.00, ceiling_price=22.00, cost=10.50,
        market_signal=MarketSignal("Ulta", 16.50, 17.47, "competitor", -1.1, 30),
        reason_oneliner="Seller dismissed: 'Holding price ahead of supplier increase'",
        reason_detail="Action proposed at 09:33 yesterday — dismissed by you at 09:51 with note: 'Holding price ahead of supplier increase'.",
        guardrails_checked=[_gc_pass("Floor", "Floor $14.00")],
        expected_gmv_lift_usd=0, expected_margin_delta_usd=0, confidence=92,
        created_at=now - timedelta(days=1, hours=2),
    ))

    # ============================================================
    # MEDIUM TIER — The headline opportunity: only 1.28% of catalog
    # is enrolled in Walmart Repricer today. Marty surfaces a bulk
    # enrollment action covering the highest-traffic + most-competitive
    # unenrolled SKUs as the #1 action a seller can take.
    # ============================================================
    actions.append(PricingAction(
        id=_aid(),
        sku="BULK-REPRICER-TOP-1200",
        item_name="Enroll your top 1,200 unenrolled SKUs in Walmart Repricer",
        item_image_emoji="⚡",
        action_type="repricer_enrollment",
        risk_tier="medium",
        status="needs_approval",
        cohort="repricer_not_enrolled",
        current_price=0.0, proposed_price=0.0,
        floor_price=None, ceiling_price=None, cost=None,
        market_signal=None,
        reason_oneliner="Only 1.28% of your 36,985-SKU catalog is enrolled in Repricer. These 1,200 are the highest-leverage.",
        reason_detail=(
            "98.72% of your catalog (36,562 items) is NOT enrolled in Walmart Repricer. Enrolled items see "
            "+70.35% PCS and +15.88% Buy Box rate vs unenrolled. I've ranked the top 1,200 unenrolled SKUs "
            "by (page views × PCS gap to competitor) and pre-configured Repricer floors at cost + 18% margin "
            "using your default policy. You can review the floor on any individual SKU before approving. "
            "This is the single highest-leverage action available in your account today."
        ),
        guardrails_checked=[
            _gc_pass("Floor per SKU", "Pre-set to cost + 18% margin (above your 15% minimum)"),
            _gc_pass("Hero SKU exclusion", "12 hero SKUs excluded from bulk enrollment"),
            _gc_pass("New SKU exclusion", "31 SKUs <30 days old excluded — they need human pricing first"),
            _gc_pass("MAP", "Repricer respects MAP/MSRP from your existing item setup"),
            _gc_pass("Reversible", "You can un-enroll any SKU in 1 click; rollback also available bulk"),
        ],
        expected_gmv_lift_usd=86_400.0, expected_margin_delta_usd=-3_200.0, confidence=88,
        created_at=now - timedelta(minutes=2),
    ))

    return actions


ACTIONS: list[PricingAction] = _seed_actions()


# --- Audit log (every state change Marty makes or seller takes) ---

@dataclass
class AuditEvent:
    id: str
    ts: datetime
    actor: Literal["marty", "seller"]
    verb: str        # "executed", "approved", "rejected", "rolled_back", "blocked", "shadow_logged"
    action_id: str
    summary: str
    note: str = ""


def _seed_audit() -> list[AuditEvent]:
    now = datetime.now()
    log: list[AuditEvent] = []
    for a in ACTIONS:
        if a.status == "auto_executed":
            log.append(AuditEvent(_aid(), a.executed_at or a.created_at, "marty", "executed",
                                  a.id, f"Auto-executed {a.action_label} on {a.item_name} — {a.reason_oneliner}"))
        elif a.status == "blocked":
            log.append(AuditEvent(_aid(), a.created_at, "marty", "blocked",
                                  a.id, f"Blocked by guardrail on {a.item_name} — {a.reason_oneliner}"))
        elif a.status == "rejected":
            log.append(AuditEvent(_aid(), a.created_at + timedelta(minutes=18), "seller", "rejected",
                                  a.id, f"Seller rejected {a.action_label} on {a.item_name}",
                                  note=a.revert_reason or ""))
    return sorted(log, key=lambda e: e.ts, reverse=True)


AUDIT: list[AuditEvent] = _seed_audit()


# ============================================================
# Repricing rules — the seller-authored "WHEN x THEN y" layer.
# A gap Walmart doesn't have natively today: catalog-level rules
# that auto-fire scoped actions within the seller's policy.
# Each rule is risk-tiered (low/med/high) based on its action,
# obeys ALL policy guardrails + cohort exclusions, and produces
# new PricingActions that flow through the same approval pipeline.
# ============================================================

RuleStatus = Literal["active", "paused", "draft", "shadow"]
RuleTriggerKind = Literal[
    "no_sales_for_days",          # "if no units sold for 365d"
    "buybox_lost_for_hours",      # "if Buy Box lost for 24h"
    "price_gap_above_pct",        # "if competitor is >5% lower"
    "inventory_aging_days",       # "if item is >180 days in inventory"
    "pcs_below_pct",              # "if SKU PCS drops below 70%"
    "high_margin_and_no_buybox",  # "if margin >X% AND not winning BB"
    "new_sku_after_days",         # "30 days after launch"
]
RuleActionKind = Literal[
    "create_clearance_promo",     # create N% off promo
    "buybox_match",               # match competitor within floor
    "buybox_beat_by_cent",        # beat by $0.01
    "drop_price_pct",             # drop price by N%
    "pause_listing",              # pause SKU
    "enroll_in_repricer",         # add to Walmart Repricer
    "apply_fee_incentive",        # opt into reduced-fee offer
    "alert_only",                 # surface in inbox, take no action
]

TRIGGER_META: dict[str, dict[str, str]] = {
    "no_sales_for_days":         {"label": "hasn't sold in",          "unit": "days",    "icon": "💭"},
    "buybox_lost_for_hours":     {"label": "has lost Buy Box for",    "unit": "hours",   "icon": "🎯"},
    "price_gap_above_pct":       {"label": "is priced above competitor by", "unit": "%",  "icon": "💰"},
    "inventory_aging_days":      {"label": "has been in inventory for", "unit": "days",   "icon": "📦"},
    "pcs_below_pct":             {"label": "has PCS below",            "unit": "%",      "icon": "📉"},
    "high_margin_and_no_buybox": {"label": "margin is above",          "unit": "% and no Buy Box", "icon": "💵"},
    "new_sku_after_days":        {"label": "is",                       "unit": "days old", "icon": "🆕"},
}

ACTION_KIND_META: dict[str, dict[str, str]] = {
    "create_clearance_promo":  {"label": "create a clearance promo at",   "unit": "% off",  "icon": "🏷️", "tier": "medium"},
    "buybox_match":            {"label": "match the Buy Box price (within floor)", "unit": "",       "icon": "🎯", "tier": "low"},
    "buybox_beat_by_cent":     {"label": "beat the Buy Box price by $0.01", "unit": "",            "icon": "💸", "tier": "low"},
    "drop_price_pct":          {"label": "drop the price by",            "unit": "%",      "icon": "📉", "tier": "medium"},
    "pause_listing":           {"label": "pause the listing",            "unit": "",       "icon": "⏸️", "tier": "high"},
    "enroll_in_repricer":      {"label": "enroll in Walmart Repricer",   "unit": "",       "icon": "⚡", "tier": "medium"},
    "apply_fee_incentive":     {"label": "apply the reduced-fee incentive", "unit": "",   "icon": "💵", "tier": "medium"},
    "alert_only":              {"label": "surface in my inbox for review", "unit": "",     "icon": "📬", "tier": "low"},
}


@dataclass
class RepricingRule:
    id: str
    name: str                         # "Move aged inventory with 20% clearance"
    description: str                  # short human-readable summary
    status: RuleStatus = "active"
    # Trigger
    trigger_kind: RuleTriggerKind = "no_sales_for_days"
    trigger_value: float = 365.0
    # Filter (scopes WHICH cohort the rule applies to)
    cohort: CohortKey = "all_enrolled"
    brand_filter: str = ""            # "Garnier", "Intex", or "" for all
    category_filter: str = ""
    # Action
    action_kind: RuleActionKind = "create_clearance_promo"
    action_value: float = 20.0        # the magnitude (% off, $ delta, etc.)
    # Exclusions (always-respected)
    exclude_hero_skus: bool = True
    exclude_new_skus: bool = True
    exclude_during_blackouts: bool = True
    exclude_below_cost: bool = True
    exclude_brands: list[str] = field(default_factory=list)
    exclude_skus: list[str] = field(default_factory=list)
    # Risk tier (derived from action_kind by default)
    risk_tier: RiskTier = "medium"
    # Author + audit
    created_by: Literal["seller", "marty_suggested"] = "seller"
    created_at: datetime = field(default_factory=datetime.now)
    last_fired_at: datetime | None = None
    # Stats (computed in the demo — in prod these would be live counters)
    affected_skus_today: int = 0
    actions_fired_7d: int = 0
    gmv_impact_7d_usd: float = 0.0
    units_moved_7d: int = 0

    @property
    def trigger_sentence(self) -> str:
        t = TRIGGER_META[self.trigger_kind]
        val = int(self.trigger_value) if self.trigger_value == int(self.trigger_value) else self.trigger_value
        return f"an item {t['label']} {val} {t['unit']}"

    @property
    def action_sentence(self) -> str:
        a = ACTION_KIND_META[self.action_kind]
        val = ""
        if a["unit"]:
            num = int(self.action_value) if self.action_value == int(self.action_value) else self.action_value
            val = f" {num}{a['unit']}" if a['unit'] in ("%", "% off") else f" {num} {a['unit']}"
        return f"{a['label']}{val}"

    @property
    def scope_sentence(self) -> str:
        parts = []
        if self.cohort and self.cohort != "all_enrolled":
            cohort_label = next((c.label for c in POLICY.cohorts if c.key == self.cohort), self.cohort)
            parts.append(f"in the {cohort_label}")
        if self.brand_filter:
            parts.append(f"from brand {self.brand_filter}")
        if self.category_filter:
            parts.append(f"in {self.category_filter}")
        return " ".join(parts) if parts else "across your catalog"

    @property
    def exclusion_summary(self) -> str:
        parts = []
        if self.exclude_hero_skus: parts.append("hero SKUs")
        if self.exclude_new_skus: parts.append("new SKUs <30d")
        if self.exclude_during_blackouts: parts.append("blackout windows")
        if self.exclude_below_cost: parts.append("anything below cost")
        if self.exclude_brands: parts.append(f"brands: {', '.join(self.exclude_brands)}")
        if self.exclude_skus: parts.append(f"{len(self.exclude_skus)} specific SKUs")
        return " · ".join(parts)

    @property
    def plain_english(self) -> str:
        return f"When {self.trigger_sentence} {self.scope_sentence}, {self.action_sentence}."

    @property
    def last_fired_label(self) -> str:
        if not self.last_fired_at:
            return "never"
        delta = datetime.now() - self.last_fired_at
        if delta < timedelta(minutes=60):
            return f"{int(delta.total_seconds() // 60)}m ago"
        if delta < timedelta(hours=24):
            return f"{int(delta.total_seconds() // 3600)}h ago"
        return f"{delta.days}d ago"

    @property
    def tier_meta(self) -> dict[str, str]:
        return TIER_META[self.risk_tier]

    @property
    def status_class(self) -> str:
        return {
            "active":  "bg-wmgreen-10 text-wmgreen-130",
            "paused":  "bg-wmgray-10 text-wmgray-130",
            "draft":   "bg-spark-10 text-spark-140",
            "shadow":  "bg-marty-10 text-marty-130",
        }[self.status]


def _seed_rules() -> list[RepricingRule]:
    now = datetime.now()
    rules: list[RepricingRule] = [
        # ============ Rule 1: the user\'s example ============
        RepricingRule(
            id="rule-101",
            name="Move 12-month aged inventory with clearance promo",
            description="The classic dead-stock clearance — fire a 20%-off clearance promo on anything that hasn't sold in a year.",
            status="active",
            trigger_kind="no_sales_for_days", trigger_value=365.0,
            cohort="inventory_risk",
            action_kind="create_clearance_promo", action_value=20.0,
            risk_tier="medium",
            last_fired_at=now - timedelta(hours=3),
            affected_skus_today=14, actions_fired_7d=87,
            gmv_impact_7d_usd=4_280.0, units_moved_7d=210,
        ),
        # ============ Rule 2: Buy Box recovery ============
        RepricingRule(
            id="rule-102",
            name="Recover Buy Box on price-competitive cohort",
            description="If we've lost Buy Box for 24h on a SKU in the price-competitive cohort, match the competitor price (within floor).",
            status="active",
            trigger_kind="buybox_lost_for_hours", trigger_value=24.0,
            cohort="price_risk",
            action_kind="buybox_match", action_value=0,
            risk_tier="low",
            last_fired_at=now - timedelta(minutes=11),
            affected_skus_today=42, actions_fired_7d=296,
            gmv_impact_7d_usd=18_640.0, units_moved_7d=812,
        ),
        # ============ Rule 3: PCS drop alert ============
        RepricingRule(
            id="rule-103",
            name="Alert me if Pro Seller status is at risk",
            description="If my catalog-level PCS drops below the 75% Pro Seller benchmark, surface it as a high-priority action.",
            status="active",
            trigger_kind="pcs_below_pct", trigger_value=75.0,
            cohort="all_enrolled",
            action_kind="alert_only", action_value=0,
            risk_tier="low",
            last_fired_at=now - timedelta(hours=8),
            affected_skus_today=1, actions_fired_7d=3,
            gmv_impact_7d_usd=0.0, units_moved_7d=0,
        ),
        # ============ Rule 4: High-margin Buy Box recovery ============
        RepricingRule(
            id="rule-104",
            name="Beat-by-1¢ on high-margin items losing Buy Box",
            description="On items with >35% margin where we've lost Buy Box, beat the competitor by $0.01 — plenty of room left in the margin.",
            status="shadow",
            trigger_kind="high_margin_and_no_buybox", trigger_value=35.0,
            cohort="all_enrolled",
            action_kind="buybox_beat_by_cent", action_value=0,
            risk_tier="low",
            exclude_brands=["Burberry", "Davidoff"],  # luxury brands where buybox-chasing is bad
            last_fired_at=now - timedelta(hours=17),
            affected_skus_today=23, actions_fired_7d=141,
            gmv_impact_7d_usd=9_120.0, units_moved_7d=297,
        ),
        # ============ Rule 5: New SKU → enroll in Repricer ============
        RepricingRule(
            id="rule-105",
            name="Auto-enroll new SKUs in Repricer after 30 days",
            description="Give new SKUs 30 days of manual pricing, then auto-enroll them in Repricer so they don't fall behind.",
            status="paused",  # user paused while reviewing
            trigger_kind="new_sku_after_days", trigger_value=30.0,
            cohort="new_skus",
            action_kind="enroll_in_repricer", action_value=0,
            risk_tier="medium",
            last_fired_at=now - timedelta(days=4),
            affected_skus_today=0, actions_fired_7d=12,
            gmv_impact_7d_usd=2_410.0, units_moved_7d=58,
        ),
    ]
    return rules


RULES: list[RepricingRule] = _seed_rules()


# ---- Rule helpers ----

RULE_TEMPLATES: list[dict] = [
    {
        "name": "Move aged inventory (12mo) with 20% clearance",
        "trigger_kind": "no_sales_for_days", "trigger_value": 365,
        "action_kind": "create_clearance_promo", "action_value": 20,
        "cohort": "inventory_risk", "risk_tier": "medium",
        "icon": "🐢", "why": "Classic dead-stock cleanup. WFS storage fees kick in hard after 12 months — better to take a margin hit and recover capital.",
    },
    {
        "name": "Recover Buy Box on price-risk cohort",
        "trigger_kind": "buybox_lost_for_hours", "trigger_value": 24,
        "action_kind": "buybox_match", "action_value": 0,
        "cohort": "price_risk", "risk_tier": "low",
        "icon": "🎯", "why": "24h lost Buy Box on a price-sensitive SKU is signal, not noise. Auto-match within your floor.",
    },
    {
        "name": "Alert on Pro Seller PCS drop",
        "trigger_kind": "pcs_below_pct", "trigger_value": 75,
        "action_kind": "alert_only", "action_value": 0,
        "cohort": "all_enrolled", "risk_tier": "low",
        "icon": "📉", "why": "Pro Seller eligibility is tied to PCS. A drop below 75% is a leading indicator — you want to know.",
    },
    {
        "name": "Beat-by-1¢ on high-margin items losing Buy Box",
        "trigger_kind": "high_margin_and_no_buybox", "trigger_value": 35,
        "action_kind": "buybox_beat_by_cent", "action_value": 0,
        "cohort": "all_enrolled", "risk_tier": "low",
        "icon": "💵", "why": "If you've got >35% margin, you've got room to fight for Buy Box — and the extra units make it net-positive.",
    },
    {
        "name": "Enroll new SKUs in Repricer after 30 days",
        "trigger_kind": "new_sku_after_days", "trigger_value": 30,
        "action_kind": "enroll_in_repricer", "action_value": 0,
        "cohort": "new_skus", "risk_tier": "medium",
        "icon": "🆕", "why": "Give new SKUs a month of manual pricing to establish a baseline, then automate.",
    },
    {
        "name": "Pause listings out of stock for >7 days",
        "trigger_kind": "no_sales_for_days", "trigger_value": 7,
        "action_kind": "pause_listing", "action_value": 0,
        "cohort": "all_enrolled", "risk_tier": "high",
        "icon": "⏸️", "why": "Active out-of-stock listings hurt your Buy Box win rate across the catalog. Pausing them protects PCS.",
    },
]


def rule_by_id(rid: str) -> RepricingRule | None:
    return next((r for r in RULES if r.id == rid), None)


def toggle_rule_status(rid: str) -> bool:
    r = rule_by_id(rid)
    if not r:
        return False
    if r.status == "active":
        r.status = "paused"
    elif r.status in ("paused", "shadow", "draft"):
        r.status = "active"
    return True


def delete_rule(rid: str) -> bool:
    global RULES
    before = len(RULES)
    RULES = [r for r in RULES if r.id != rid]
    return len(RULES) < before


def add_rule(rule: RepricingRule) -> None:
    RULES.append(rule)


# ---- Suggested rules — Marty notices patterns in audit history ----

@dataclass
class SuggestedRule:
    name: str
    rationale: str               # "You approved 7 similar markdowns in 14 days"
    icon: str
    confidence: int              # 0-100
    template_index: int          # index into RULE_TEMPLATES
    affected_skus_estimate: int


def suggested_rules() -> list[SuggestedRule]:
    """In production these would be ML-detected. For the demo, hand-crafted."""
    return [
        SuggestedRule(
            name="Aged-inventory clearance pattern detected",
            rationale="You\'ve approved 7 slow-mover markdowns in the last 14 days — all from the inventory-risk cohort.",
            icon="🐢", confidence=92, template_index=0,
            affected_skus_estimate=1054,
        ),
        SuggestedRule(
            name="Pro Seller PCS guardrail",
            rationale="Your PCS sits 9.56 points below the Pro Seller benchmark — an alert rule would catch dips before they cost you the badge.",
            icon="📉", confidence=86, template_index=2,
            affected_skus_estimate=0,
        ),
        SuggestedRule(
            name="Beat-by-1¢ on high-margin items",
            rationale="23 of your high-margin SKUs lost Buy Box in the past week. A standing rule recovers them automatically.",
            icon="💵", confidence=78, template_index=3,
            affected_skus_estimate=23,
        ),
    ]



# --- KPI helpers ---

def run_stats() -> AgentRunStat:
    actions_24h = [a for a in ACTIONS if a.created_at > datetime.now() - timedelta(hours=24)]
    return AgentRunStat(
        actions_proposed_24h=len(actions_24h),
        actions_auto_executed_24h=sum(1 for a in actions_24h if a.status == "auto_executed"),
        actions_needing_approval=sum(1 for a in ACTIONS if a.status == "needs_approval"),
        actions_blocked_24h=sum(1 for a in actions_24h if a.status == "blocked"),
        gmv_protected_usd_7d=18420.0,
        gmv_uplift_usd_7d=42180.0,
        buybox_wins_added_7d=287,
        pcs_delta_7d=2.76,
        hours_saved_estimate_7d=14.5,
        last_check_minutes_ago=2,
    )


# --- Walmart-wide telemetry (matches updated Pricing Insights screenshot) ---
# Values mirror screenshot SCR-20260527-jgcf.png so the demo lines up with reality.
MARKETPLACE_TELEMETRY = {
    "buybox_win_rate_pct":      5.62,
    "buybox_win_rate_delta_pct": -0.07,
    "pcs_pct":                  65.44,
    "pcs_delta_pct":            1.93,
    "pcs_pro_seller_benchmark": 75.0,
    "pcs_gap_to_pro_seller":    9.56,
    "repricer_enrolled_pct":    1.28,
    "repricer_not_enrolled_pct":98.72,
    "repricer_enrolled_pcs":    70.35,
    "repricer_enrolled_buybox_rate": 15.88,
    "unpublished_items_count":  378,
    "unpublished_gmv_loss_usd": 475_000,
    "aging_items_count":        1055,
    "aging_gmv_opportunity_usd":153_000,
    "small_price_gap_items_count": 1834,
    "small_price_gap_gmv_usd":  17_000,
    "catalog_total_items":      36985,
}


# --- Community queries (real Smart Filters telemetry, Apr 27 → May 27 2026) ---
# Sourced from Smart filters_Insights_2026-04-27_to_2026-05-27.csv
# Used to (a) seed the "Sellers like you are asking…" overview panel and
# (b) inform intent routing in marty_chat.py.
@dataclass
class CommunityQuery:
    rank: int
    query: str
    count: int
    intent: str       # which Marty intent it maps to
    icon: str
    translated: str = ""   # English translation if non-English
    lang: str = "en"       # ISO-639-1


COMMUNITY_QUERIES: list[CommunityQuery] = [
    CommunityQuery(1, "Losing the Buy Box", 53, "losing_buybox", "🎯",
                   lang="en"),
    CommunityQuery(2, "流量高但销售额低的产品", 9, "high_traffic_low_sales", "📈",
                   translated="Products with high traffic but low sales", lang="zh"),
    CommunityQuery(3, "Items with aged inventory that are losing the Buy Box", 6, "aged_and_losing_buybox", "🐢",
                   lang="en"),
    CommunityQuery(4, "长期库存滞销且正在失去 Buy Box 的商品", 3, "aged_and_losing_buybox", "🐢",
                   translated="Aged inventory items that are losing the Buy Box", lang="zh"),
    CommunityQuery(5, "Products with high traffic and low sales", 3, "high_traffic_low_sales", "📈",
                   lang="en"),
    CommunityQuery(6, "price not competitive", 2, "not_competitive", "💰",
                   lang="en"),
    CommunityQuery(7, "Reason for Buy Box ineligibility", 2, "buybox_ineligibility", "❓",
                   lang="en"),
    CommunityQuery(8, "kar elde etme oranı yüksek olanlar", 1, "high_margin", "💵",
                   translated="Products with high profit margin", lang="tr"),
    CommunityQuery(9, "products that are WFS AND have no buybox", 1, "wfs_no_buybox", "📦",
                   lang="en"),
    CommunityQuery(10, "products with high traffic and close to competitive price but not having buybox", 1, "close_but_no_buybox", "🎯",
                   lang="en"),
]

# Quick lookups
QUERY_INTENT_PHRASES: dict[str, list[str]] = {
    "losing_buybox":           ["losing the buy box", "losing buy box", "lost buy box", "lose the buy box", "失去buybox", "失去 buy box"],
    "high_traffic_low_sales":  ["high traffic and low sales", "high traffic low sales", "traffic high", "low conversion", "流量高但销售", "high view low sale"],
    "aged_and_losing_buybox":  ["aged inventory", "aged and losing", "aging", "old inventory", "长期库存", "库存滞销"],
    "not_competitive":         ["not competitive", "price not competitive", "价格没有竞争力", "uncompetitive"],
    "buybox_ineligibility":    ["ineligible", "ineligibility", "reason for buy box", "why no buy box", "why can't i win"],
    "high_margin":             ["high margin", "high profit", "kar elde etme", "高利润"],
    "wfs_no_buybox":           ["wfs and have no buybox", "wfs no buybox", "wfs without buybox"],
    "close_but_no_buybox":     ["close to competitive", "close but not having buybox", "close to competitor"],
    "repricer_enroll":         ["enroll in repricer", "repricer enrollment", "add to repricer", "start using repricer", "why repricer", "about repricer"],
}


def actions_by_status(status: ActionStatus) -> list[PricingAction]:
    return sorted(
        [a for a in ACTIONS if a.status == status],
        key=lambda a: a.created_at,
        reverse=True,
    )


def actions_by_tier(tier: RiskTier) -> list[PricingAction]:
    return [a for a in ACTIONS if a.risk_tier == tier]


def action_by_id(aid: str) -> PricingAction | None:
    return next((a for a in ACTIONS if a.id == aid), None)


def set_mode(mode: AgentMode) -> None:
    POLICY.mode = mode
    # If we go back to shadow, any already-auto-executed stays executed (history),
    # but the running banner should reflect new mode immediately.


def approve_action(aid: str, note: str = "") -> bool:
    a = action_by_id(aid)
    if not a or a.status not in ("needs_approval",):
        return False
    a.status = "approved"
    a.executed_at = datetime.now()
    AUDIT.insert(0, AuditEvent(_aid(), datetime.now(), "seller", "approved", a.id,
                               f"Approved {a.action_label} on {a.item_name}", note=note))
    return True


def reject_action(aid: str, note: str = "") -> bool:
    a = action_by_id(aid)
    if not a or a.status not in ("needs_approval",):
        return False
    a.status = "rejected"
    a.revert_reason = note
    AUDIT.insert(0, AuditEvent(_aid(), datetime.now(), "seller", "rejected", a.id,
                               f"Rejected {a.action_label} on {a.item_name}", note=note))
    return True


def rollback_action(aid: str, note: str = "") -> bool:
    a = action_by_id(aid)
    if not a:
        return False
    a.reverted = True
    a.revert_reason = note or "Seller rolled back"
    AUDIT.insert(0, AuditEvent(_aid(), datetime.now(), "seller", "rolled_back", a.id,
                               f"Rolled back {a.action_label} on {a.item_name}", note=note))
    return True


def bulk_approve(action_ids: list[str]) -> int:
    count = 0
    for aid in action_ids:
        if approve_action(aid):
            count += 1
    return count


def bulk_reject(action_ids: list[str], note: str = "") -> int:
    count = 0
    for aid in action_ids:
        if reject_action(aid, note=note):
            count += 1
    return count
