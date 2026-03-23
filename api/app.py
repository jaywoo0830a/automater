"""
api/app.py — FastAPI application.

    uvicorn api.app:app --port 8000 --reload
    bash ./run/dev.sh --api
"""
from __future__ import annotations
from fastapi import FastAPI
from api.auth import router as auth_router
from api.step1 import router as step1_router
from api.step2_keywords import router as step2_keywords_router
from api.step2_pools import router as step2_pools_router
from api.step2_spacing import router as step2_spacing_router
from api.step2_title import router as step2_title_router
from api.step2_confirm import router as step2_confirm_router
from api.step3 import router as step3_router
from api.step4 import router as step4_router
from api.monitor import router as monitor_router

PREFIX = "/api/spa/v1"

def create_app() -> FastAPI:
    application = FastAPI(
        title="automater SPA API",
        version="1.3.0",
        docs_url=f"{PREFIX}/docs",
        openapi_url=f"{PREFIX}/openapi.json",
    )
    for r in [auth_router, step1_router, step2_keywords_router, step2_pools_router,
              step2_spacing_router, step2_title_router, step2_confirm_router,
              step3_router, step4_router, monitor_router]:
        application.include_router(r, prefix=PREFIX)
    return application

app = create_app()
