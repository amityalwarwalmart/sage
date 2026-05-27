"""Policy & Guardrails — setup wizard + ongoing settings view.

Wizard (4 steps, per PRD §11 'four-step progression'):
  1. Goals (multi-select)
  2. Hard guardrails (floors, velocity caps, MAP/MSRP)
  3. Cohorts (opt-in / always-ask)
  4. Mode (Shadow → Recommend → Autopilot) + review

After completion, /agent/policy serves the settings view for ongoing edits.
"""
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.data.marty import MODE_META, POLICY, TIER_META, actions_by_status
from app.templates_env import templates

router = APIRouter()

GOAL_META = {
    "maximize_buybox": {"icon": "🎯", "label": "Maximize Buy Box share",
                        "desc": "Win the 'Add to Cart' button on more searches"},
    "protect_margin":  {"icon": "📉", "label": "Protect margin",
                        "desc": "Never sacrifice profit per item for top-line"},
    "liquidate_aged":  {"icon": "🐢", "label": "Liquidate aged inventory",
                        "desc": "Move slow-movers before storage fees pile up"},
    "price_stability": {"icon": "🎚️", "label": "Price stability",
                        "desc": "Minimize how often prices change, even if it costs some Buy Box"},
}


@router.get("/agent/policy")
async def policy_view(request: Request):
    # If not yet set up, redirect to wizard step 1
    if not POLICY.setup_complete:
        return RedirectResponse("/agent/policy/setup/1", status_code=303)
    return templates.TemplateResponse(request=request, name="agent_policy.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "policy",
        "needs_approval_count": sum(1 for x in actions_by_status("needs_approval")),
        "policy": POLICY,
        "mode_meta": MODE_META[POLICY.mode],
        "tier_meta": TIER_META,
        "goal_meta": GOAL_META,
        "all_modes": MODE_META,
    })


@router.get("/agent/policy/setup/{step}")
async def wizard_step(request: Request, step: int):
    if step < 1 or step > 4:
        raise HTTPException(404)
    POLICY.setup_step = step
    return templates.TemplateResponse(request=request, name="agent_policy_wizard.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "policy",
        "needs_approval_count": sum(1 for x in actions_by_status("needs_approval")),
        "policy": POLICY,
        "step": step,
        "total_steps": 4,
        "goal_meta": GOAL_META,
        "all_modes": MODE_META,
    })


@router.post("/agent/policy/setup/1")
async def save_step_1(goals: list[str] = Form(default=["maximize_buybox", "protect_margin"])):
    POLICY.goals = goals  # type: ignore[assignment]
    return RedirectResponse("/agent/policy/setup/2", status_code=303)


@router.post("/agent/policy/setup/2")
async def save_step_2(
    min_margin_pct: int = Form(default=15),
    max_daily_movement_pct: int = Form(default=10),
    respect_map: bool = Form(default=False),
    respect_msrp: bool = Form(default=False),
):
    POLICY.min_margin_pct = min_margin_pct
    POLICY.max_daily_movement_pct = max_daily_movement_pct
    POLICY.respect_map = respect_map
    POLICY.respect_msrp = respect_msrp
    return RedirectResponse("/agent/policy/setup/3", status_code=303)


@router.post("/agent/policy/setup/3")
async def save_step_3(
    enrolled_cohorts: list[str] = Form(default=[]),
    excluded_cohorts: list[str] = Form(default=[]),
):
    for c in POLICY.cohorts:
        c.enrolled = c.key in enrolled_cohorts
        c.excluded = c.key in excluded_cohorts
    return RedirectResponse("/agent/policy/setup/4", status_code=303)


@router.post("/agent/policy/setup/4")
async def save_step_4(mode: str = Form(default="shadow")):
    if mode in ("shadow", "recommend", "autopilot"):
        POLICY.mode = mode  # type: ignore[assignment]
    POLICY.setup_complete = True
    return RedirectResponse("/", status_code=303)


@router.post("/agent/policy/reset")
async def reset_setup():
    POLICY.setup_complete = False
    POLICY.setup_step = 1
    return RedirectResponse("/agent/policy/setup/1", status_code=303)
