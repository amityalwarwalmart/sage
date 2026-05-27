"""Pricing Agent Overview — the new landing page for the Pricing Agent.

Replaces the old Sage home page. Lives at `/` (inside Seller Center, under
Pricing → Pricing Agent → Agent overview).
"""
from fastapi import APIRouter, Request

from app.data.marty import (
    ACTIONS,
    MODE_META,
    POLICY,
    TIER_META,
    actions_by_status,
    actions_by_tier,
    run_stats,
)
from app.templates_env import templates

router = APIRouter()


@router.get("/")
async def agent_overview(request: Request):
    stats = run_stats()
    needs_approval = actions_by_status("needs_approval")
    auto_executed_today = actions_by_status("auto_executed")
    blocked = actions_by_status("blocked")

    return templates.TemplateResponse(request=request, name="agent_overview.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "overview",
        "needs_approval_count": len(needs_approval),
        "stats": stats,
        "policy": POLICY,
        "mode_meta": MODE_META[POLICY.mode],
        "all_modes": MODE_META,
        "tier_meta": TIER_META,
        "needs_approval": needs_approval[:4],  # preview only
        "auto_executed": auto_executed_today[:4],
        "blocked": blocked[:3],
        "total_actions": len(ACTIONS),
        "low_tier_count": len(actions_by_tier("low")),
        "med_tier_count": len(actions_by_tier("medium")),
        "high_tier_count": len(actions_by_tier("high")),
    })
