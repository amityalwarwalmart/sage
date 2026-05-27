"""Marty chat — intent-routed conversational layer over the Pricing Agent.

Mock-LLM style: keyword routing → rich HTML bubbles with inline action cards,
mini-approve buttons, and follow-up suggestions. Every action button posts
back to /marty/action which actually mutates state and acknowledges with a
fresh Marty bubble.

Killer flows (per user spec):
- "Show me what the agent did today"        → daily digest with bulk-approve
- "Why did you drop X?"                     → market signal + reasoning + link
- "Bulk approve the Pro Seller actions"     → batched approval in-chat
- "Switch to autopilot"                     → mode change w/ confirmation
- "What's my biggest risk right now?"       → highest-priority surface
"""
from __future__ import annotations

import html
import re
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse

from app.data.marty import (
    ACTIONS,
    AUDIT,
    MODE_META,
    POLICY,
    TIER_META,
    PricingAction,
    actions_by_status,
    actions_by_tier,
    approve_action,
    bulk_approve,
    bulk_reject,
    reject_action,
    rollback_action,
    run_stats,
    set_mode,
)

router = APIRouter()


# ---------- Rendering helpers ----------

def _user(text: str) -> str:
    return f'''
    <div class="flex gap-2 justify-end slide-up">
      <div class="bg-marty-100 text-white rounded-2xl rounded-tr-md px-3.5 py-2.5 max-w-[85%] leading-snug text-[13px]">{html.escape(text)}</div>
    </div>'''


def _marty(body_html: str) -> str:
    return f'''
    <div class="flex gap-2 slide-up">
      <div class="w-7 h-7 rounded-xl marty-orb flex-shrink-0"></div>
      <div class="bg-wmgray-5 rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] leading-snug text-[13px] text-wmgray-130 space-y-2">{body_html}</div>
    </div>'''


def _chip(label: str, ask: str) -> str:
    safe_ask = html.escape(ask).replace("'", "&#39;")
    return (f'<button onclick="askMarty(\'{safe_ask}\')" '
            f'class="text-[11px] px-2.5 py-1 rounded-full border border-wmgray-30 text-wmgray-130 '
            f'hover:border-marty-100 hover:text-marty-100 bg-white">{html.escape(label)}</button>')


def _action_btn(label: str, action_name: str, payload: dict, kind: str = "primary") -> str:
    """Inline button that mutates state via /marty/action."""
    import json
    vals = json.dumps({"action": action_name, **payload}).replace('"', "&quot;")
    cls_primary = "marty-grad text-white hover:opacity-90"
    cls_ghost = "bg-white border border-wmgray-30 text-wmgray-130 hover:border-marty-100 hover:text-marty-100"
    cls_danger = "bg-white border border-wmgray-30 text-wmgray-130 hover:border-wmred-100 hover:text-wmred-130"
    cls = {"primary": cls_primary, "ghost": cls_ghost, "danger": cls_danger}.get(kind, cls_primary)
    return (
        f'<button hx-post="/marty/action" hx-vals="{vals}" '
        f'hx-target="#marty-thread" hx-swap="beforeend" '
        f'class="{cls} text-[11px] font-bold rounded-lg px-3 py-1.5 transition">{html.escape(label)}</button>'
    )


def _link_btn(label: str, url: str) -> str:
    return (f'<a href="{url}" class="bg-white border border-wmgray-30 text-wmgray-130 hover:border-marty-100 hover:text-marty-100 '
            f'text-[11px] font-bold rounded-lg px-3 py-1.5 transition inline-block">{html.escape(label)}</a>')


