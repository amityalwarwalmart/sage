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
    COMMUNITY_QUERIES,
    MARKETPLACE_TELEMETRY,
    MODE_META,
    POLICY,
    QUERY_INTENT_PHRASES,
    RULE_TEMPLATES,
    RULES,
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
        ("🎯 Losing Buy Box", "Show me items losing the Buy Box"),
        ("⚡ Enroll in Repricer", "Why should I enroll in Repricer?"),
        ("🐢 Aged + losing BB", "Show me aged inventory losing the Buy Box"),
        ("❓ Why ineligible?", "What\'s the reason for Buy Box ineligibility?"),
        ("📊 Today's digest", "Show me what you did today"),
    ])}
    ''')


# ---------- New community-driven intents (from Smart Filters telemetry) ----------

def _items_losing_buybox(limit: int = 5) -> list[PricingAction]:
    """All actions that are about Buy Box recovery (match/beat/SPIP, plus price_risk cohort)."""
    out = [a for a in ACTIONS
           if a.action_type in ("buybox_match", "buybox_beat_by_cent", "spip_unsuppress")
           and a.status in ("needs_approval", "auto_executed")]
    return sorted(out, key=lambda a: -a.expected_gmv_lift_usd)[:limit]


def reply_losing_buybox() -> str:
    items = _items_losing_buybox()
    total = sum(a.expected_gmv_lift_usd for a in items)
    cards = "".join(_action_card(a) for a in items)
    return _marty(f'''
    <div class="font-bold text-wmgray-160">🎯 Losing the Buy Box — your top community query right now</div>
    <div class="text-[12px]">
      You\'ve lost Buy Box on <strong>{MARKETPLACE_TELEMETRY["small_price_gap_items_count"]:,}</strong>
      items with small price gaps. Here are the highest-value matches I can do right now —
      worth <strong class="text-wmgreen-130">+${total:,.0f}/30d</strong>.
    </div>
    {cards}
    <div class="flex gap-1.5 pt-1">
      {_action_btn("✓ Approve all matches", "bulk_approve_buybox", {})}
      {_link_btn("See full inbox →", "/agent/inbox?cohort=price_risk")}
    </div>
    {_suggestions([
        ("Why am I losing it?", "What\'s the reason for Buy Box ineligibility?"),
        ("Aged + losing BB", "Show me aged inventory losing the Buy Box"),
        ("WFS + no BB", "Show WFS items with no Buy Box"),
    ])}
    ''')


def reply_repricer_enrollment() -> str:
    """The #1 demo moment — only 1.28% of catalog is enrolled."""
    enroll_action = next((a for a in ACTIONS if a.action_type == "repricer_enrollment"), None)
    tel = MARKETPLACE_TELEMETRY
    card_html = _action_card(enroll_action) if enroll_action else ""
    return _marty(f'''
    <div class="font-bold text-wmgray-160">⚡ Repricer is your biggest untapped lever right now.</div>
    <div class="bg-white rounded-lg p-2.5 border border-wmgray-30">
      <div class="grid grid-cols-2 gap-2 text-center">
        <div>
          <div class="text-2xl font-extrabold text-wmred-130">{tel["repricer_enrolled_pct"]:.2f}%</div>
          <div class="text-[10px] text-wmgray-100">of your {tel["catalog_total_items"]:,} SKUs are enrolled today</div>
        </div>
        <div>
          <div class="text-2xl font-extrabold text-wmgreen-130">+{tel["repricer_enrolled_buybox_rate"]:.1f}%</div>
          <div class="text-[10px] text-wmgray-100">Buy Box rate lift on enrolled vs unenrolled</div>
        </div>
      </div>
    </div>
    <div class="text-[12px]">
      Enrolled items also see <strong>{tel["repricer_enrolled_pcs"]:.1f}%</strong> PCS
      vs your overall <strong>{tel["pcs_pct"]:.1f}%</strong>. Closing this gap
      is the single highest-leverage move available in your account today.
    </div>
    <div class="text-[11px] font-bold text-wmgray-100 uppercase tracking-wider pt-1">My proposal:</div>
    {card_html}
    {_suggestions([
        ("Show me what it'd change", "Why did you propose Repricer enrollment?"),
        ("Approve top 1,200", "Approve the Repricer enrollment action"),
        ("Show me what you did today", "Show me what you did today"),
    ])}
    ''')


def reply_high_traffic_low_sales() -> str:
    rows = [a for a in ACTIONS
            if a.action_type in ("buybox_match", "buybox_beat_by_cent", "spip_unsuppress")
            and a.status == "needs_approval"][:3]
    cards = "".join(_action_card(a) for a in rows)
    return _marty(f'''
    <div class="font-bold text-wmgray-160">📈 High traffic, low sales — usually a Buy Box or price problem</div>
    <div class="text-[12px]">
      When a SKU has views but no sales, 9 times out of 10 it\'s losing Buy Box to a small price gap
      or sitting on a price the algorithm doesn\'t consider competitive. Here are 3 likely culprits:
    </div>
    {cards}
    <div class="text-[11px] text-wmgray-100 pt-1">Want the full list? It\'s in the <a href="/agent/inbox?cohort=price_risk" class="text-marty-100 font-bold hover:underline">price-risk cohort</a>.</div>
    {_suggestions([
        ("Show losing Buy Box", "Show me items losing the Buy Box"),
        ("Why ineligible?", "Reason for Buy Box ineligibility"),
    ])}
    ''')


def reply_aged_and_losing_buybox() -> str:
    """Compound query — aged inventory + losing buybox = highest-value cohort."""
    return _marty(f'''
    <div class="font-bold text-wmgray-160">🐢 Aged inventory that\'s also losing the Buy Box — nasty combo</div>
    <div class="text-[12px]">
      You have <strong>{MARKETPLACE_TELEMETRY["aging_items_count"]:,}</strong> items older than 12 months,
      tying up storage and Buy Box share. There\'s about
      <strong class="text-wmgreen-130">${MARKETPLACE_TELEMETRY["aging_gmv_opportunity_usd"]:,}</strong>
      in clearance opportunity sitting here.
    </div>
    <div class="bg-white rounded-lg p-2.5 border border-wmgray-30 space-y-1.5">
      <div class="text-[11px] font-bold text-wmgray-100 uppercase tracking-wider">My recommended play:</div>
      <div class="text-[12px]">
        ① Markdown the 1,054-SKU inventory-risk cohort by 8–12% (medium tier, bulk approve)<br>
        ② Match Buy Box on the highest-traffic aged items first (low tier, auto)<br>
        ③ Anything still unsold after 30 days → escalate to clearance promo (high tier, your call)
      </div>
    </div>
    <div class="flex gap-1.5 pt-1">
      {_link_btn("See inventory-risk cohort", "/agent/inbox?cohort=inventory_risk")}
      {_action_btn("Stage all 3 steps for review", "stage_aged_buybox_plan", {})}
    </div>
    ''')


def reply_buybox_ineligibility() -> str:
    """Diagnostic intent — explain the multi-factor model."""
    return _marty(f'''
    <div class="font-bold text-wmgray-160">❓ The 5 reasons you can lose Buy Box on Walmart</div>
    <div class="bg-white rounded-lg p-2.5 border border-wmgray-30 text-[12px] space-y-2">
      <div><strong>1. Price not competitive ({MARKETPLACE_TELEMETRY["small_price_gap_items_count"]:,} of your items today)</strong><br>
        <span class="text-wmgray-100">You\'re even $0.01 above another offer on the same item.</span></div>
      <div><strong>2. Item suppressed (SPIP)</strong><br>
        <span class="text-wmgray-100">Walmart pulled visibility because the price was too high vs external sites.</span></div>
      <div><strong>3. Stock-out or low inventory</strong><br>
        <span class="text-wmgray-100">Sellers with &lt;3 days of inventory get deprioritized.</span></div>
      <div><strong>4. Poor shipping speed / Pro Seller status</strong><br>
        <span class="text-wmgray-100">Buy Box weights ship-time and Pro Seller badge alongside price.</span></div>
      <div><strong>5. Listing quality score below threshold</strong><br>
        <span class="text-wmgray-100">Missing attributes, low-res images, or weak SEO drop the listing rank.</span></div>
    </div>
    <div class="text-[12px]">
      For YOUR account today, <strong>reason #1 is the biggest —
      <strong class="text-wmred-130">{MARKETPLACE_TELEMETRY["small_price_gap_items_count"]:,}</strong>
      items lose Buy Box to small price gaps</strong>. Enrolling in Repricer fixes most of them automatically.
    </div>
    {_suggestions([
        ("Enroll in Repricer", "Why should I enroll in Repricer?"),
        ("Show losing Buy Box", "Show me items losing the Buy Box"),
        ("High traffic / low sales", "Products with high traffic and low sales"),
    ])}
    ''')


def reply_wfs_no_buybox() -> str:
    return _marty(f'''
    <div class="font-bold text-wmgray-160">📦 WFS items with no Buy Box</div>
    <div class="text-[12px]">
      You\'re paying WFS storage and pick-pack but not winning the order. Usually 1 of 2 reasons:
      <strong>(a)</strong> another seller is matching price + has competitive shipping, or
      <strong>(b)</strong> SPIP suppression. I can match price on the worst offenders within your floor:
    </div>
    {"".join(_action_card(a) for a in [a for a in ACTIONS if "WFS" in a.sku and a.status == "needs_approval"][:3])}
    ''')


def reply_high_margin() -> str:
    """For Turkish 'kar elde etme orani yuksek olanlar' / 'high margin'."""
    high_margin = [a for a in ACTIONS if a.margin_pct and a.margin_pct >= 35]
    cards = "".join(_action_card(a) for a in high_margin[:3])
    return _marty(f'''
    <div class="font-bold text-wmgray-160">💵 Your highest-margin items where I can move price safely</div>
    <div class="text-[12px]">
      These have &gt;35% margin at the proposed price, so dropping a bit to win Buy Box still leaves
      healthy profit.
    </div>
    {cards or "<div class='text-[11px] text-wmgray-100'>No high-margin pricing actions pending right now.</div>"}
    ''')


# ---------- Rules intents ----------

def reply_rules_overview() -> str:
    """List active rules + offer to create from template."""
    actives = [r for r in RULES if r.status == "active"]
    total_fired = sum(r.actions_fired_7d for r in RULES)
    total_gmv = sum(r.gmv_impact_7d_usd for r in RULES)
    rule_lines = "".join(
        f'<div class="bg-white rounded-lg border border-wmgray-30 p-2.5 text-[12px]">'
        f'<div class="flex items-center gap-1.5 mb-0.5">'
        f'<span class="text-[9px] font-bold px-1 py-0.5 rounded {r.tier_meta["tone_class"]}">{r.tier_meta["label"].upper()}</span>'
        f'<a href="/agent/rules/{r.id}" class="font-bold text-wmgray-160 hover:text-marty-130 truncate">{html.escape(r.name)}</a>'
        f'</div>'
        f'<div class="text-[11px] text-wmgray-100 italic">“{html.escape(r.plain_english)}”</div>'
        f'<div class="text-[10px] text-wmgray-100 mt-1">{r.actions_fired_7d} fired · 7d · +${r.gmv_impact_7d_usd:,.0f}</div>'
        f'</div>'
        for r in actives[:3]
    )
    return _marty(f'''
    <div class="font-bold text-wmgray-160">📜 Your active repricing rules ({len(actives)})</div>
    <div class="text-[12px]">
      Combined: <strong>{total_fired}</strong> actions fired in the last 7 days, with about
      <strong class="text-wmgreen-130">+${total_gmv:,.0f}</strong> GMV impact.
    </div>
    {rule_lines}
    <div class="flex gap-1.5 pt-1">
      {_link_btn("Open all rules →", "/agent/rules")}
      {_link_btn("+ Create new rule", "/agent/rules/new")}
    </div>
    {_suggestions([
        ("Aged inventory rule", "Create a rule for aged inventory"),
        ("Buy Box recovery rule", "Create a rule for losing Buy Box"),
        ("What\'s pending?", "What needs my approval?"),
    ])}
    ''')


def reply_create_rule(hint: str) -> str:
    """User asked to create a rule — surface matching templates."""
    hint_l = hint.lower()
    # Score templates by keyword overlap
    scored = []
    for i, tpl in enumerate(RULE_TEMPLATES):
        score = 0
        if "aged" in hint_l or "clearance" in hint_l or "slow" in hint_l or "unsold" in hint_l:
            if tpl["trigger_kind"] == "no_sales_for_days" or tpl["action_kind"] == "create_clearance_promo":
                score += 3
        if "buy box" in hint_l or "buybox" in hint_l or "losing" in hint_l:
            if tpl["trigger_kind"] in ("buybox_lost_for_hours", "high_margin_and_no_buybox") or tpl["action_kind"].startswith("buybox"):
                score += 3
        if "pcs" in hint_l or "pro seller" in hint_l:
            if tpl["trigger_kind"] == "pcs_below_pct":
                score += 3
        if "new sku" in hint_l or "repricer" in hint_l:
            if tpl["action_kind"] == "enroll_in_repricer":
                score += 3
        if "margin" in hint_l or "profit" in hint_l:
            if tpl["trigger_kind"] == "high_margin_and_no_buybox":
                score += 3
        if "pause" in hint_l or "stock" in hint_l:
            if tpl["action_kind"] == "pause_listing":
                score += 3
        scored.append((score, i, tpl))
    scored.sort(key=lambda x: -x[0])
    top = [(i, tpl) for s, i, tpl in scored if s > 0][:3]
    if not top:
        top = [(i, tpl) for s, i, tpl in scored[:3]]

    tpl_cards = "".join(
        f'<a href="/agent/rules/new/{i}" class="block bg-white rounded-lg border border-wmgray-30 hover:border-marty-100 p-2.5 transition">'
        f'<div class="flex items-start gap-2">'
        f'<span class="text-base">{tpl["icon"]}</span>'
        f'<div class="flex-1 min-w-0">'
        f'<div class="text-[12px] font-bold text-wmgray-160 leading-tight">{html.escape(tpl["name"])}</div>'
        f'<div class="text-[11px] text-wmgray-100 leading-snug mt-0.5">{html.escape(tpl["why"][:90])}{"…" if len(tpl["why"]) > 90 else ""}</div>'
        f'</div></div></a>'
        for i, tpl in top
    )
    return _marty(f'''
    <div class="font-bold text-wmgray-160">📜 Let\'s create a rule for that.</div>
    <div class="text-[12px]">Here are my best-matching templates — click to customize the trigger, action, and exclusions:</div>
    {tpl_cards}
    <div class="flex gap-1.5 pt-1">
      {_link_btn("Browse all templates", "/agent/rules/new")}
    </div>
    {_suggestions([
        ("List my active rules", "What rules do I have?"),
        ("Daily digest", "Show me what you did today"),
    ])}
    ''')


def reply_community_panel() -> str:
    """Show what other sellers are asking right now — the social-proof intent."""
    chips = "".join(
        f'<button onclick="askMarty({_js_escape(q.query)})" '
        f'class="w-full text-left px-3 py-2 rounded-lg border border-wmgray-30 hover:border-marty-100 hover:bg-marty-5 text-[12px] transition">'
        f'<span class="text-base mr-2">{q.icon}</span>'
        f'<strong class="text-wmgray-160">{html.escape(q.query[:50])}{"…" if len(q.query) > 50 else ""}</strong>'
        f'<span class="text-[10px] text-wmgray-100 ml-2">×{q.count} sellers</span>'
        f'{f"<div class=\"text-[10px] text-wmgray-100 mt-0.5 ml-7\">{html.escape(q.translated)}</div>" if q.translated else ""}'
        f'</button>'
        for q in COMMUNITY_QUERIES[:6]
    )
    return _marty(f'''
    <div class="font-bold text-wmgray-160">👥 Sellers like you have been asking…</div>
    <div class="text-[12px] text-wmgray-100">Top 6 questions from the seller community this month — across English, Chinese, and Turkish. Click any to run it.</div>
    <div class="space-y-1.5">{chips}</div>
    ''')


def _js_escape(s: str) -> str:
    """Escape a string for use inside a single-quoted JS function arg in HTML."""
    safe = s.replace("\\", "\\\\").replace("'", "\\'").replace("\"", "&quot;")
    return f"'{safe}'"


# ---------- Multi-language detection ----------

_CJK_RE = re.compile(r'[\u4e00-\u9fff]')
_TR_RE = re.compile(r'[\u011e\u011f\u0130\u0131\u015e\u015f\u00c7\u00e7\u00d6\u00f6\u00dc\u00fc]')


def _detect_lang(message: str) -> str:
    if _CJK_RE.search(message):
        return "zh"
    if _TR_RE.search(message):
        return "tr"
    return "en"


LANG_BANNERS = {
    "zh": ("🌏 I see you asked in Chinese —", "Detected: Chinese (中文)"),
    "tr": ("🌏 I see you asked in Turkish —", "Detected: Turkish (Türkçe)"),
}


def _lang_banner(lang: str, translated_hint: str = "") -> str:
    if lang == "en":
        return ""
    title, sub = LANG_BANNERS.get(lang, ("🌏 Detected non-English message", ""))
    hint = f'<div class="text-[11px] text-wmgray-130 italic mt-1">I\'m treating your question as: “{html.escape(translated_hint)}”</div>' if translated_hint else ""
    return (
        f'<div class="bg-marty-5 border border-marty-100/30 rounded-lg px-2.5 py-1.5 text-[11px]">'
        f'<div class="font-bold text-marty-130">{title}</div>'
        f'<div class="text-wmgray-100">{sub}</div>'
        f'{hint}</div>'
    )


# ---------- Routes ----------

INTENT_PATTERNS: list[tuple[re.Pattern, Callable[[re.Match], str]]] = [
    # === Rules intents (very specific so they don\'t collide) ===
    (re.compile(r'\b(create|make|set up|add|build).{0,15}rule\b(.*)', re.I),
     lambda m: reply_create_rule(m.group(2) if m.lastindex and m.lastindex >= 2 else "")),
    (re.compile(r'\b(?:what|which|list|show|see)\b.{0,15}\b(?:rules|repricing rules|standing rules)\b', re.I),
     lambda m: reply_rules_overview()),
    (re.compile(r'\b(my )?(active )?(repricing )?rules?\b', re.I),
     lambda m: reply_rules_overview()),

    # === Real seller queries (highest-volume from Smart Filters telemetry) ===
    # NOTE: more-specific compound patterns must come BEFORE the generic ones.
    (re.compile(r'(aged.{0,20}buy.?box|aged.{0,20}losing|aging.{0,20}losing|\u957f\u671f\u5e93\u5b58|old.{0,10}inventory.{0,15}buy.?box|aged.{0,5}inventory)', re.I),
     lambda m: reply_aged_and_losing_buybox()),
    (re.compile(r'(wfs.{0,15}(?:no|without).{0,5}buy.?box|wfs.{0,5}and.{0,5}have.{0,5}no.{0,5}buy.?box)', re.I),
     lambda m: reply_wfs_no_buybox()),
    (re.compile(r'(losing.{0,5}buy.?box|lose.{0,5}buy.?box|lost.{0,5}buy.?box|\u5931\u53bb.?buybox|\u5931\u53bb.?buy.?box)', re.I),
     lambda m: reply_losing_buybox()),
    (re.compile(r'(repricer|enroll.{0,15}repricer|repricer.{0,15}enroll)', re.I),
     lambda m: reply_repricer_enrollment()),
    (re.compile(r'(high.{0,5}traffic.{0,5}(?:and|but).{0,5}low.{0,5}sales|\u6d41\u91cf\u9ad8|high.{0,5}view.{0,5}low|traffic.{0,5}low.{0,5}conver)', re.I),
     lambda m: reply_high_traffic_low_sales()),
    (re.compile(r'(high.?margin|high.?profit|kar.?elde|\u9ad8\u5229\u6da6)', re.I),
     lambda m: reply_high_margin()),
    (re.compile(r'(buy.?box.{0,10}ineligib|reason.{0,5}for.{0,5}buy.?box|why.{0,10}no.{0,5}buy.?box|why.{0,10}lose.{0,5}buy.?box)', re.I),
     lambda m: reply_buybox_ineligibility()),
    (re.compile(r'(price.{0,5}not.{0,5}competitive|not.{0,5}competitive|uncompetitive|\u4ef7\u683c\u6ca1\u6709\u7ade\u4e89\u529b)', re.I),
     lambda m: reply_buybox_ineligibility()),
    (re.compile(r'(what.{0,5}(?:are|do).{0,5}other.{0,5}sellers|community.{0,5}quer|sellers.{0,5}asking|popular.{0,5}quer)', re.I),
     lambda m: reply_community_panel()),

    # === Original Wave C intents ===
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
    # Multi-language detection — prepend a banner if non-English
    lang = _detect_lang(message)
    translated_hint = ""
    if lang != "en":
        # Try to find a community query that matches and use its translation
        for q in COMMUNITY_QUERIES:
            if q.lang == lang and q.translated and any(part in message for part in q.query.split() if len(part) > 1):
                translated_hint = q.translated
                break
        if not translated_hint:
            # Fallback rough heuristics
            ml = message.lower()
            if "流量高" in ml or "销售额低" in ml:
                translated_hint = "Products with high traffic but low sales"
            elif "长期库存" in ml or "库存滞销" in ml:
                translated_hint = "Aged inventory items losing Buy Box"
            elif "buybox" in ml or "buy box" in ml or "失去" in ml:
                translated_hint = "Items losing the Buy Box"
            elif "kar" in ml or "yüksek" in ml:
                translated_hint = "Items with high profit margin"

    banner = _lang_banner(lang, translated_hint)

    for pattern, handler in INTENT_PATTERNS:
        m = pattern.search(message)
        if m:
            try:
                reply = handler(m)
                if banner:
                    # Splice banner into the Marty bubble's space-y-2 div
                    reply = reply.replace('<div class="bg-wmgray-5 rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] leading-snug text-[13px] text-wmgray-130 space-y-2">',
                                          '<div class="bg-wmgray-5 rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] leading-snug text-[13px] text-wmgray-130 space-y-2">' + banner, 1)
                return reply
            except Exception as e:  # pragma: no cover — defensive
                return _marty(f"Hmm, I tripped on that one. ({html.escape(str(e))})")
    fallback = reply_default(message)
    if banner:
        fallback = fallback.replace('<div class="bg-wmgray-5 rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] leading-snug text-[13px] text-wmgray-130 space-y-2">',
                                    '<div class="bg-wmgray-5 rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] leading-snug text-[13px] text-wmgray-130 space-y-2">' + banner, 1)
    return fallback


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

    if action == "bulk_approve_buybox":
        # Approve all needs_approval buybox-related actions
        buybox = [a for a in actions_by_status("needs_approval")
                  if a.action_type in ("buybox_match", "buybox_beat_by_cent", "spip_unsuppress")]
        ids = [a.id for a in buybox]
        count = bulk_approve(ids)
        total = sum(a.expected_gmv_lift_usd for a in buybox)
        return HTMLResponse(_marty(f'''
        <div>✅ Approved <strong>{count}</strong> Buy Box recovery action{"s" if count != 1 else ""} —
        projected <strong class="text-wmgreen-130">+${total:,.0f}</strong> over 30 days.</div>
        <div class="text-[11px] text-wmgray-100">All reversible from <a href="/agent/history" class="text-marty-100 font-bold hover:underline">action history</a>.</div>
        '''))

    if action == "stage_aged_buybox_plan":
        # Future: would compose 3 plan actions. For demo, acknowledge.
        return HTMLResponse(_marty('''
        <div>✅ Staged the 3-step plan for the aged-inventory cohort.</div>
        <div class="text-[12px] text-wmgray-100">You\'ll see the markdown actions in your <a href="/agent/inbox?cohort=inventory_risk" class="text-marty-100 font-bold hover:underline">inbox</a> within a minute, ready for bulk-approve.</div>
        '''))

    if action == "noop":
        return HTMLResponse(_marty("👍 No worries, nothing changed."))

    return HTMLResponse(_marty("Hmm, I didn't catch that."))
