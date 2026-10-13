"""
API FastAPI do painel SGC.

Processo isolado do worker (main.py / AgendadorSGC).
Não expõe conf/, tokens ou credenciais.
Escritas ADMIN: técnicos, redirect GLPI, reassign de chamado, matrículas e regras.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .bootstrap import PROJECT_ROOT, ensure_legacy_path
from .logging_config import setup_logging
from .routers import auth, health, v1
logger = setup_logging()

# Carrega .env antes de ler CORS/docs/flags
def _load_dotenv() -> None:
    """Carrega backend/.env ou .env da raiz sem sobrescrever env já definida."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in (
        PROJECT_ROOT / "backend" / ".env",
        PROJECT_ROOT / ".env",
    ):
        if candidate.is_file():
            load_dotenv(candidate, override=False)


_load_dotenv()


def _cors_origins() -> list[str]:
    raw = (os.getenv("SGC_CORS_ORIGINS") or "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def _docs_urls() -> tuple[str | None, str | None]:
    """Em produção (SGC_API_DOCS=0) desliga /docs e /redoc."""
    flag = (os.getenv("SGC_API_DOCS") or "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return None, None
    return "/docs", "/redoc"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_legacy_path()
    secret_ok = bool((os.getenv("SGC_JWT_SECRET") or "").strip())
    logger.info(
        "SGC API iniciada (v%s) — auth=%s cors=%s",
        __version__,
        "ok" if secret_ok else "SGC_JWT_SECRET AUSENTE",
        _cors_origins(),
    )
    yield
    logger.info("SGC API encerrada")


_docs, _redoc = _docs_urls()

app = FastAPI(
    title="SGC API",
    description=(
        "API do painel web do SGC: leituras operacionais para perfis autorizados; "
        "escritas delimitadas a ADMIN (técnicos, redirect GLPI, matrícula, regras). "
        "Isolada do worker de atribuição. "
        "Rotas /api/v1 exigem JWT (exceto /api/v1/auth/login)."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url=_docs,
    redoc_url=_redoc,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()) if x != "query" and x != "path")
        msg = err.get("msg", "inválido")
        parts.append(f"{loc}: {msg}" if loc else str(msg))
    detail = "; ".join(parts) if parts else "Parâmetros inválidos na requisição."
    logger.warning("Validação 422: %s", detail)
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Erro não tratado em %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor."},
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(v1.router)


def _frontend_dist():
    flag = (os.getenv("SGC_SERVE_FRONTEND") or "0").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return None
    dist = PROJECT_ROOT / "frontend" / "dist"
    return dist if dist.is_dir() else None


def _maybe_mount_frontend() -> None:
    """Serve frontend/dist (SPA) se SGC_SERVE_FRONTEND=1."""
    from fastapi.responses import FileResponse

    dist = _frontend_dist()
    if dist is None:
        if (os.getenv("SGC_SERVE_FRONTEND") or "0").strip().lower() in ("1", "true", "yes", "on"):
            logger.warning("SGC_SERVE_FRONTEND=1 mas frontend/dist ausente — rode npm run build")

        @app.get("/", include_in_schema=False)
        def root():
            return {
                "name": "SGC API",
                "version": __version__,
                "docs": "/docs" if _docs else None,
                "health": "/health",
                "api": "/api/v1",
                "auth": "/api/v1/auth",
            }

        return

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_root():
        return FileResponse(dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Arquivo estático real (favicon, etc.); senão index.html (React Router)
        candidate = (dist / full_path).resolve()
        try:
            candidate.relative_to(dist.resolve())
        except ValueError:
            return FileResponse(dist / "index.html")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")

    logger.info("Frontend SPA montado em / a partir de %s", dist)


_maybe_mount_frontend()
