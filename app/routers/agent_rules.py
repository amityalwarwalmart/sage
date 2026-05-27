"""Repricing Rules — the catalog-level WHEN→THEN layer.

Walmart doesn't ship rule-builders natively today. Marty does.
Every rule respects the same policy guardrails, cohort exclusions,
and audit trail as one-time actions. Risk-tiered per action.
"""
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.data.marty import (
    ACTION_KIND_META,
    AUDIT,
    MODE_META,
    POLICY,
    RULE_TEMPLATES,
    RULES,
    TIER_META,
    TRIGGER_META,
    AuditEvent,
    RepricingRule,
    actions_by_status,
    add_rule,
    delete_rule,
    rule_by_id,
    suggested_rules,
    toggle_rule_status,
)
from app.templates_env import templates
from datetime import datetime
from app.data.marty import _aid

router = APIRouter()


# ============================================================
# LIST page — /agent/rules
# ============================================================

@router.get("/agent/rules")
async def rules_list(request: Request):
    actives  = [r for r in RULES if r.status == "active"]
    paused   = [r for r in RULES if r.status == "paused"]
    shadow   = [r for r in RULES if r.status == "shadow"]
    drafts   = [r for r in RULES if r.status == "draft"]

    return templates.TemplateResponse(request=request, name="agent_rules.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "rules",
        "needs_approval_count": sum(1 for x in actions_by_status("needs_approval")),
        "policy": POLICY,
        "mode_meta": MODE_META[POLICY.mode],
        "rules": RULES,
        "actives": actives,
        "paused": paused,
        "shadow": shadow,
        "drafts": drafts,
        "tier_meta": TIER_META,
        "suggestions": suggested_rules(),
        "templates_list": RULE_TEMPLATES,
        # Headline stats
        "total_rules": len(RULES),
        "active_count": len(actives),
        "total_actions_fired_7d": sum(r.actions_fired_7d for r in RULES),
        "total_gmv_impact_7d": sum(r.gmv_impact_7d_usd for r in RULES),
        "total_units_moved_7d": sum(r.units_moved_7d for r in RULES),
        "total_affected_today": sum(r.affected_skus_today for r in RULES),
    })


# ============================================================
# CREATE wizard — must be declared BEFORE /agent/rules/{rid}
# because FastAPI matches routes in declaration order and
# 'new' would otherwise be captured as a rule id.
# ============================================================

@router.get("/agent/rules/new")
async def rules_new_gallery(request: Request):
    return templates.TemplateResponse(request=request, name="agent_rule_wizard.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "rules",
        "needs_approval_count": sum(1 for x in actions_by_status("needs_approval")),
        "step": "gallery",
        "templates_list": RULE_TEMPLATES,
        "policy": POLICY,
        "tier_meta": TIER_META,
    })


@router.get("/agent/rules/new/{template_idx}")
async def rules_new_customize(request: Request, template_idx: int):
    if template_idx < 0 or template_idx >= len(RULE_TEMPLATES):
        raise HTTPException(404)
    tpl = RULE_TEMPLATES[template_idx]
    return templates.TemplateResponse(request=request, name="agent_rule_wizard.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "rules",
        "needs_approval_count": sum(1 for x in actions_by_status("needs_approval")),
        "step": "customize",
        "tpl": tpl,
        "template_idx": template_idx,
        "policy": POLICY,
        "tier_meta": TIER_META,
        "trigger_meta_lookup": TRIGGER_META,
        "action_meta_lookup": ACTION_KIND_META,
    })


@router.post("/agent/rules/new/{template_idx}")
async def rules_new_save(
    template_idx: int,
    name: str = Form(...),
    trigger_value: float = Form(...),
    action_value: float = Form(default=0),
    cohort: str = Form(default="all_enrolled"),
    brand_filter: str = Form(default=""),
    exclude_hero_skus: bool = Form(default=True),
    exclude_new_skus: bool = Form(default=True),
    exclude_below_cost: bool = Form(default=True),
    start_mode: str = Form(default="shadow"),
):
    if template_idx < 0 or template_idx >= len(RULE_TEMPLATES):
        raise HTTPException(404)
    tpl = RULE_TEMPLATES[template_idx]
    rid = f"rule-{200 + len(RULES)}"
    new_rule = RepricingRule(
        id=rid,
        name=name,
        description=tpl.get("why", ""),
        status="shadow" if start_mode == "shadow" else "active",
        trigger_kind=tpl["trigger_kind"], trigger_value=trigger_value,
        cohort=cohort, brand_filter=brand_filter,
        action_kind=tpl["action_kind"], action_value=action_value or tpl.get("action_value", 0),
        exclude_hero_skus=exclude_hero_skus,
        exclude_new_skus=exclude_new_skus,
        exclude_below_cost=exclude_below_cost,
        risk_tier=tpl.get("risk_tier", "medium"),
        created_by="seller",
        created_at=datetime.now(),
    )
    add_rule(new_rule)
    AUDIT.insert(0, AuditEvent(
        id=_aid(), ts=datetime.now(), actor="seller", verb="approved",
        action_id=rid,
        summary=f"Created rule: {new_rule.name} (starts in {new_rule.status} mode)",
        note=new_rule.plain_english,
    ))
    return RedirectResponse(f"/agent/rules/{rid}?just_created=1", status_code=303)


# ============================================================
# DETAIL page — /agent/rules/{rid}
# (declared AFTER /agent/rules/new so 'new' isn't captured as id)
# ============================================================

@router.get("/agent/rules/{rid}")
async def rule_detail(request: Request, rid: str):
    r = rule_by_id(rid)
    if not r:
        raise HTTPException(404, f"Rule {rid} not found")

    return templates.TemplateResponse(request=request, name="agent_rule_detail.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "rules",
        "needs_approval_count": sum(1 for x in actions_by_status("needs_approval")),
        "rule": r,
        "policy": POLICY,
        "mode_meta": MODE_META[POLICY.mode],
        "trigger_meta": TRIGGER_META[r.trigger_kind],
        "action_meta": ACTION_KIND_META[r.action_kind],
        # Surface the most recent audit events that could plausibly be this rule firing
        "recent_firings": AUDIT[:6],
    })


@router.post("/agent/rules/{rid}/toggle")
async def rule_toggle(rid: str):
    r = rule_by_id(rid)
    toggle_rule_status(rid)
    if r:
        AUDIT.insert(0, AuditEvent(
            id=_aid(), ts=datetime.now(), actor="seller", verb="approved",
            action_id=rid,
            summary=f"{'Paused' if r.status == 'paused' else 'Activated'} rule: {r.name}",
            note="",
        ))
    return RedirectResponse("/agent/rules", status_code=303)


@router.post("/agent/rules/{rid}/delete")
async def rule_delete(rid: str):
    r = rule_by_id(rid)
    if r:
        AUDIT.insert(0, AuditEvent(
            id=_aid(), ts=datetime.now(), actor="seller", verb="rejected",
            action_id=rid, summary=f"Deleted rule: {r.name}", note="",
        ))
    delete_rule(rid)
    return RedirectResponse("/agent/rules", status_code=303)


# (Wizard routes moved above — to take precedence over /agent/rules/{rid})
