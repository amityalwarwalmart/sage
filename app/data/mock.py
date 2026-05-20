"""
Mock data for Sage — the AI Marketplace Manager.

All in-memory so the demo is reset-friendly. Seeded with SKUs lifted from
real Seller Center screenshots so it feels grounded.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Literal

Category = Literal["catalog", "pricing", "incentives", "seo"]
RiskTier = Literal["low", "medium", "high"]
OppStatus = Literal["new", "reviewing", "approved", "rejected", "executed", "deferred"]


# ---------- Opportunity & related models ----------

@dataclass
class ProposedChange:
    sku: str
    item_name: str
    field: str
    current: str
    proposed: str
    sku_impact_usd: float
    image_emoji: str = "📦"
    excluded: bool = False


@dataclass
class ToolCall:
    name: str
    args: str
    result: str
    duration_ms: int


@dataclass
class Opportunity:
    id: str
    title: str
    summary: str
    category: Category
    risk_tier: RiskTier
    confidence: int  # 0–100
    gmv_impact_usd: float
    sku_count: int
    status: OppStatus
    created_at: datetime
    reasoning: str
    evidence: list[str]
    proposed_changes: list[ProposedChange] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    requires_approval: bool = True

    @property
    def category_label(self) -> str:
        return {
            "catalog": "Catalog",
            "pricing": "Pricing",
            "incentives": "Incentives",
            "seo": "SEO",
        }[self.category]

    @property
    def risk_label(self) -> str:
        return self.risk_tier.capitalize()

    @property
    def age(self) -> str:
        delta = datetime.now() - self.created_at
        if delta < timedelta(minutes=60):
            return f"{int(delta.total_seconds() // 60)}m ago"
        if delta < timedelta(hours=24):
            return f"{int(delta.total_seconds() // 3600)}h ago"
        return f"{delta.days}d ago"


@dataclass
class AuditEntry:
    id: str
    ts: datetime
    actor: str  # "sage" | "user"
    action: str
    target: str
    detail: str
    gmv_impact_usd: float
    reverted: bool = False


@dataclass
class Settings:
    auto_approve_enabled: bool = True
    auto_approve_max_usd: float = 500.0
    auto_approve_min_confidence: int = 85
    daily_action_cap: int = 1000
    paused_capabilities: list[Category] = field(default_factory=list)
    require_approval_for_clearance: bool = True
    require_approval_for_ad_spend: bool = True
    require_approval_for_bulk_content: bool = True


# ---------- The store ----------

_counter = itertools.count(1000)


def _id(prefix: str) -> str:
    return f"{prefix}-{next(_counter)}"


def _seed_opportunities() -> list[Opportunity]:
    now = datetime.now()
    opps: list[Opportunity] = []

    # ---- PRICING: Buy Box small price cuts ----
    pricing_changes = [
        ProposedChange("MERC-WFS-1127217", "Garnier Nutrisse Ultra Color Nourishing Hair Color",
                       "Price", "$10.00", "$8.47", 1842.0, "💇"),
        ProposedChange("PEPE-M2020", "Davidoff Cool Water Eau de Toilette for Men, 4.2 oz",
                       "Price", "$35.56", "$33.24", 1610.0, "🧴"),
        ProposedChange("FBAS-MERCFBA55143", "Dr. Brown's Natural Flow Anti-Colic Bottles",
                       "Price", "$10.00", "$9.98", 980.0, "🍼"),
        ProposedChange("CPCS-WFS-BFMMTS", "Burberry For Men, Brit Eau de Toilette",
                       "Price", "$36.81", "$34.97", 1455.0, "🧴"),
        ProposedChange("FBAS-PLOTSNLBG27", "Pilot G2 Premium Gel Roller Pen, Fine Point",
                       "Price", "$10.42", "$2.98", 612.0, "🖊️"),
        ProposedChange("EMRY-WFS-1367853", "Minwax Polycrylic Protective Finish, Clear Satin",
                       "Price", "$13.87", "$11.74", 723.0, "🪵"),
    ]
    opps.append(Opportunity(
        id=_id("opp"),
        title="Match Buy Box on 6 high-traffic SKUs",
        summary="Small price cuts on items with Very High traffic could capture Buy Box for an estimated +$7,222 in 30-day GMV.",
        category="pricing",
        risk_tier="low",
        confidence=92,
        gmv_impact_usd=7222.0,
        sku_count=6,
        status="new",
        created_at=now - timedelta(minutes=8),
        reasoning="Scanned 32,121 catalog items. Filtered to SKUs with traffic=Very High, BuyBox win-rate <5%, and current price within 8% of suggested. Cross-checked competitor delta from Walmart price intelligence feed. Projected GMV using 30-day historical conversion rate per SKU.",
        evidence=[
            "Buy Box win rate: 5.39% (down 0.56% in 30 days)",
            "Price Competitiveness Score: 65.29% (9.71% below Pro Seller benchmark)",
            "Repricer covers only 1.32% of catalog — 98.68% of items unprotected",
            "Matching suggested prices on these 6 items lifts PCS by +14.8 points",
        ],
        proposed_changes=pricing_changes,
        tool_calls=[
            ToolCall("scan_catalog_pricing", "filter=very_high_traffic,buybox<5%", "Returned 184 candidates", 412),
            ToolCall("get_competitive_prices", "skus=184", "Got competitor prices for 178/184", 1340),
            ToolCall("rank_by_gmv_impact", "horizon=30d", "Ranked; top 6 = $7.2K opp", 88),
        ],
    ))

    # ---- PRICING: Clearance for aging inventory ----
    aging_changes = [
        ProposedChange("PETR-FDC16806250", "Fujifilm Instax Mini 12 Instant Camera, Lilac Purple",
                       "Price", "$134.76", "$89.00", 4120.0, "📷"),
        ProposedChange("COMO-COSEPGR486G", "48\" Freestanding Double Oven Gas Range, 6 Sealed Burners",
                       "Price", "$2,499.00", "$1,899.00", 18750.0, "🔥"),
        ProposedChange("CPCS-WFS-JCWES33", "Jimmy Choo Ladies I Want Choo Eau de Parfum, 100ml",
                       "Price", "$165.00", "$119.00", 7340.0, "🧴"),
        ProposedChange("MRRY-PTH1330010010", "Zoovilla Free-Range X-Large Mobile Chicken Coop",
                       "Price", "$589.00", "$429.00", 7225.0, "🐔"),
    ]
    opps.append(Opportunity(
        id=_id("opp"),
        title="Run clearance promotion on 1,054 aging WFS items",
        summary="Items >12 months in storage are bleeding storage fees. Clearance pricing + Aged Inventory promo could recover $157K in 30-day GMV.",
        category="pricing",
        risk_tier="high",
        confidence=78,
        gmv_impact_usd=157000.0,
        sku_count=1054,
        status="new",
        created_at=now - timedelta(minutes=22),
        reasoning="Cross-referenced WFS Inventory Age report (7,208 units >365 days = 28% of stock) with Sales Velocity. Identified 1,054 SKUs with zero sales in 60 days AND aged status. Applied category-aware discount curves (-25% to -45%) derived from past clearance ROI.",
        evidence=[
            "7,208 units stored >365 days (defined as 'aged')",
            "Estimated 30-day GMV opportunity: $157K",
            "Average storage fee bleed: $4.20/unit/month on aged stock",
            "Past clearance campaigns sold-through 68% of enrolled SKUs in 21 days",
        ],
        proposed_changes=aging_changes,
        tool_calls=[
            ToolCall("get_wfs_inventory_age", "bucket=365+", "7,208 units across 1,892 SKUs", 580),
            ToolCall("get_sales_velocity", "window=60d", "1,054 SKUs zero-sale", 920),
            ToolCall("calculate_clearance_curve", "category_aware=true", "Curves applied per category", 145),
        ],
        requires_approval=True,
    ))

    # ---- CATALOG: Listing quality fixes ----
    catalog_changes = [
        ProposedChange("DRUM-LPA653", "LPA653, Aspire Slide Mount Double Conga Stand",
                       "Description + 3 attrs", "Short, missing material/dimensions",
                       "Full description + material=Steel, height=42in, weight=18lbs", 320.0, "🥁"),
        ProposedChange("THUN-AX48PROSILVER", "Ultimate Support APEX AX-48 Pro Two-Tier Keyboard Stand",
                       "Title + 4 attrs", "Generic title, missing key specs",
                       "SEO-optimized title + weight capacity, materials, dimensions", 410.0, "🎹"),
        ProposedChange("FEKT-RT2035", "Cocktail Shaker",
                       "Title + Description", "Title=\"Cocktail Shaker\" (2 words)",
                       "\"Stainless Steel Cocktail Shaker, 24oz, 3-Piece Bartender Set\" + full desc", 280.0, "🍸"),
        ProposedChange("FBAS-LIPRFBA1143", "Lipper International 1143 Acacia Straight-Side Serving Bowl",
                       "5 missing attrs", "No dimensions, capacity, material care",
                       "Diameter=10in, capacity=64oz, hand-wash, finished w/ mineral oil", 195.0, "🥗"),
        ProposedChange("DESI-TOS2", "Salad Spoons",
                       "Title + Description", "Title=\"Salad Spoons\"",
                       "\"Premium Acacia Wood Salad Servers Set, 12\" Hand-Carved Spoon & Fork\"", 175.0, "🥄"),
    ]
    opps.append(Opportunity(
        id=_id("opp"),
        title="Fix Listing Quality on 247 'Poor' items with high page views",
        summary="247 items rated Poor are getting >50 page views/week but converting at <0.5%. Content rewrites + missing attributes could lift conversion 3–5x.",
        category="catalog",
        risk_tier="medium",
        confidence=87,
        gmv_impact_usd=44818.0,
        sku_count=247,
        status="new",
        created_at=now - timedelta(minutes=35),
        reasoning="Filtered 138,830 'Poor' items by page_views > 50/week. Identified 247 with conversion <0.5% AND quality score <50%. Generated content using GenAI optimized for Walmart search ranking signals.",
        evidence=[
            "Overall listing quality: 41% (Poor)",
            "138,830 items rated Poor = $44.8K weekly GMV at risk",
            "Content quality score: 84.33% overall, but skews bad on long-tail",
            "Pro Seller threshold: Content Quality ≥75% — currently 83.84%",
        ],
        proposed_changes=catalog_changes,
        tool_calls=[
            ToolCall("scan_listing_quality", "rating=poor", "Found 138,830 items", 1820),
            ToolCall("filter_high_value", "page_views>50,conv<0.5%", "247 high-value targets", 340),
            ToolCall("generate_content_batch", "model=walmart-genai-v3", "Drafted 247 rewrites", 14200),
        ],
    ))

    # ---- SEO ----
    seo_changes = [
        ProposedChange("SPTA-SD9263SSB", "Sunpentown 18 in. Portable Dishwasher with Energy Star",
                       "Title + Description",
                       "Sunpentown 18 in. Portable Dishwasher with Energy Star",
                       "Sunpentown 18\" Standard Portable Countertop Dishwasher — Energy Star, 6 Wash Cycles, Stainless Steel",
                       890.0, "🍽️"),
        ProposedChange("MERC-WFS-18976", "Nature's Blend Protein Tablets, 200 Count",
                       "Title + Description",
                       "Nature's Blend Protein Tablets, 200 Count",
                       "Nature's Blend Chewable Soy Protein Tablets, 200 Count — Honey Flavor, Vegetarian, Daily Supplement",
                       640.0, "💊"),
        ProposedChange("GOBO-XWEGK1BLK", "Baja X 1000W Electric Kids Go-Kart Black",
                       "Title",
                       "Baja X 1000W Electric Kids Go-Kart Black",
                       "Gobowen Baja X 48V 1000W Electric Kids Go-Kart, Black — Brushless Motor, Ages 8+",
                       1240.0, "🏎️"),
        ProposedChange("USSC-AW40", "Ashley Hearth Products AW40 2,000 Sq. Ft. EPA Certified Wood Stove",
                       "Title",
                       "Ashley Hearth Products AW40 2,000 Sq. Ft. EPA Certified Wood Stove",
                       "Ashley Furniture Wood Burning Circulator AW40 — 93,000 BTU, Heats 2,000 sq ft, EPA Certified",
                       1580.0, "🔥"),
        ProposedChange("DIGI-MTTRK500", "MotoTec 500 Watt 48V 3 Wheel Electric Trike Mobility Scooter",
                       "Description",
                       "Generic description",
                       "Full SEO desc: range, weight capacity, charge time, safety features",
                       720.0, "🛵"),
    ]
    opps.append(Opportunity(
        id=_id("opp"),
        title="Apply Gen AI SEO rewrites to 33 top-traffic items",
        summary="Gen AI–optimized titles & descriptions for your 33 highest-traffic items. Walmart sellers using SEO suggestions see avg 15% sales lift.",
        category="seo",
        risk_tier="low",
        confidence=91,
        gmv_impact_usd=18400.0,
        sku_count=33,
        status="new",
        created_at=now - timedelta(hours=1, minutes=12),
        reasoning="Ranked top-performing items by 30-day page views. For each, queried trending keywords (internal + Google), competitor titles, and applied Walmart GenAI rewrite model. Suggested copy preserves brand voice, adds rank-eligible keywords, fixes title length.",
        evidence=[
            "Walmart sellers using SEO suggestions see avg 15% sales lift (first-party data)",
            "Estimated total increase in sales: +15%",
            "Top 33 items account for 12% of total weekly page views",
        ],
        proposed_changes=seo_changes,
        tool_calls=[
            ToolCall("get_top_traffic_items", "limit=33", "33 SKUs returned", 220),
            ToolCall("trending_keywords", "source=google+internal", "Keywords harvested", 980),
            ToolCall("genai_rewrite_seo", "model=walmart-genai-v3", "33 rewrites drafted", 9800),
        ],
    ))

    # ---- INCENTIVES: claim ad credits ----
    opps.append(Opportunity(
        id=_id("opp"),
        title="Claim $1,250 in unused ad credits, deploy to 8 top items",
        summary="You have $1,250 in unclaimed Walmart Connect ad credits expiring in 14 days. Sage can claim + allocate across 8 Customer Favorite SKUs.",
        category="incentives",
        risk_tier="medium",
        confidence=95,
        gmv_impact_usd=8750.0,
        sku_count=8,
        status="new",
        created_at=now - timedelta(hours=2, minutes=5),
        reasoning="Detected $1,250 unclaimed Sponsored Search credits expiring Jun 3. Identified 8 Customer Favorite SKUs with high search demand but low ad coverage. Suggested allocation prioritizes ROAS based on historical campaign data.",
        evidence=[
            "$1,250 ad credit balance, expires Jun 3, 2026",
            "Historical Sponsored Search ROAS: 7.0x for this seller",
            "8 Customer Favorites currently have zero Sponsored coverage",
        ],
        proposed_changes=[
            ProposedChange("MERC-WFS-213470", "Care Emery Boards, 20 Count", "Daily ad budget",
                           "$0.00", "$15.00 (14 days)", 1470.0, "💅"),
            ProposedChange("CDIS-BC125AT", "Uniden BC125AT Handheld Scanner", "Daily ad budget",
                           "$0.00", "$25.00 (14 days)", 1825.0, "📻"),
            ProposedChange("ACHI-MSG225WH06", "Achim Morningstar Cordless Vinyl Blind, 25\" x 64\"",
                           "Daily ad budget", "$0.00", "$20.00 (14 days)", 1240.0, "🪟"),
            ProposedChange("PERF-W3982", "Cologne Spray by Coty for Women, 1.7 oz", "Daily ad budget",
                           "$0.00", "$10.00 (14 days)", 920.0, "🧴"),
            ProposedChange("CANA-WINTMIN1866070", "Minnkota PowerDrive Black Trolling Motor",
                           "Daily ad budget", "$0.00", "$15.00 (14 days)", 1180.0, "🛥️"),
        ],
        tool_calls=[
            ToolCall("get_ad_credit_balance", "", "$1,250 expiring 2026-06-03", 80),
            ToolCall("identify_high_demand_skus", "filter=customer_favorite,sponsored=0", "8 SKUs", 410),
            ToolCall("allocate_budget", "optimize=roas", "Allocation drafted", 230),
        ],
    ))

    # ---- INCENTIVES: enroll Flash Deals ----
    opps.append(Opportunity(
        id=_id("opp"),
        title="Enroll 4 SKUs in upcoming Memorial Day Flash Deal",
        summary="Memorial Day Flash Deal window opens May 24. 4 of your high-stock SKUs are eligible — projected +$5,400 GMV at 18% promo discount.",
        category="incentives",
        risk_tier="medium",
        confidence=82,
        gmv_impact_usd=5400.0,
        sku_count=4,
        status="new",
        created_at=now - timedelta(hours=3, minutes=40),
        reasoning="Walmart event calendar shows Memorial Day Flash Deal May 24–27. Filtered catalog to eligible SKUs with sufficient inventory (>50 units), Pro Seller-tier listings, and high seasonal relevance (BBQ, outdoor, grilling).",
        evidence=[
            "Memorial Day Flash Deal window: May 24–27, 2026",
            "4 SKUs eligible: outdoor/grill category, inventory >50",
            "Past Flash Deal events: avg 3.2x sales lift during window",
        ],
        proposed_changes=[
            ProposedChange("MATL-WFS-C4982", "Hot Wheels 1:64 Scale Die-Cast Vehicle Assortment",
                           "Flash Deal price", "$6.31", "$4.99 (May 24–27)", 1180.0, "🚗"),
            ProposedChange("MATL-WFS-HTN77", "Hot Wheels City Downtown Ice Cream Swirl Playset",
                           "Flash Deal price", "$24.99", "$19.99 (May 24–27)", 1620.0, "🍦"),
        ],
        tool_calls=[
            ToolCall("get_promo_calendar", "window=14d", "Memorial Day Flash Deal", 120),
            ToolCall("filter_eligible_skus", "event=memorial_day", "4 eligible", 380),
        ],
    ))

    # ---- CATALOG: low-confidence, low-impact — auto-eligible ----
    opps.append(Opportunity(
        id=_id("opp"),
        title="Auto-fix 19 SKUs missing required attributes",
        summary="19 SKUs are missing 1–2 required attributes inferable from existing data. Low risk, low impact — auto-approve eligible.",
        category="catalog",
        risk_tier="low",
        confidence=98,
        gmv_impact_usd=320.0,
        sku_count=19,
        status="new",
        created_at=now - timedelta(hours=4, minutes=15),
        reasoning="Found 19 SKUs missing 'color', 'material', or 'weight' attributes that can be reliably extracted from product images and titles. High-confidence single-field fixes.",
        evidence=[
            "19 SKUs missing 1–2 required attributes",
            "All inferable from existing title/image with >95% confidence",
            "Below auto-approve threshold of $500 — eligible to run unattended",
        ],
        proposed_changes=[
            ProposedChange("AUTO-EX-1", "[19 SKUs - bulk attribute fill]", "Missing attributes",
                           "1–2 missing per SKU", "Inferred from title/image", 320.0, "🤖"),
        ],
        tool_calls=[
            ToolCall("scan_missing_attrs", "required_only=true", "19 SKUs", 240),
        ],
        requires_approval=False,
    ))

    return opps


def _seed_audit() -> list[AuditEntry]:
    now = datetime.now()
    return [
        AuditEntry(_id("a"), now - timedelta(hours=1), "sage",
                   "Updated price", "MERC-WFS-1698826 (Mederma Advanced Scar Gel)",
                   "$37.98 → $37.50 (Repricer)", 142.0),
        AuditEntry(_id("a"), now - timedelta(hours=2), "sage",
                   "Auto-fixed attributes", "12 SKUs (missing color/material)",
                   "Auto-fill from images, 12/12 succeeded", 240.0),
        AuditEntry(_id("a"), now - timedelta(hours=4), "user",
                   "Approved SEO batch", "8 high-traffic SKUs",
                   "Gen AI titles + descriptions applied", 2840.0),
        AuditEntry(_id("a"), now - timedelta(hours=6), "sage",
                   "Claimed ad credit", "Walmart Connect — $480",
                   "Auto-claimed expiring credit", 480.0),
        AuditEntry(_id("a"), now - timedelta(hours=8), "user",
                   "Approved repricer enrollment", "47 SKUs",
                   "Enrolled in Walmart Repricer with floor=cost+15%", 4120.0),
        AuditEntry(_id("a"), now - timedelta(days=1, hours=2), "sage",
                   "Updated price", "FEKT-M196 (MXR A/B BOX)",
                   "$89.99 → $84.99 (Buy Box match)", 218.0),
        AuditEntry(_id("a"), now - timedelta(days=1, hours=5), "user",
                   "Rejected clearance proposal", "1,054 aging WFS items",
                   "User opted to wait one more week before clearance", 0.0),
        AuditEntry(_id("a"), now - timedelta(days=2), "sage",
                   "Enrolled in promo", "Mother's Day Flash Deal — 6 SKUs",
                   "Auto-enrolled per user pre-approval", 3240.0),
        AuditEntry(_id("a"), now - timedelta(days=3), "sage",
                   "Applied SEO content", "22 SKUs (bulk Gen AI)",
                   "User pre-approved batch", 1840.0),
    ]


# ---------- Module-level singleton state ----------

OPPORTUNITIES: dict[str, Opportunity] = {o.id: o for o in _seed_opportunities()}
AUDIT_LOG: list[AuditEntry] = _seed_audit()
SETTINGS: Settings = Settings()


# ---------- KPI helpers (computed live so they react to state changes) ----------

def kpi_summary() -> dict:
    open_opps = [o for o in OPPORTUNITIES.values() if o.status == "new"]
    approved_24h = [a for a in AUDIT_LOG
                    if a.actor == "sage" and a.ts > datetime.now() - timedelta(hours=24)]
    saved_7d = sum(a.gmv_impact_usd for a in AUDIT_LOG
                   if a.ts > datetime.now() - timedelta(days=7) and not a.reverted)
    pending_value = sum(o.gmv_impact_usd for o in open_opps)
    return {
        "open_opps": len(open_opps),
        "pending_value": pending_value,
        "actions_24h": len(approved_24h),
        "saved_7d": saved_7d,
    }


def opps_by_category() -> dict[Category, list[Opportunity]]:
    buckets: dict[Category, list[Opportunity]] = {"catalog": [], "pricing": [], "incentives": [], "seo": []}
    for o in OPPORTUNITIES.values():
        if o.status == "new":
            buckets[o.category].append(o)
    return buckets


def append_audit(actor: str, action: str, target: str, detail: str, gmv: float) -> AuditEntry:
    entry = AuditEntry(_id("a"), datetime.now(), actor, action, target, detail, gmv)
    AUDIT_LOG.insert(0, entry)
    return entry