def _action_card(a: PricingAction, show_approve: bool = True) -> str:
    """A miniature version of an inbox row, embedded in chat."""
    tier_cls = a.tier_meta["tone_class"]
    tier_lbl = a.tier_meta["label"].upper()
    price_html = ""
    if a.current_price > 0:
        price_html = (
            f'<div class="flex items-center gap-1.5 text-[11px] mt-1">'
            f'<span class="bubble-current px-1.5 py-0.5 rounded font-bold text-[10px]">${a.current_price:.2f}</span>'
            f'<span class="text-wmgray-100">→</span>'
            f'<span class="bubble-proposed px-1.5 py-0.5 rounded font-bold text-[10px]">${a.proposed_price:.2f}</span>'
            f'<span class="text-[10px] font-bold {"text-wmred-130" if a.price_delta_pct < 0 else "text-wmgreen-130"}">'
            f'{a.price_delta_pct:+.1f}%</span></div>'
        )
    impact = (f'<span class="text-[10px] font-bold text-wmgreen-130">'
              f'+${a.expected_gmv_lift_usd:,.0f}/30d</span>') if a.expected_gmv_lift_usd > 0 else ''

    approve_btn = ""
    if show_approve and a.status == "needs_approval":
        approve_btn = (
            f'<div class="flex gap-1 mt-2">'
            f'{_action_btn("✓ Approve", "approve", {"aid": a.id})}'
            f'{_action_btn("✖ Dismiss", "reject", {"aid": a.id}, kind="danger")}'
            f'{_link_btn("Open", f"/agent/action/{a.id}")}'
            f'</div>'
        )

    return f'''
    <div class="bg-white rounded-lg border border-wmgray-30 p-2.5 text-[12px]">
      <div class="flex items-start gap-2">
        <span class="text-base">{a.item_image_emoji}</span>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <span class="text-[9px] font-bold px-1 py-0.5 rounded {tier_cls}">{tier_lbl}</span>
            <span class="text-[9px] font-bold text-wmgray-100">{a.action_label}</span>
            {impact}
          </div>
          <div class="text-[12px] font-semibold text-wmgray-160 leading-tight truncate">{html.escape(a.item_name)}</div>
          <div class="text-[11px] text-wmgray-100 leading-snug mt-0.5">{html.escape(a.reason_oneliner)}</div>
          {price_html}
          {approve_btn}
        </div>
      </div>
    </div>'''


def _suggestions(chips: list[tuple[str, str]]) -> str:
    return f'<div class="flex flex-wrap gap-1.5 pt-1">{"".join(_chip(l, a) for l, a in chips)}</div>'


# ---------- Intent routing ----------

def _find_action_by_name(name_fragment: str) -> PricingAction | None:
    fragment = name_fragment.lower()
    matches = [a for a in ACTIONS if fragment in a.item_name.lower()]
    return matches[0] if matches else None


def reply_daily_digest() -> str:
    stats = run_stats()
    auto = actions_by_status("auto_executed")
    needs = actions_by_status("needs_approval")
    blocked = actions_by_status("blocked")
    cards = "".join(_action_card(a) for a in auto[:3])
    pending_cards = "".join(_action_card(a, show_approve=True) for a in needs[:2])

    return _marty(f'''
    <div class="font-bold text-wmgray-160">Here's what I've been up to today 👀</div>

    <div class="bg-white rounded-lg p-2.5 border border-wmgray-30">
      <div class="grid grid-cols-3 gap-2 text-center">
        <div><div class="text-base font-extrabold text-wmgreen-130">{stats.actions_auto_executed_24h}</div><div class="text-[10px] text-wmgray-100">auto-executed</div></div>
        <div><div class="text-base font-extrabold text-spark-140">{stats.actions_needing_approval}</div><div class="text-[10px] text-wmgray-100">need your call</div></div>
        <div><div class="text-base font-extrabold text-wmred-130">{stats.actions_blocked_24h}</div><div class="text-[10px] text-wmgray-100">blocked</div></div>
      </div>
    </div>

    <div class="text-[12px] text-wmgray-130">
      <strong>+${stats.gmv_uplift_usd_7d:,.0f}</strong> in attributed uplift this week, with <strong>+{stats.buybox_wins_added_7d}</strong> Buy Box wins and a <strong>+{stats.pcs_delta_7d:.2f}pt</strong> PCS lift. ~{stats.hours_saved_estimate_7d:.1f}h saved.
    </div>

    <div class="text-[11px] font-bold text-wmgray-100 uppercase tracking-wider pt-1">✅ Recent auto-executions</div>
    {cards}

    <div class="text-[11px] font-bold text-wmgray-100 uppercase tracking-wider pt-2">⏳ Top 2 waiting on you</div>
    {pending_cards}

    <div class="flex gap-1.5 pt-1">
      {_action_btn(f"✓ Bulk approve all {len(needs)} pending", "bulk_approve_all", {})}
      {_link_btn("See full inbox", "/agent/inbox")}
    </div>

    {_suggestions([
        ("Why is one blocked?", "Why are some actions blocked?"),
        ("Show me high-risk only", "Show me high-risk actions"),
        ("Switch to autopilot", "Switch to autopilot mode"),
    ])}
    ''')


