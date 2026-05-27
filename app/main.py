"""Marty Pricing Agent — FastAPI app entrypoint."""
from fastapi import FastAPI, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.data.marty import set_mode
from app.routers import (
    agent_action,
    agent_history,
    agent_inbox,
    agent_overview,
    agent_policy,
)

app = FastAPI(title="Marty Pricing Agent · Walmart Seller Center")

# Static (graceful fallback if dir missing)
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception:
    pass

# Routers
app.include_router(agent_overview.router)
app.include_router(agent_inbox.router)
app.include_router(agent_action.router)
app.include_router(agent_policy.router)
app.include_router(agent_history.router)


@app.post("/agent/mode")
async def change_mode(mode: str = Form(...)):
    if mode in ("shadow", "recommend", "autopilot"):
        set_mode(mode)
    return RedirectResponse("/", status_code=303)


# Marty chat stub (Wave C will fill in)
@app.post("/marty/chat")
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
        Conversational flows (daily digest, "why did you drop X?", bulk approvals) coming in Wave C. For now, head to the
        <a href="/agent/inbox" class="text-marty-100 font-bold hover:underline">agent inbox</a> or <a href="/agent/policy" class="text-marty-100 font-bold hover:underline">policy</a>.
      </div>
    </div>
    ''')
