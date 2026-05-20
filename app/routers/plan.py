from datetime import datetime
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.data.mock import OPPORTUNITIES, append_audit, kpi_summary
from app.templates_env import templates

router = APIRouter()


@router.get("/plan/{opp_id}")
async def view_plan(request: Request, opp_id: str):
    opp = OPPORTUNITIES.get(opp_id)
    if not opp:
        raise HTTPException(404)
    return templates.TemplateResponse(request=request, name="plan.html", context={
        "request": request,
        "active_page": "sage", "sub_page": "inbox",
        "opp": opp,
        "open_opps_count": kpi_summary()["open_opps"],
    })


@router.post("/plan/{opp_id}/approve")
async def approve_plan(opp_id: str, excluded: list[str] = Form(default=[])):
    opp = OPPORTUNITIES.get(opp_id)
    if not opp:
        raise HTTPException(404)
    for ch in opp.proposed_changes:
        ch.excluded = ch.sku in excluded
    included = [c for c in opp.proposed_changes if not c.excluded]
    opp.status = "executed"
    realized = sum(c.sku_impact_usd for c in included)
    append_audit(
        actor="user",
        action=f"Approved {opp.category_label} batch",
        target=opp.title,
        detail=f"{len(included)}/{len(opp.proposed_changes)} changes applied via Sage",
        gmv=realized,
    )
    return RedirectResponse(f"/runs/{opp.id}", status_code=303)


@router.post("/plan/{opp_id}/reject")
async def reject_plan(opp_id: str):
    opp = OPPORTUNITIES.get(opp_id)
    if not opp:
        raise HTTPException(404)
    opp.status = "rejected"
    append_audit(
        actor="user",
        action=f"Rejected {opp.category_label} proposal",
        target=opp.title,
        detail="Sage will learn from this rejection",
        gmv=0.0,
    )
    return RedirectResponse("/inbox", status_code=303)


@router.post("/plan/{opp_id}/defer")
async def defer_plan(opp_id: str):
    opp = OPPORTUNITIES.get(opp_id)
    if not opp:
        raise HTTPException(404)
    opp.status = "deferred"
    return RedirectResponse("/inbox", status_code=303)
