"""GET /health"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from .. import __version__
from ..deps import get_dal
from ..schemas import HealthResponse
from ..services import queries

logger = logging.getLogger("sgc_api")
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_status = "unavailable"
    try:
        dal = get_dal()
        ok = bool(dal.test_connection())
        db_status = "ok" if ok else "error"
    except Exception as exc:
        logger.warning("Health check DB: %s", exc)
        db_status = "error"

    overall = "ok" if db_status == "ok" else "degraded"
    snap = queries.get_worker_heartbeat()
    err = str(snap.get("last_error") or "").strip()
    age = snap.get("age_seconds")
    try:
        age_i = int(age) if age is not None else None
    except (TypeError, ValueError):
        age_i = None
    has_hb = bool(snap.get("updated_at"))
    glpi_ok = snap.get("glpi_ok")

    return HealthResponse(
        status=overall,
        database=db_status,
        version=__version__,
        worker_updated_at=snap.get("updated_at") if has_hb else None,
        worker_age_seconds=age_i if has_hb else None,
        worker_alive=bool(snap.get("alive")) if has_hb else None,
        worker_glpi_ok=None if (not has_hb or glpi_ok is None) else bool(glpi_ok),
        worker_last_error=(err or None) if has_hb else None,
    )
