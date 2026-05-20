from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.data.mock import AUDIT_LOG, kpi_summary
from app.templates_env import templates

router = APIRouter()


@router.get("/audit")
async def audit_log(request: Request, actor: str | None = None):
    entries = AUDIT_LOG
    if actor and actor != "all":
        entries = [e for e in entries if e.actor == actor]
    return templates.TemplateResponse(request=request, name="audit.html", context={
        "request": request,
        "active_page": "sage", "sub_page": "audit",
        "entries": entries,
        "actor": actor or "all",
        "open_opps_count": kpi_summary()["open_opps"],
    })


@router.post("/audit/{entry_id}/revert")
async def revert(entry_id: str):
    for e in AUDIT_LOG:
        if e.id == entry_id:
            e.reverted = True
            break
    return RedirectResponse("/audit", status_code=303)