def reply_explain(action_name_fragment: str) -> str:
    a = _find_action_by_name(action_name_fragment)
    if not a:
        return _marty(f'''
        <div>I couldn't find an item matching <strong>"{html.escape(action_name_fragment)}"</strong>. Try a SKU name or just say "what's pending?"</div>
        {_suggestions([
            ("What's pending?", "What needs my approval?"),
            ("Daily digest", "Show me what you did today"),
        ])}
        ''')

    signal_html = ""
    if a.market_signal:
        ms = a.market_signal
        signal_html = f'''
        <div class="bg-white rounded-lg p-2.5 border border-wmgray-30">
          <div class="text-[10px] font-bold text-wmgray-100 uppercase tracking-wider mb-1.5">📡 What changed</div>
          <div class="grid grid-cols-3 gap-2 text-[11px]">
            <div><div class="text-wmgray-100">{html.escape(ms.competitor_name)}</div><div class="font-bold text-wmgray-160">${ms.competitor_price:.2f}</div></div>
            <div><div class="text-wmgray-100">You</div><div class="font-bold text-wmgray-160">${ms.your_price:.2f}</div></div>
            <div><div class="text-wmgray-100">Buy Box</div><div class="font-bold {"text-wmred-130" if ms.buybox_winner == "competitor" else "text-wmgreen-130"}">{("Them" if ms.buybox_winner == "competitor" else "You" if ms.buybox_winner == "you" else "—")}</div></div>
          </div>
          <div class="text-[10px] text-wmgray-100 mt-1.5">Spotted {ms.signal_age_minutes}m ago</div>
        </div>'''

    guardrail_html = "".join(
        f'<div class="flex items-start gap-1.5 text-[11px]">'
        f'<span class="{"text-wmgreen-130" if g.result == "pass" else "text-wmred-130"}">{"✓" if g.result == "pass" else "🛑"}</span>'
        f'<div><strong>{html.escape(g.name)}</strong> <span class="text-wmgray-100">— {html.escape(g.detail)}</span></div>'
        f'</div>'
        for g in a.guardrails_checked
    )

    cta_chip = []
    if a.status == "needs_approval":
        cta_chip = [_action_btn("✓ Approve this one", "approve", {"aid": a.id})]
    elif a.status == "auto_executed" and not a.reverted:
        cta_chip = [_action_btn("↩ Roll it back", "rollback", {"aid": a.id}, kind="danger")]

    cta_html = "".join(cta_chip) + _link_btn("Open full detail →", f"/agent/action/{a.id}")

    return _marty(f'''
    <div class="font-bold text-wmgray-160">{html.escape(a.item_name)}</div>
    <div class="text-[11px] text-wmgray-100">{a.action_icon} {html.escape(a.action_label)} · {a.tier_meta["label"]} risk</div>
    {signal_html}
    <div class="text-[12px]">{html.escape(a.reason_detail)}</div>
    <div class="bg-white rounded-lg p-2.5 border border-wmgray-30 space-y-1">
      <div class="text-[10px] font-bold text-wmgray-100 uppercase tracking-wider mb-1">🛡️ Guardrails checked</div>
      {guardrail_html}
    </div>
    <div class="flex gap-1.5 pt-1">{cta_html}</div>
    {_suggestions([
        ("Why this tier?", f"Why is {a.item_name.split()[0]} {a.tier_meta['label']} risk?"),
        ("Daily digest", "Show me what you did today"),
    ])}
    ''')


