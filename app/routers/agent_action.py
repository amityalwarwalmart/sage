"""Action detail page — the 'explanation panel' the PRD §6 / research report call for.

Shows for a single PricingAction:
- Market signal (what changed)
- Reasoning narrative (why agent proposed this)
- Risk tier rationale
- Guardrail checks (each pass/block with detail)
- Expected impact + simulation
- Approve / Reject / Rollback controls (state-aware)
"""
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.data.marty import (
    AUDIT,
    MODE_META,
    POLICY,
    TIER_META,
    action_by_id,
    actions_by_status,
    approve_action,
    reject_action,
    rollback_action,
)
from app.templates_env import templates

router = APIRouter()


@router.get("/agent/action/{aid}")
async def action_detail(request: Request, aid: str):
    a = action_by_id(aid)
    if not a:
        raise HTTPException(404, f"Action {aid} not found")

    # Audit trail for this action
    related_events = [e for e in AUDIT if e.action_id == aid]

    return templates.TemplateResponse(request=request, name="agent_action.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "inbox",
        "needs_approval_count": sum(1 for x in actions_by_status("needs_approval")),
        "a": a,
        "policy": POLICY,
        "mode_meta": MODE_META[POLICY.mode],
        "tier_meta": TIER_META[a.risk_tier],
        "related_events": related_events,
    })


@router.post("/agent/action/{aid}/approve")
async def action_approve(aid: str, note: str = Form(default="")):
    approve_action(aid, note=note)
    return RedirectResponse(f"/agent/action/{aid}", status_code=303)


@router.post("/agent/action/{aid}/reject")
async def action_reject(aid: str, note: str = Form(default="")):
    reject_action(aid, note=note)
    return RedirectResponse(f"/agent/action/{aid}", status_code=303)


@router.post("/agent/action/{aid}/rollback")
async def action_rollback(aid: str, note: str = Form(default="")):
    rollback_action(aid, note=note)
    return RedirectResponse(f"/agent/action/{aid}", status_code=303)
