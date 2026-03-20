"""
api/app.py
-----------
FastAPI application factory.

    from api.app import create_app
    app = create_app()

Run:
    uvicorn api.app:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, admin, platforms, accounts, keywords, layouts, presets, campaigns, combinations, batches, utility


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Automater Factory API",
        version="0.1.0",
        root_path="/api/v1",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(platforms.router)
    app.include_router(accounts.router)
    app.include_router(keywords.router)
    app.include_router(layouts.router)
    app.include_router(presets.router)
    app.include_router(campaigns.router)
    app.include_router(combinations.router)
    app.include_router(batches.router)
    app.include_router(utility.router)

    return app


app = create_app()