def reply_pending() -> str:
    needs = actions_by_status("needs_approval")
    if not needs:
        return _marty('''
        <div>🎉 Nothing waiting on you right now. I'll surface things as I find them.</div>
        ''' + _suggestions([
            ("Daily digest", "Show me what you did today"),
            ("Switch to autopilot", "Switch to autopilot"),
        ]))

    cards = "".join(_action_card(a) for a in needs[:4])
    total_value = sum(a.expected_gmv_lift_usd for a in needs)

    return _marty(f'''
    <div>You have <strong>{len(needs)}</strong> action{"s" if len(needs) != 1 else ""} waiting — worth about <strong class="text-wmgreen-130">+${total_value:,.0f}</strong> over the next month.</div>
    {cards}
    <div class="flex gap-1.5 pt-1">
      {_action_btn(f"✓ Approve all {len(needs)}", "bulk_approve_all", {})}
      {_link_btn("Full inbox", "/agent/inbox")}
    </div>
    ''')


def reply_biggest_risk() -> str:
    blocked = actions_by_status("blocked")
    high_pending = [a for a in actions_by_status("needs_approval") if a.risk_tier == "high"]

    if blocked:
        a = blocked[0]
        return _marty(f'''
        <div class="font-bold text-wmgray-160">🛑 Your biggest risk right now is a blocked action.</div>
        <div class="text-[12px]">{html.escape(a.item_name)} would have needed me to break two of your guardrails. I refused. Here's what I almost did:</div>
        {_action_card(a, show_approve=False)}
        <div class="text-[11px] text-wmgray-100">You can either widen the guardrail for this SKU, or accept losing Buy Box on it.</div>
        <div class="flex gap-1.5">
          {_link_btn("Open detail →", f"/agent/action/{a.id}")}
          {_link_btn("Review guardrails", "/agent/policy")}
        </div>
        ''')
    if high_pending:
        a = high_pending[0]
        return _marty(f'''
        <div class="font-bold text-wmgray-160">⚠️ Your biggest pending decision:</div>
        {_action_card(a)}
        <div class="text-[11px] text-wmgray-100">This is a high-risk action — you'll see <em>every</em> one of these before it touches your prices.</div>
        ''')

    return _marty('''
    <div>👌 Nothing risky pending. Everything I'm working on is within your guardrails and either auto-executed or queued for a routine bulk-approval.</div>
    ''' + _suggestions([
        ("Show me pending", "What needs my approval?"),
        ("Daily digest", "Show me what you did today"),
    ]))


def reply_mode_change(target_mode: str) -> str:
    target_mode = target_mode.lower().strip()
    if target_mode not in ("shadow", "recommend", "autopilot"):
        return _marty(f'I have three modes: <strong>Shadow</strong>, <strong>Recommend</strong>, and <strong>Autopilot</strong>. Which one?')

    meta = MODE_META[target_mode]
    current = POLICY.mode
    if current == target_mode:
        return _marty(f'I\'m already in <strong>{meta["label"]}</strong> mode. {html.escape(meta["tagline"])}')

    warning = ""
    if target_mode == "autopilot":
        warning = '<div class="bg-spark-5 border border-spark-100 rounded p-2 text-[11px] text-spark-140"><strong>Heads up:</strong> I\'ll start auto-executing low-risk actions immediately. Medium and high-risk still need your sign-off.</div>'

    return _marty(f'''
    <div>Switch from <strong>{MODE_META[current]["label"]}</strong> → <strong>{meta["label"]}</strong>?</div>
    <div class="text-[12px] text-wmgray-100">{html.escape(meta["tagline"])}</div>
    {warning}
    <div class="flex gap-1.5">
      {_action_btn(f"✓ Yes, switch to {meta['label']}", "set_mode", {"mode": target_mode})}
      {_action_btn("Cancel", "noop", {}, kind="ghost")}
    </div>
    ''')


def reply_show_tier(tier: str) -> str:
    rows = [a for a in actions_by_tier(tier) if a.status in ("needs_approval", "auto_executed", "blocked")]
    if not rows:
        return _marty(f'No {tier}-tier actions right now.')
    cards = "".join(_action_card(a) for a in rows[:5])
    return _marty(f'''
    <div>{tier.title()}-tier actions right now ({len(rows)} total):</div>
    {cards}
    {_link_btn(f"Full {tier} list →", f"/agent/inbox?tier={tier}")}
    ''')


