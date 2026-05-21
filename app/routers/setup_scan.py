"""Setup scan — the post-onboarding 'discover' experience.

Layout: opportunities on the left, suggested guardrails on the right,
a chat strip across the bottom with quick-action buttons.
"""
import html
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.data.mock import (
    GUARDRAILS,
    ONBOARDING,
    OPPORTUNITIES,
    SETTINGS,
    kpi_summary,
)
from app.templates_env import templates

router = APIRouter()


@router.get("/setup-scan")
async def setup_scan(request: Request):
    open_opps = sorted(
        [o for o in OPPORTUNITIES.values() if o.status == "new"],
        key=lambda o: o.gmv_impact_usd,
        reverse=True,
    )

    # Group opportunities into the 4 focus areas
    opp_groups = {
        "pricing": [o for o in open_opps if o.category == "pricing"],
        "catalog": [o for o in open_opps if o.category == "catalog"],
        "incentives": [o for o in open_opps if o.category == "incentives"],
        "seo": [o for o in open_opps if o.category == "seo"],
    }
    group_totals = {k: sum(o.gmv_impact_usd for o in v) for k, v in opp_groups.items()}
    total_value = sum(group_totals.values())

    # Suggested guardrails based on scan
    suggested_floors = sum(1 for g in GUARDRAILS.values() if g.floor is not None)
    suggested_ceilings = sum(1 for g in GUARDRAILS.values() if g.ceiling is not None)

    return templates.TemplateResponse(request=request, name="setup_scan.html", context={
        "request": request,
        "active_page": "sage",
        "sub_page": "home",
        "ob": ONBOARDING,
        "opp_groups": opp_groups,
        "group_totals": group_totals,
        "total_value": total_value,
        "total_opps": len(open_opps),
        "settings": SETTINGS,
        "suggested_floors": suggested_floors,
        "suggested_ceilings": suggested_ceilings,
        "open_opps_count": kpi_summary()["open_opps"],
    })


# ---------- Inline chat with action buttons ----------

def _user_bubble(text: str) -> str:
    return f'''
    <div class="flex gap-2 justify-end">
      <div class="bg-wmblue-100 text-white rounded-2xl rounded-tr-md px-3.5 py-2.5 max-w-[80%] leading-snug text-sm">{html.escape(text)}</div>
      <div class="w-7 h-7 bg-wmgray-30 rounded-xl flex items-center justify-center text-xs font-bold text-wmgray-130 flex-shrink-0">You</div>
    </div>
    '''


def _sage_bubble(html_body: str) -> str:
    return f'''
    <div class="flex gap-2">
      <div class="w-7 h-7 sage-grad rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0">S</div>
      <div class="bg-wmgray-5 rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] leading-snug text-sm">{html_body}</div>
    </div>
    '''


def _action_btn(label: str, action: str, color: str = "blue") -> str:
    bg = "bg-wmblue-100 hover:bg-wmblue-110" if color == "blue" else "bg-white border border-wmgray-30 hover:border-wmblue-100 text-wmgray-130"
    text_cls = "text-white" if color == "blue" else "text-wmgray-130"
    return (
        f'<button hx-post="/setup-scan/action" hx-vals=\'{{"action":"{action}"}}\' '
        f'hx-target="#scan-chat-thread" hx-swap="beforeend" '
        f'class="{bg} {text_cls} text-xs font-bold rounded-lg px-3 py-1.5">{label}</button>'
    )


SCAN_RESPONSES = {
    "approve_pricing": lambda: _sage_bubble('''
        <div>Great. I'll start watching all 6 of those pricing opportunities and queue up the small ones for you to review tomorrow morning. ✅</div>
        <div class="mt-2 text-xs text-wmgray-100">Heading to your <a href="/inbox" class="text-wmblue-100 font-bold hover:underline">to-do list</a> with these queued.</div>
    '''),
    "approve_all": lambda: _sage_bubble('''
        <div>Locked in. I've added all 7 opportunities to your to-do list and set the guardrails I suggested. ✅</div>
        <div class="mt-2">''' + _action_btn("Take me to my workspace →", "go_workspace", "blue") + '''</div>
    '''),
    "tighten_floor": lambda: _sage_bubble('''
        <div>Done — I bumped your minimum margin from 15% to 20%. I'll never set a price below that. 🛡️</div>
    '''),
    "explain_seo": lambda: _sage_bubble('''
        <div>Walmart sellers who use the SEO suggestions I generate see <strong>15% more sales on average</strong> (Walmart's data). I rewrote titles & descriptions for your top 33 items using words shoppers actually search for.</div>
        <div class="mt-2">''' + _action_btn("Show me one", "show_seo_example", "blue") + ''' ''' + _action_btn("Skip for now", "skip_seo", "white") + '''</div>
    '''),
    "show_seo_example": lambda: _sage_bubble('''
        <div>Here's the Sunpentown dishwasher:</div>
        <div class="mt-2 text-xs space-y-2">
            <div class="bg-white rounded p-2 border border-wmgray-30"><b>Before:</b> "Sunpentown 18 in. Portable Dishwasher with Energy Star"</div>
            <div class="bg-wmblue-5 rounded p-2 border border-wmblue-100/40"><b>After:</b> "Sunpentown 18" Standard Portable Countertop Dishwasher — Energy Star, 6 Wash Cycles, Stainless Steel"</div>
        </div>
        <div class="mt-2 text-xs text-wmgray-100">The "after" hits 4 keywords shoppers search for that the "before" missed.</div>
    '''),
    "skip_seo": lambda: _sage_bubble("I'll skip SEO for now. You can always turn it back on in <a href='/settings' class='text-wmblue-100 font-bold hover:underline'>your preferences</a>."),
    "go_workspace": lambda: '<script>window.location="/workspace"</script>',
    "go_inbox": lambda: '<script>window.location="/inbox"</script>',
}


def _route(msg: str) -> str:
    m = msg.lower()
    if "yes" in m or "go ahead" in m or "do it" in m or "approve" in m:
        return SCAN_RESPONSES["approve_all"]()
    if "tight" in m or "20%" in m or "stricter" in m or "raise margin" in m:
        return SCAN_RESPONSES["tighten_floor"]()
    if "seo" in m or "search" in m or "keyword" in m:
        return SCAN_RESPONSES["explain_seo"]()
    if "workspace" in m or "dashboard" in m:
        return SCAN_RESPONSES["go_workspace"]()
    return _sage_bubble('''
        <div>I can answer questions about any of the opportunities or guardrails on this page. Try:</div>
        <div class="mt-2 flex flex-wrap gap-1.5">''' +
        _action_btn("Tell me about SEO", "explain_seo", "white") + ''' ''' +
        _action_btn("Approve all of this", "approve_all", "white") + ''' ''' +
        _action_btn("Tighten my floors", "tighten_floor", "white") +
        '''</div>
    ''')


@router.post("/setup-scan/chat", response_class=HTMLResponse)
async def scan_chat(message: str = Form(...)):
    return HTMLResponse(_user_bubble(message) + _route(message))


@router.post("/setup-scan/action", response_class=HTMLResponse)
async def scan_action(action: str = Form(...)):
    fn = SCAN_RESPONSES.get(action)
    if not fn:
        return HTMLResponse(_sage_bubble("Hmm, I didn't catch that. Try again?"))
    return HTMLResponse(fn())
