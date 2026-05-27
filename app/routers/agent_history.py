"""Action history — full audit log with rollback per action.

Per PRD §6: "Full audit log + plain-English reasoning trace per action"
+ "one-click rollback (single action or batch)".
"""
from fastapi import APIRouter, Request

from app.data.marty import ACTIONS, AUDIT, MODE_META, POLICY, action_by_id, actions_by_status
from app.templates_env import templates

router = APIRouter()


@router.get("/agent/history")
async def history(request: Request):
    # Audit events with their actions attached
    enriched = []
    for e in AUDIT:
        a = action_by_id(e.action_id)
        if a:
            enriched.append((e, a))

    return templates.TemplateResponse(request=request, name="agent_history.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "history",
        "needs_approval_count": sum(1 for x in actions_by_status("needs_approval")),
        "policy": POLICY,
        "mode_meta": MODE_META[POLICY.mode],
        "events": enriched,
        "total_actions": len(ACTIONS),
        "events_count": len(enriched),
    })
