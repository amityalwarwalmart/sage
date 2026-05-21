"""Sage workspace — the 'visualize + act' surface.

A 2x3 live tile grid showing health/inventory/compliance/sales/ads/search
status all in one place. Each tile drills into a related Sage opportunity.
"""
from fastapi import APIRouter, Request

from app.data.mock import WORKSPACE_TILES, kpi_summary
from app.templates_env import templates

router = APIRouter()


@router.get("/workspace")
async def workspace(request: Request):
    tiles = WORKSPACE_TILES
    alerts = sum(1 for t in tiles if t.status == "alert")
    warns = sum(1 for t in tiles if t.status == "warn")
    goods = sum(1 for t in tiles if t.status == "good")
    return templates.TemplateResponse(request=request, name="workspace.html", context={
        "request": request,
        "active_page": "sage",
        "sub_page": "workspace",
        "tiles": tiles,
        "alerts": alerts,
        "warns": warns,
        "goods": goods,
        "open_opps_count": kpi_summary()["open_opps"],
    })
