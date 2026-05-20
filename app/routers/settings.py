from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.data.mock import SETTINGS, kpi_summary
from app.templates_env import templates

router = APIRouter()


@router.get("/settings")
async def view_settings(request: Request):
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "request": request,
        "active_page": "settings",
        "s": SETTINGS,
        "open_opps_count": kpi_summary()["open_opps"],
    })


@router.post("/settings")
async def update_settings(
    auto_approve_enabled: str = Form(default=""),
    auto_approve_max_usd: float = Form(default=500.0),
    auto_approve_min_confidence: int = Form(default=85),
    daily_action_cap: int = Form(default=1000),
    paused: list[str] = Form(default=[]),
    require_clearance: str = Form(default=""),
    require_ad_spend: str = Form(default=""),
    require_bulk_content: str = Form(default=""),
):
    SETTINGS.auto_approve_enabled = bool(auto_approve_enabled)
    SETTINGS.auto_approve_max_usd = auto_approve_max_usd
    SETTINGS.auto_approve_min_confidence = auto_approve_min_confidence
    SETTINGS.daily_action_cap = daily_action_cap
    SETTINGS.paused_capabilities = paused  # type: ignore
    SETTINGS.require_approval_for_clearance = bool(require_clearance)
    SETTINGS.require_approval_for_ad_spend = bool(require_ad_spend)
    SETTINGS.require_approval_for_bulk_content = bool(require_bulk_content)
    return RedirectResponse("/settings", status_code=303)
