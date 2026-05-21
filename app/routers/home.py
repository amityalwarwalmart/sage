from fastapi import APIRouter, Request

from app.data.mock import GUARDRAILS, ONBOARDING, OPPORTUNITIES, kpi_summary, opps_by_category
from app.templates_env import templates

router = APIRouter()


@router.get("/")
async def home(request: Request):
    kpi = kpi_summary()
    by_cat = opps_by_category()
    top_opps = sorted(
        [o for o in OPPORTUNITIES.values() if o.status == "new"],
        key=lambda o: o.gmv_impact_usd,
        reverse=True,
    )[:3]
    return templates.TemplateResponse(request=request, name="home.html", context={
        "request": request,
        "active_page": "sage", "sub_page": "home",
        "kpi": kpi,
        "by_cat": by_cat,
        "top_opps": top_opps,
        "open_opps_count": kpi["open_opps"],
        "rules_count": len([g for g in GUARDRAILS.values() if g.has_floor or g.has_ceiling]),
        "ob": ONBOARDING,
    })
