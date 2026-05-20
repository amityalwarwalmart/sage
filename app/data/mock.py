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
    title: str  # friendly headline
    summary: str  # plain-english one-liner
    category: Category
    risk_tier: RiskTier
    confidence: int  # 0–100 (hidden from UI, used only for ranking & confidence_label)
    gmv_impact_usd: float
    sku_count: int
    status: OppStatus
    created_at: datetime
    reasoning: str  # tucked under "Why I'm suggesting this"
    evidence: list[str]
    proposed_changes: list[ProposedChange] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    requires_approval: bool = True
    horizon_label: str = "in the next month"  # human-friendly time-frame for the $ impact
    one_liner_why: str = ""  # super-short "because X" for cards

    @property
    def category_label(self) -> str:
        return {
            "catalog": "Product listings",
            "pricing": "Pricing",
            "incentives": "Ads & promos",
            "seo": "Search visibility",
        }[self.category]

    @property
    def category_emoji(self) -> str:
        return {"catalog": "📝", "pricing": "💰", "incentives": "🎉", "seo": "🔍"}[self.category]

    @property
    def risk_label(self) -> str:
        return {
            "low": "Quick win",
            "medium": "Worth a look",
            "high": "Bigger change",
        }[self.risk_tier]

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 90:
            return "Highly recommended"
        if self.confidence >= 80:
            return "Worth trying"
        return "Something to consider"

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
        title="Drop prices on 6 popular items so they show up as the top offer",
        summary="These 6 items get lots of shoppers, but a competitor is winning the sale right now. Small price cuts could earn you about $7,200 more next month.",
        one_liner_why="A competitor is just a few cents cheaper on these.",
        category="pricing",
        risk_tier="low",
        confidence=92,
        gmv_impact_usd=7222.0,
        sku_count=6,
        status="new",
        created_at=now - timedelta(minutes=8),
        reasoning="I looked at all 32,121 of your items and found the ones that get the most shoppers but aren’t winning the sale because another seller has a slightly lower price. For each one, I checked what your competitors charge and figured out the smallest price drop that would let you win the top spot on the page.",
        evidence=[
            "Right now, shoppers pick your offer only about 5 times out of 100",
            "You're $2–$8 above the lowest competitor on these items",
            "Most of your items aren't using Walmart's auto-pricing tool yet",
            "Matching these prices would make your store much more competitive",
        ],
        proposed_changes=pricing_changes,
        tool_calls=[
            ToolCall("scan_catalog_pricing", "filter=very_high_traffic,buybox<5%", "Returned 184 candidates", 412),
            ToolCall("get_competitive_prices", "skus=184", "Got competitor pric 178/184", 1340),
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
        title="Run a sale on 1,054 items that have been sitting in the warehouse over a year",
        summary="These items haven’t sold in a long time and Walmart is charging you storage fees every month. A clearance sale could turn them into $157,000 of cash back in your pocket next month.",
        one_liner_why="You're paying storage fees on items that aren't selling.",
        category="pricing",
        risk_tier="high",
        confidence=78,
        gmv_impact_usd=157000.0,
        sku_count=1054,
        status="new",
        created_at=now - timedelta(minutes=22),
        reasoning="I checked which of your warehouse items have been sitting there for more than a year without selling. There are 7,208 units like this — you're paying about $4.20 a month per unit in storage fees, which adds up. I picked discount amounts based on what's worked for your past clearance sales (usually 25–45% off, depending on category).",
        evidence=[
            "7,208 units have been sitting in storage for over a year",
            "Estimated cash you could recover: $157,000 next month",
            "You're paying about $4.20 a month per unit just to store these",
            "Last time you ran a clearance, you sold 68% of the items in 3 weeks",
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
                       "Product description & details",
                       "Short description, no size or material info",
                       "Full description plus: made of steel, 42\" tall, weighs 18 lbs", 320.0, "🥁"),
        ProposedChange("THUN-AX48PROSILVER", "Ultimate Support APEX AX-48 Pro Two-Tier Keyboard Stand",
                       "Product title & details",
                       "Generic title, missing important details",
                       "Better title that shoppers actually search for, plus weight capacity and dimensions", 410.0, "🎹"),
        ProposedChange("FEKT-RT2035", "Cocktail Shaker",
                       "Product title & description",
                       "Title is just “Cocktail Shaker” — too vague",
                       "“Stainless Steel Cocktail Shaker, 24oz, 3-Piece Bartender Set” + full description", 280.0, "🍸"),
        ProposedChange("FBAS-LIPRFBA1143", "Lipper International 1143 Acacia Straight-Side Serving Bowl",
                       "Product details",
                       "Missing size, capacity, and care instructions",
                       "10\" wide, holds 64oz, hand-wash, treated with mineral oil", 195.0, "🥗"),
        ProposedChange("DESI-TOS2", "Salad Spoons",
                       "Product title & description",
                       "Title is just “Salad Spoons”",
                       "“Premium Acacia Wood Salad Servers Set — 12\" Hand-Carved Spoon & Fork”", 175.0, "🥄"),
    ]
    opps.append(Opportunity(
        id=_id("opp"),
        title="Fix the product pages on 247 items that shoppers visit but don't buy",
        summary="These 247 items show up in search and people look at them, but they leave without buying. Better photos, titles, and descriptions could turn 3–5 times more lookers into buyers — about $44,800 more next month.",
        one_liner_why="Your listings are missing details shoppers want to see.",
        category="catalog",
        risk_tier="medium",
        confidence=87,
        gmv_impact_usd=44818.0,
        sku_count=247,
        status="new",
        created_at=now - timedelta(minutes=35),
        reasoning="I looked at all your items rated ‘Poor’ by Walmart and found 247 of them that are actually getting traffic — 50+ visitors a week each — but converting less than half a percent. That means lots of people are looking but bouncing. I drafted improved titles and descriptions for each one, focused on the details that make shoppers click ‘Buy’.",
        evidence=[
            "Walmart rates 41% of your listings as ‘Poor’ overall",
            "These 247 items are losing about $44,800 in sales per week",
            "Most of them are missing key details like dimensions, materials, or care instructions",
            "Pro Sellers usually have at least 75% of listings rated ‘Good’ or better",
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
                       "Product title & description",
                       "Sunpentown 18 in. Portable Dishwasher with Energy Star",
                       "Sunpentown 18\" Standard Portable Countertop Dishwasher — Energy Star, 6 Wash Cycles, Stainless Steel",
                       890.0, "🍽️"),
        ProposedChange("MERC-WFS-18976", "Nature's Blend Protein Tablets, 200 Count",
                       "Product title & description",
                       "Nature's Blend Protein Tablets, 200 Count",
                       "Nature's Blend Chewable Soy Protein Tablets, 200 Count — Honey Flavor, Vegetarian, Daily Supplement",
                       640.0, "💊"),
        ProposedChange("GOBO-XWEGK1BLK", "Baja X 1000W Electric Kids Go-Kart Black",
                       "Product title",
                       "Baja X 1000W Electric Kids Go-Kart Black",
                       "Gobowen Baja X 48V 1000W Electric Kids Go-Kart, Black — Brushless Motor, Ages 8+",
                       1240.0, "🏎️"),
        ProposedChange("USSC-AW40", "Ashley Hearth Products AW40 2,000 Sq. Ft. EPA Certified Wood Stove",
                       "Product title",
                       "Ashley Hearth Products AW40 2,000 Sq. Ft. EPA Certified Wood Stove",
                       "Ashley Furniture Wood Burning Circulator AW40 — 93,000 BTU, Heats 2,000 sq ft, EPA Certified",
                       1580.0, "🔥"),
        ProposedChange("DIGI-MTTRK500", "MotoTec 500 Watt 48V 3 Wheel Electric Trike Mobility Scooter",
                       "Product description",
                       "Generic description",
                       "Full description with range, weight capacity, charging time, and safety features",
                       720.0, "🛵"),
    ]
    opps.append(Opportunity(
        id=_id("opp"),
        title="Help shoppers find your 33 best-selling items more easily",
        summary="I rewrote the titles and descriptions of your top 33 items using words shoppers actually search for. Sellers who use these suggestions see about 15% more sales on average.",
        one_liner_why="Your titles don't include the words shoppers type in.",
        category="seo",
        risk_tier="low",
        confidence=91,
        gmv_impact_usd=18400.0,
        sku_count=33,
        status="new",
        created_at=now - timedelta(hours=1, minutes=12),
        reasoning="I took your 33 most-visited items and looked up what words shoppers type when searching for things like them — both on Walmart and Google. Then I rewrote each title and description to include those words naturally, while keeping your brand voice and product details intact.",
        evidence=[
            "Walmart sellers who use these suggestions average 15% more sales",
            "These 33 items already drive 12% of all your weekly traffic",
            "Small wording changes typically improve search ranking within days",
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
        title="Claim $1,250 in free ad money before it expires in 14 days",
        summary="Walmart gave you $1,250 in free advertising credit and you haven’t used it yet. It expires June 3. I can claim it and spread it across 8 of your most-loved items — likely worth about $8,750 in extra sales.",
        one_liner_why="Free money is about to disappear.",
        category="incentives",
        risk_tier="medium",
        confidence=95,
        gmv_impact_usd=8750.0,
        sku_count=8,
        status="new",
        created_at=now - timedelta(hours=2, minutes=5),
        reasoning="I noticed you have $1,250 in Walmart advertising credit just sitting there, set to expire on June 3rd. I picked 8 of your Customer Favorites (items shoppers love) that aren’t being advertised yet, and figured out how much budget to put on each one based on what's worked for you in the past.",
        evidence=[
            "$1,250 in ad credit expires June 3, 2026",
            "Every $1 you've spent on Walmart ads has earned you about $7 back",
            "8 of your most-loved items have no ads running on them right now",
        ],
        proposed_changes=[
            ProposedChange("MERC-WFS-213470", "Care Emery Boards, 20 Count", "Daily ad budget",
                           "$0 (no ads)", "$15/day for 14 days", 1470.0, "💅"),
            ProposedChange("CDIS-BC125AT", "Uniden BC125AT Handheld Scanner", "Daily ad budget",
                           "$0 (no ads)", "$25/day for 14 days", 1825.0, "📻"),
            ProposedChange("ACHI-MSG225WH06", "Achim Morningstar Cordless Vinyl Blind, 25\" x 64\"",
                           "Daily ad budget", "$0 (no ads)", "$20/day for 14 days", 1240.0, "🪟"),
            ProposedChange("PERF-W3982", "Cologne Spray by Coty for Women, 1.7 oz", "Daily ad budget",
                           "$0 (no ads)", "$10/day for 14 days", 920.0, "🧴"),
            ProposedChange("CANA-WINTMIN1866070", "Minnkota PowerDrive Black Trolling Motor",
                           "Daily ad budget", "$0 (no ads)", "$15/day for 14 days", 1180.0, "🛥️"),
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
        title="Get 4 of your items into Walmart's Memorial Day sale event",
        summary="Walmart is running a big Memorial Day weekend sale (May 24–27) and 4 of your items qualify. Discounting them about 18% during that window could bring in roughly $5,400 extra.",
        one_liner_why="Walmart is sending a wave of shoppers your way for the holiday.",
        category="incentives",
        risk_tier="medium",
        confidence=82,
        gmv_impact_usd=5400.0,
        sku_count=4,
        status="new",
        created_at=now - timedelta(hours=3, minutes=40),
        reasoning="Walmart's Memorial Day sale runs May 24–27 and brings a big wave of shoppers. I looked through your catalog for items that fit (enough in stock, well-rated, holiday-friendly) and found 4 good candidates. During past Walmart sale events, items in the promotion sold about 3 times more than usual.",
        evidence=[
            "Walmart's Memorial Day sale runs May 24–27, 2026",
            "4 of your outdoor & grill items are a good fit",
            "Items in past Walmart sales sold about 3 times faster than normal",
        ],
        proposed_changes=[
            ProposedChange("MATL-WFS-C4982", "Hot Wheels 1:64 Scale Die-Cast Vehicle Assortment",
                           "Sale price", "$6.31", "$4.99 (just for the sale weekend)", 1180.0, "🚗"),
            ProposedChange("MATL-WFS-HTN77", "Hot Wheels City Downtown Ice Cream Swirl Playset",
                           "Sale price", "$24.99", "$19.99 (just for the sale weekend)", 1620.0, "🍦"),
        ],
        tool_calls=[
            ToolCall("get_promo_calendar", "window=14d", "Memorial Day Flash Deal", 120),
            ToolCall("filter_eligible_skus", "event=memorial_day", "4 eligible", 380),
        ],
    ))

    # ---- CATALOG: low-confidence, low-impact — auto-eligible ----
    opps.append(Opportunity(
        id=_id("opp"),
        title="Fill in missing details on 19 items — small but easy",
        summary="19 of your items are missing simple info like color or material. I can fill these in automatically by reading the product photos and titles. Small but quick.",
        one_liner_why="These details are right there in your photos.",
        category="catalog",
        risk_tier="low",
        confidence=98,
        gmv_impact_usd=320.0,
        sku_count=19,
        status="new",
        created_at=now - timedelta(hours=4, minutes=15),
        reasoning="19 of your items are missing one or two simple details — like color or material — that I can read straight from the product photo or title. These are quick fills with high confidence. Because the impact is small and the risk is tiny, you can let me handle these automatically if you'd like.",
        evidence=[
            "19 items missing 1–2 simple details each",
            "All of them can be filled in from existing photos and titles",
            "Small enough impact that you can let me handle it on my own",
        ],
        proposed_changes=[
            ProposedChange("AUTO-EX-1", "19 items — bulk fix", "Missing details",
                           "1–2 missing per item", "Filled in from photos & titles", 320.0, "🤖"),
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
                   "Lowered the price of one item", "Mederma Advanced Scar Gel",
                   "Was $37.98, now $37.50 — to stay competitive", 142.0),
        AuditEntry(_id("a"), now - timedelta(hours=2), "sage",
                   "Filled in missing product details", "12 items (color and material)",
                   "Read the details from product photos and titles", 240.0),
        AuditEntry(_id("a"), now - timedelta(hours=4), "user",
                   "You approved better product wording", "8 popular items",
                   "New titles and descriptions to help shoppers find them", 2840.0),
        AuditEntry(_id("a"), now - timedelta(hours=6), "sage",
                   "Claimed free ad money before it expired", "Walmart — $480",
                   "Spread across your top 3 items", 480.0),
        AuditEntry(_id("a"), now - timedelta(hours=8), "user",
                   "You turned on auto-pricing for 47 items", "47 items now using auto-pricing",
                   "They'll stay competitive without you doing anything", 4120.0),
        AuditEntry(_id("a"), now - timedelta(days=1, hours=2), "sage",
                   "Lowered the price of one item", "MXR A/B Box",
                   "Was $89.99, now $84.99 — to win the sale", 218.0),
        AuditEntry(_id("a"), now - timedelta(days=1, hours=5), "user",
                   "You said ‘not yet’ on the warehouse clearance idea", "1,054 old items",
                   "Wanted to wait another week before discounting", 0.0),
        AuditEntry(_id("a"), now - timedelta(days=2), "sage",
                   "Added 6 items to Mother's Day sale", "6 items",
                   "You'd told me ahead of time to handle holiday sales", 3240.0),
        AuditEntry(_id("a"), now - timedelta(days=3), "sage",
                   "Updated product wording on 22 items", "22 items",
                   "You'd pre-approved this batch of wording improvements", 1840.0),
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
