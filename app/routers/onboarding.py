"""Onboarding wizard — 3 micro-steps optimized for completion.

Each step has a smart default pre-selected. Seller can hit Continue
without changing anything. ~30 seconds to complete.
"""
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.data.mock import ONBOARDING, apply_onboarding_to_settings, kpi_summary
from app.templates_env import templates

router = APIRouter()


@router.get("/onboarding")
async def onboarding_start(request: Request):
    # Always start from step 1
    ONBOARDING.current_step = 1
    return RedirectResponse("/onboarding/1", status_code=303)


@router.get("/onboarding/{step}")
async def onboarding_step(request: Request, step: int):
    ONBOARDING.current_step = step
    return templates.TemplateResponse(request=request, name="onboarding.html", context={
        "request": request,
        "active_page": "onboarding",
        "ob": ONBOARDING,
        "step": step,
        "total_steps": 3,
        "open_opps_count": kpi_summary()["open_opps"],
    })


@router.post("/onboarding/1")
async def onboarding_save_step1(goal: str = Form(default="both")):
    ONBOARDING.goal = goal  # type: ignore
    return RedirectResponse("/onboarding/2", status_code=303)


@router.post("/onboarding/2")
async def onboarding_save_step2(autonomy: str = Form(default="handle_small")):
    ONBOARDING.autonomy = autonomy  # type: ignore
    return RedirectResponse("/onboarding/3", status_code=303)


@router.post("/onboarding/3")
async def onboarding_save_step3(
    min_margin_pct: int = Form(default=15),
    focus_areas: list[str] = Form(default=["pricing", "catalog", "incentives", "seo"]),
):
    ONBOARDING.min_margin_pct = min_margin_pct
    ONBOARDING.focus_areas = focus_areas  # type: ignore
    ONBOARDING.completed = True
    apply_onboarding_to_settings()
    return RedirectResponse("/setup-scan", status_code=303)


@router.post("/onboarding/reset")
async def onboarding_reset():
    """Used in demo to restart the journey."""
    ONBOARDING.completed = False
    ONBOARDING.current_step = 1
    ONBOARDING.goal = None
    ONBOARDING.autonomy = None
    return RedirectResponse("/onboarding", status_code=303)
