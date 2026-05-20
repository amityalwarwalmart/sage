"""Price rules — per-item min/max guardrails Sage will never cross."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.data.mock import GUARDRAILS, SETTINGS, kpi_summary
from app.templates_env import templates

router = APIRouter()


@router.get("/rules")
async def rules(request: Request):
    rules_list = sorted(GUARDRAILS.values(), key=lambda g: g.item_name.lower())
    return templates.TemplateResponse(request=request, name="rules.html", context={
        "request": request,
        "active_page": "sage",
        "sub_page": "rules",
        "rules": rules_list,
        "s": SETTINGS,
        "open_opps_count": kpi_summary()["open_opps"],
    })


@router.post("/rules/defaults")
async def update_defaults(
    default_min_margin_pct: int = Form(default=15),
    default_max_discount_pct: int = Form(default=30),
    default_max_increase_pct: int = Form(default=20),
    enforce_floors: str = Form(default=""),
    enforce_ceilings: str = Form(default=""),
):
    SETTINGS.default_min_margin_pct = default_min_margin_pct
    SETTINGS.default_max_discount_pct = default_max_discount_pct
    SETTINGS.default_max_increase_pct = default_max_increase_pct
    SETTINGS.enforce_floors = bool(enforce_floors)
    SETTINGS.enforce_ceilings = bool(enforce_ceilings)
    return RedirectResponse("/rules", status_code=303)


@router.post("/rules/{sku}")
async def update_rule(
    sku: str,
    floor: str = Form(default=""),
    ceiling: str = Form(default=""),
    cost: str = Form(default=""),
):
    rule = GUARDRAILS.get(sku)
    if rule is None:
        return RedirectResponse("/rules", status_code=303)

    def _parse(v: str) -> float | None:
        v = v.strip().replace("$", "").replace(",", "")
        if not v:
            return None
        try:
            return float(v)
        except ValueError:
            return None

    rule.floor = _parse(floor)
    rule.ceiling = _parse(ceiling)
    new_cost = _parse(cost)
    if new_cost is not None:
        rule.cost = new_cost
    return RedirectResponse("/rules", status_code=303)
