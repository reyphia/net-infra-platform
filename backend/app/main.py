from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    audit,
    changes,
    configuration,
    credentials,
    devices,
    discovery,
    monitoring,
    terminal,
    topology,
)
from app.core.config import get_settings
from app.core.fsutil import resolve_frontend_dist_path
from app.db.session import init_models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.environment != "production":
        # Dev/test convenience only. Production deployments should manage
        # schema via `alembic upgrade head` (see backend/alembic/).
        await init_models()
    logger.info("%s starting (environment=%s)", settings.app_name, settings.environment)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Network infrastructure discovery, topology, and controlled-change "
            "management platform. See /docs for the full API surface."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(devices.router, prefix=settings.api_prefix)
    app.include_router(discovery.router, prefix=settings.api_prefix)
    app.include_router(topology.router, prefix=settings.api_prefix)
    app.include_router(credentials.router, prefix=settings.api_prefix)
    app.include_router(configuration.router, prefix=settings.api_prefix)
    app.include_router(changes.router, prefix=settings.api_prefix)
    app.include_router(audit.router, prefix=settings.api_prefix)
    app.include_router(monitoring.router, prefix=settings.api_prefix)
    app.include_router(terminal.router, prefix=settings.api_prefix)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": settings.app_name}

    # Optionally serve the built frontend from this same process. This is
    # what lets the standalone packaged app (PyInstaller .exe / Linux
    # binary -- see scripts/build_release_*.{ps1,sh}) be a single
    # double-click-and-go artifact: no separate frontend server needed.
    # In normal Docker Compose or local-dev setups this simply finds
    # nothing and is a no-op -- the frontend is served by its own
    # container/dev-server instead. Registered last so it never shadows
    # /api, /health, /docs, /openapi.json, or /redoc.
    frontend_dist = resolve_frontend_dist_path()
    if frontend_dist is not None:
        logger.info("Serving bundled frontend from %s", frontend_dist)
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        index_file = frontend_dist / "index.html"
        reserved_prefixes = (settings.api_prefix, "/health", "/docs", "/openapi.json", "/redoc")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str) -> FileResponse:
            # A real file in dist/ (favicon, manifest, etc.) is served
            # directly; anything else falls back to index.html so client-side
            # routes like /devices/{id} work on a hard refresh, matching how
            # every SPA router (React Router included) expects its host to
            # behave.
            if any(("/" + full_path).startswith(p) for p in reserved_prefixes):
                from fastapi import HTTPException

                raise HTTPException(status_code=404)
            candidate = frontend_dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_file)
    else:
        logger.info("No bundled frontend found -- serving API only (this is expected in Docker/dev setups)")

    return app


app = create_app()
