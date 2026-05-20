"""Mocked chat — returns canned 'Sage' responses based on keyword match.

This is intentionally a hard-coded dispatcher so the demo is reliable. It
returns HTML fragments that get appended to the chat thread via HTMX.
"""
import html
from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse

router = APIRouter()


def _user_bubble(text: str) -> str:
    return f'''
    <div class="flex gap-2 justify-end">
      <div class="bg-wmblue-100 text-white rounded-2xl rounded-tr-sm px-3 py-2 max-w-[85%]">{html.escape(text)}</div>
      <div class="w-7 h-7 bg-wmgray-30 rounded-lg flex items-center justify-center text-xs font-bold text-wmgray-130 flex-shrink-0">A</div>
    </div>
    '''


def _sage_bubble(html_body: str) -> str:
    return f'''
    <div class="flex gap-2">
      <div class="w-7 h-7 sage-grad rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0">S</div>
      <div class="bg-wmgray-5 rounded-2xl rounded-tl-sm px-3 py-2 max-w-[85%]">{html_body}</div>
    </div>
    '''


def _thinking_bubble() -> str:
    return _sage_bubble(
        '<div class="flex items-center gap-1.5 text-wmgray-100 text-xs"><span class="pulse-dot w-1.5 h-1.5 bg-wmgray-100 rounded-full"></span><span>Scanning catalog…</span></div>'
    )


# Canned responses keyed by intent
RESPONSES = {
    "reprice": lambda: _sage_bubble('''
        <div>Found <strong>6 high-traffic SKUs</strong> where a small price cut could capture Buy Box.</div>
        <div class="mt-2 text-xs text-wmgray-100">Projected impact: <strong class="text-wmgreen-100">+$7,222</strong> in 30-day GMV · 92% confidence</div>
        <a href="/plan/opp-1000" class="mt-2 inline-block text-xs font-semibold text-wmblue-100 hover:underline">Review the plan →</a>
    '''),
    "aging": lambda: _sage_bubble('''
        <div>I see <strong>7,208 units aged &gt;365 days</strong> in WFS, bleeding storage fees.</div>
        <div class="mt-2 text-xs text-wmgray-100">Clearance pricing on 1,054 SKUs could recover <strong class="text-wmgreen-100">$157K</strong> in 30-day GMV.</div>
        <div class="mt-2 text-xs text-wmgray-100">⚠ This is High Risk — requires your approval.</div>
        <a href="/plan/opp-1001" class="mt-2 inline-block text-xs font-semibold text-wmblue-100 hover:underline">Review the plan →</a>
    '''),
    "listings": lambda: _sage_bubble('''
        <div><strong>247 'Poor' listings</strong> are getting traffic but converting under 0.5%.</div>
        <div class="mt-2 text-xs text-wmgray-100">Content rewrites could lift conversion 3–5x · <strong class="text-wmgreen-100">+$44.8K</strong> weekly GMV at risk</div>
        <a href="/plan/opp-1002" class="mt-2 inline-block text-xs font-semibold text-wmblue-100 hover:underline">Review the plan →</a>
    '''),
    "seo": lambda: _sage_bubble('''
        <div>Drafted Gen AI–optimized titles & descriptions for your <strong>33 top-traffic items</strong>.</div>
        <div class="mt-2 text-xs text-wmgray-100">Walmart sellers using SEO suggestions see avg <strong>+15% sales</strong>.</div>
        <a href="/plan/opp-1003" class="mt-2 inline-block text-xs font-semibold text-wmblue-100 hover:underline">Review the plan →</a>
    '''),
    "ad": lambda: _sage_bubble('''
        <div>You have <strong>$1,250 in unclaimed ad credits</strong> expiring Jun 3.</div>
        <div class="mt-2 text-xs text-wmgray-100">I can claim them and allocate across 8 Customer Favorites · projected <strong class="text-wmgreen-100">+$8,750</strong> GMV</div>
        <a href="/plan/opp-1004" class="mt-2 inline-block text-xs font-semibold text-wmblue-100 hover:underline">Review the plan →</a>
    '''),
    "promo": lambda: _sage_bubble('''
        <div><strong>Memorial Day Flash Deal</strong> opens May 24 — 4 of your SKUs are eligible.</div>
        <div class="mt-2 text-xs text-wmgray-100">Projected <strong class="text-wmgreen-100">+$5,400</strong> GMV during the window.</div>
        <a href="/plan/opp-1005" class="mt-2 inline-block text-xs font-semibold text-wmblue-100 hover:underline">Review the plan →</a>
    '''),
    "summary": lambda: _sage_bubble('''
        <div>Here's where you stand right now:</div>
        <ul class="mt-2 text-xs space-y-1 text-wmgray-130">
          <li>• <strong>7 open opportunities</strong> worth ~$241K in 30-day GMV</li>
          <li>• Buy Box win rate: 5.39% (down 0.56% in 30d)</li>
          <li>• Listing quality: 41% (Poor)</li>
          <li>• 7,208 units aged &gt;365 days in WFS</li>
        </ul>
        <a href="/inbox" class="mt-2 inline-block text-xs font-semibold text-wmblue-100 hover:underline">Open the inbox →</a>
    '''),
    "default": lambda: _sage_bubble('''
        <div>I can help you with <strong>catalog, pricing, incentives, and SEO</strong>.</div>
        <div class="mt-2 text-xs text-wmgray-100">Try one of the slash commands below, or ask me things like:</div>
        <ul class="mt-1 text-xs text-wmgray-100 list-disc pl-4 space-y-0.5">
          <li>"What's bleeding money right now?"</li>
          <li>"Show me my biggest opportunity"</li>
          <li>"Fix my worst listings"</li>
        </ul>
    '''),
}


def _route(msg: str) -> str:
    m = msg.lower()
    if "reprice" in m or "buy box" in m or "buybox" in m:
        return RESPONSES["reprice"]()
    if "aging" in m or "clearance" in m or "old stock" in m or "wfs stale" in m:
        return RESPONSES["aging"]()
    if "fix-listing" in m or "listing" in m or "poor" in m or "quality" in m:
        return RESPONSES["listings"]()
    if "seo" in m or "title" in m or "description" in m or "keyword" in m:
        return RESPONSES["seo"]()
    if "ad" in m or "credit" in m or "sponsored" in m or "campaign" in m:
        return RESPONSES["ad"]()
    if "promo" in m or "flash" in m or "deal" in m or "memorial" in m:
        return RESPONSES["promo"]()
    if "bleed" in m or "summary" in m or "status" in m or "stand" in m or "biggest" in m:
        return RESPONSES["summary"]()
    return RESPONSES["default"]()


@router.post("/chat", response_class=HTMLResponse)
async def chat(message: str = Form(...)):
    return HTMLResponse(_user_bubble(message) + _route(message))