def reply_default(message: str) -> str:
    return _marty(f'''
    <div>I can help with anything pricing-related across the {len(ACTIONS)} actions I'm tracking. Try one of these:</div>
    {_suggestions([
        ("📊 What you did today", "Show me what you did today"),
        ("⏳ What's pending?", "What needs my approval?"),
        ("⚠️ Biggest risk?", "What's my biggest risk right now?"),
        ("🤖 Switch to autopilot", "Switch to autopilot"),
        ("🛡️ Show blocked actions", "Show me blocked actions"),
    ])}
    ''')


# ---------- Routes ----------

INTENT_PATTERNS: list[tuple[re.Pattern, Callable[[re.Match], str]]] = [
    (re.compile(r'\b(today|did today|daily|digest|what (?:have|did) you|what.{0,10}been (?:up to|doing)|recent)\b', re.I),
     lambda m: reply_daily_digest()),
    (re.compile(r'\bwhy (?:did|are|is) (?:you |.{0,20} )?(?:drop|raise|change|action|approve|block|skip).*?(\w[\w ]*?)(?:\?|$)', re.I),
     lambda m: reply_explain(m.group(1).strip())),
    (re.compile(r'\b(?:why|explain|tell me about|what.{0,5}(?:up|going on) with)\s+(\w[\w \-\']{2,30})(?:\?|$)', re.I),
     lambda m: reply_explain(m.group(1).strip())),
    (re.compile(r'\b(?:what.{0,10}pending|what needs my (?:approval|sign[- ]?off)|what.{0,10}wait|inbox|review queue)\b', re.I),
     lambda m: reply_pending()),
    (re.compile(r'\b(?:biggest risk|highest priority|most urgent|what.{0,10}(?:worry|concern)|critical|red flag)\b', re.I),
     lambda m: reply_biggest_risk()),
    (re.compile(r'\b(?:switch|change|set|move|put)(?:\s+(?:to|me to|the agent to|the mode to))?\s+(shadow|recommend|autopilot)\b', re.I),
     lambda m: reply_mode_change(m.group(1))),
    (re.compile(r'\b(shadow|recommend|autopilot)(?:\s+mode)?\b', re.I),
     lambda m: reply_mode_change(m.group(1))),
    (re.compile(r'\b(?:show|list|see|find).{0,20}?(low|medium|med|high)(?:[- ]?risk|[- ]?tier)?\b', re.I),
     lambda m: reply_show_tier(m.group(1).lower().replace("med", "medium"))),
    (re.compile(r'\b(?:bulk.{0,5}approve|approve all|approve everything)\b', re.I),
     lambda m: HTMLResponse_marker_BULK_APPROVE()),
    (re.compile(r'\b(?:blocked|stopped|refused|wouldn.t)\b', re.I),
     lambda m: reply_show_tier("blocked") if False else _reply_blocked()),
]


def HTMLResponse_marker_BULK_APPROVE() -> str:
    needs = actions_by_status("needs_approval")
    if not needs:
        return _marty("Nothing to approve right now 🎉")
    return _marty(f'''
    <div>About to approve all <strong>{len(needs)}</strong> pending action{"s" if len(needs) != 1 else ""} — worth <strong class="text-wmgreen-130">+${sum(a.expected_gmv_lift_usd for a in needs):,.0f}/30d</strong>. Confirm?</div>
    <div class="flex gap-1.5">
      {_action_btn(f"✓ Yes, approve all {len(needs)}", "bulk_approve_all", {})}
      {_action_btn("Cancel", "noop", {}, kind="ghost")}
    </div>''')


