from fastapi import APIRouter, HTTPException, Request

from app.data.mock import OPPORTUNITIES, kpi_summary
from app.templates_env import templates

router = APIRouter()


@router.get("/runs")
async def runs_index(request: Request):
    recent = sorted(
        [o for o in OPPORTUNITIES.values() if o.status in ("executed", "rejected", "deferred")],
        key=lambda o: o.created_at, reverse=True,
    )
    return templates.TemplateResponse(request=request, name="runs_index.html", context={
        "request": request,
        "active_page": "sage", "sub_page": "runs",
        "recent": recent,
        "open_opps_count": kpi_summary()["open_opps"],
    })


@router.get("/runs/{opp_id}")
async def view_run(request: Request, opp_id: str):
    opp = OPPORTUNITIES.get(opp_id)
    if not opp:
        raise HTTPException(404)
    return templates.TemplateResponse(request=request, name="run.html", context={
        "request": request,
        "active_page": "sage", "sub_page": "runs",
        "opp": opp,
        "open_opps_count": kpi_summary()["open_opps"],
    })
