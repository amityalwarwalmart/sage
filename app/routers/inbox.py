from fastapi import APIRouter, Request

from app.data.mock import OPPORTUNITIES, kpi_summary
from app.templates_env import templates

router = APIRouter()


@router.get("/inbox")
async def inbox(request: Request, category: str | None = None, risk: str | None = None):
    opps = [o for o in OPPORTUNITIES.values() if o.status == "new"]
    if category and category != "all":
        opps = [o for o in opps if o.category == category]
    if risk and risk != "all":
        opps = [o for o in opps if o.risk_tier == risk]
    opps = sorted(opps, key=lambda o: o.gmv_impact_usd, reverse=True)
    kpi = kpi_summary()
    return templates.TemplateResponse(request=request, name="inbox.html", context={
        "request": request,
        "active_page": "inbox",
        "opps": opps,
        "category": category or "all",
        "risk": risk or "all",
        "open_opps_count": kpi["open_opps"],
    })
