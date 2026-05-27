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
    marty_chat,
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
app.include_router(marty_chat.router)


@app.post("/agent/mode")
async def change_mode(mode: str = Form(...)):
    if mode in ("shadow", "recommend", "autopilot"):
        set_mode(mode)
    return RedirectResponse("/", status_code=303)
