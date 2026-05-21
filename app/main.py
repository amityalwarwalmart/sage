"""Sage — AI Marketplace Manager. FastAPI entrypoint."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import audit, chat, home, inbox, plan, rules, runs, workspace
from app.routers import settings as settings_router

app = FastAPI(title="Sage — AI Marketplace Manager")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(home.router)
app.include_router(inbox.router)
app.include_router(plan.router)
app.include_router(runs.router)
app.include_router(rules.router)
app.include_router(workspace.router)
app.include_router(settings_router.router)
app.include_router(audit.router)
app.include_router(chat.router)
