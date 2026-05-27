"""Marty Pricing Agent — FastAPI app entrypoint.

Wave A: only the agent overview + mode toggle + stubs are wired.
Wave B will add the inbox, policy wizard, action detail.
Wave C will fill in Marty chat with the killer flows.
"""
from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.data.marty import POLICY, set_mode
from app.routers import agent_overview
from app.templates_env import templates

app = FastAPI(title="Marty Pricing Agent · Walmart Seller Center")

# ---------- Static (optional — falls back gracefully if missing) ----------
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception:
    pass

# ---------- Wave A: overview + mode ----------
app.include_router(agent_overview.router)


# Mode toggle (PRD: Shadow → Recommend → Autopilot)
@app.post("/agent/mode")
async def change_mode(mode: str = Form(...)):
    if mode in ("shadow", "recommend", "autopilot"):
        set_mode(mode)
    return RedirectResponse("/", status_code=303)


# ---------- Stub router for Wave B/C surfaces ----------
stubs = APIRouter()


@stubs.get("/agent/inbox")
@stubs.get("/agent/policy")
@stubs.get("/agent/history")
async def stub(request: Request):
    path = request.url.path
    label = {
        "/agent/inbox":   ("Agent inbox",          "Auto-executed · Needs approval · Dismissed tabs with cohort filters."),
        "/agent/policy":  ("Policy & guardrails",  "Setup wizard: goals, floors, velocity caps, MAP/MSRP, hero-SKU exclusions, blackout dates."),
        "/agent/history": ("Action history",       "Full audit log with one-click rollback + shadow-mode counterfactual."),
    }.get(path, ("Coming soon", ""))
    return templates.TemplateResponse(request=request, name="stub.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": path.split("/")[-1],
        "title": label[0],
        "blurb": label[1],
    })


@stubs.get("/agent/action/{aid}")
async def action_stub(request: Request, aid: str):
    from app.data.marty import action_by_id
    a = action_by_id(aid)
    return templates.TemplateResponse(request=request, name="stub.html", context={
        "request": request,
        "active_page": "pricing",
        "sub_page": "agent",
        "active_sub_sub": "inbox",
        "title": f"Action detail · {aid}",
        "blurb": f"Coming in Wave B. Will show market signal, guardrail checks, simulation, and approve/reject/rollback controls for: {a.item_name if a else aid}",
    })


@stubs.post("/marty/chat")
async def marty_chat_stub(message: str = Form(...)):
    from fastapi.responses import HTMLResponse
    import html
    return HTMLResponse(f'''
    <div class="flex gap-2 justify-end">
      <div class="bg-marty-100 text-white rounded-2xl rounded-tr-md px-3.5 py-2.5 max-w-[85%] leading-snug text-[13px]">{html.escape(message)}</div>
    </div>
    <div class="flex gap-2">
      <div class="w-7 h-7 rounded-xl marty-orb flex-shrink-0"></div>
      <div class="bg-wmgray-5 rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] leading-snug text-[13px]">
        Killer chat flows coming in Wave C — "Show me what the agent did today" (daily digest), bulk approvals, and per-action explanations. For now, head to the
        <a href="/agent/inbox" class="text-marty-100 font-bold hover:underline">agent inbox</a>.
      </div>
    </div>
    ''')


app.include_router(stubs)