def _reply_blocked() -> str:
    blocked = actions_by_status("blocked")
    if not blocked:
        return _marty("Nothing blocked right now — your guardrails are letting me work cleanly. 👍")
    cards = "".join(_action_card(a, show_approve=False) for a in blocked)
    return _marty(f'''
    <div>I refused to take <strong>{len(blocked)}</strong> action{"s" if len(blocked) != 1 else ""} because they\'d break one of your guardrails:</div>
    {cards}
    <div class="text-[11px] text-wmgray-100">You can widen a guardrail per SKU, or accept that those Buy Boxes will stay lost.</div>
    {_link_btn("Open policy", "/agent/policy")}
    ''')


def _route_intent(message: str) -> str:
    for pattern, handler in INTENT_PATTERNS:
        m = pattern.search(message)
        if m:
            try:
                return handler(m)
            except Exception as e:  # pragma: no cover — defensive
                return _marty(f"Hmm, I tripped on that one. ({html.escape(str(e))})")
    return reply_default(message)


@router.post("/marty/chat")
async def marty_chat(message: str = Form(...)):
    user_bubble = _user(message)
    marty_bubble = _route_intent(message)
    return HTMLResponse(user_bubble + marty_bubble)


# ---------- Action handlers (button clicks inside chat) ----------

@router.post("/marty/action")
async def marty_action(
    action: str = Form(...),
    aid: str = Form(default=""),
    mode: str = Form(default=""),
):
    if action == "approve":
        ok = approve_action(aid)
        a = next((x for x in ACTIONS if x.id == aid), None)
        if ok and a:
            return HTMLResponse(_marty(f'''
            <div>✅ Approved <strong>{html.escape(a.item_name)}</strong> — sent to Repricer. Goes live within ~90 seconds.</div>
            <div class="text-[11px] text-wmgray-100">You can roll it back any time from <a href="/agent/history" class="text-marty-100 font-bold hover:underline">action history</a>.</div>
            '''))
        return HTMLResponse(_marty("That action is no longer pending."))

    if action == "reject":
        ok = reject_action(aid, note="Dismissed in Marty chat")
        a = next((x for x in ACTIONS if x.id == aid), None)
        if ok and a:
            return HTMLResponse(_marty(f'Got it — dismissed <strong>{html.escape(a.item_name)}</strong>. I won\'t re-propose this for 24h.'))
        return HTMLResponse(_marty("That action is no longer pending."))

    if action == "rollback":
        ok = rollback_action(aid, note="Rolled back from Marty chat")
        a = next((x for x in ACTIONS if x.id == aid), None)
        if ok and a:
            return HTMLResponse(_marty(f'↩ Rolled back <strong>{html.escape(a.item_name)}</strong> to ${a.current_price:.2f}.'))
        return HTMLResponse(_marty("Couldn't roll that back."))

    if action == "bulk_approve_all":
        needs = actions_by_status("needs_approval")
        ids = [a.id for a in needs]
        count = bulk_approve(ids)
        total_value = sum(a.expected_gmv_lift_usd for a in needs)
        return HTMLResponse(_marty(f'''
        <div>✅ Approved <strong>{count}</strong> action{"s" if count != 1 else ""} — sent to Repricer. Projected <strong class="text-wmgreen-130">+${total_value:,.0f}</strong> over 30 days.</div>
        <div class="text-[11px] text-wmgray-100">Any of them can be rolled back individually from <a href="/agent/history" class="text-marty-100 font-bold hover:underline">action history</a>.</div>
        '''))

    if action == "set_mode":
        if mode in ("shadow", "recommend", "autopilot"):
            old_mode = POLICY.mode
            set_mode(mode)  # type: ignore[arg-type]
            meta = MODE_META[mode]
            return HTMLResponse(_marty(f'''
            <div>✅ Switched from <strong>{MODE_META[old_mode]["label"]}</strong> → <strong>{meta["label"]}</strong>.</div>
            <div class="text-[12px] text-wmgray-100">{html.escape(meta["tagline"])}</div>
            <div class="text-[11px] text-wmgray-100">You'll see the change reflected on the <a href="/" class="text-marty-100 font-bold hover:underline">agent overview</a> mode banner.</div>
            '''))

    if action == "noop":
        return HTMLResponse(_marty("👍 No worries, nothing changed."))

    return HTMLResponse(_marty("Hmm, I didn't catch that."))
