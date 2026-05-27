"""Pricing Agent Inbox — the prioritized triage surface.

Tabs: Auto-executed | Needs approval | Dismissed | Blocked
Filters: cohort, tier, action type
Bulk actions: approve, reject
Inline action: each row clicks through to /agent/action/{id}
"""
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse

from app.data.marty import (
    ACTION_TYPE_META,
    ACTIONS,
    MODE_META,
    POLICY,
    TIER_META,
    actions_by_status,
    bulk_approve,
    bulk_reject,
    run_stats,
)
from app.templates_env import templates

router = APIRouter()


TABS = [
    ("needs_approval", "Needs your approval", "🟡", "spark-140"),
    ("auto_executed", "Auto-executed",        "🟢", "wmgreen-130"),
    ("blocked",       "Blocked",              "🛡️", "wmred-130"),
    ("rejected",      "Dismissed",            "✖️", "wmgray-100"),
]


@router.get("/agent/inbox")
async def inbox(
    request: Request,
    tab: str = Query(default="needs_approval"),
    cohort: str = Query(default="all"),
    tier: str = Query(default="all"),
    action_type: str = Query(default="all"),
):
    if tab not in [t[0] for t in TABS]:
        tab = "needs_approval"

    rows = actions_by_status(tab)  # type: ignore[arg-type]

    if cohort != "all":
        rows = [a for a in rows if a.cohort == cohort]
    if tier != "all":
        rows = [a for a in rows if a.risk_tier == tier]
    if action_type != "all":
        rows = [a for a in rows if a.action_type == action_type]

    # Tab counts (unfiltered)
    tab_counts = {t[0]: len(actions_by_status(t[0])) for t in TABS}  # type: ignore[arg-type]

    # Cohort options derived from POLICY
    cohort_opts = [("all", f"All cohorts ({sum(1 for a in actions_by_status(tab))})")]  # type: ignore[arg-type]
    for c in POLICY.cohorts:
        cnt = sum(1 for a in actions_by_status(tab) if a.cohort == c.key)  # type: ignore[arg-type]
        if cnt > 0:
            cohort_opts.append((c.key, f"{c.label} ({cnt})"))

    # Action type filter options (only ones that exist in current tab)
    action_types_present = sorted({a.action_type for a in actions_by_status(tab)})  # type: ignore[arg-type]
    action_type_opts = [("all", "All action types")] + [
        (at, ACTION_TYPE_META[at]["label"]) for at in action_types_present
    ]

    return templates.TemplateResponse(request=request, name="agent_inbox.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "inbox",
        "needs_approval_count": tab_counts.get("needs_approval", 0),
        "policy": POLICY,
        "mode_meta": MODE_META[POLICY.mode],
        "tier_meta": TIER_META,
        "tab": tab,
        "tabs": TABS,
        "tab_counts": tab_counts,
        "rows": rows,
        "row_count": len(rows),
        "cohort_opts": cohort_opts,
        "action_type_opts": action_type_opts,
        "selected_cohort": cohort,
        "selected_tier": tier,
        "selected_action_type": action_type,
        "stats": run_stats(),
        "total_pending_gmv": sum(a.expected_gmv_lift_usd for a in actions_by_status("needs_approval")),
    })


@router.post("/agent/inbox/bulk")
async def inbox_bulk(
    op: str = Form(...),
    action_ids: list[str] = Form(default=[]),
    tab: str = Form(default="needs_approval"),
):
    if op == "approve":
        bulk_approve(action_ids)
    elif op == "reject":
        bulk_reject(action_ids, note="Bulk-rejected from inbox")
    return RedirectResponse(f"/agent/inbox?tab={tab}", status_code=303)
