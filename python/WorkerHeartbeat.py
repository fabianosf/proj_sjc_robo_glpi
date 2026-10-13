# WorkerHeartbeat.py — último loop do main.py (arquivo em log/, sem segredos)

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from paths import LOG_DIR

HEARTBEAT_FILE = LOG_DIR / "worker_heartbeat.json"
ALIVE_AFTER_SECONDS = max(
    30, int(os.getenv("SGC_WORKER_ALIVE_SECONDS", "300") or 300)
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_heartbeat() -> Dict[str, Any]:
    if not HEARTBEAT_FILE.is_file():
        return {}
    try:
        data = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_heartbeat(**fields: Any) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    current = read_heartbeat()
    today = datetime.now().date().isoformat()
    if current.get("skips_date") != today:
        current["skips_today"] = 0
        current["skips_date"] = today
    current.update({k: v for k, v in fields.items() if v is not None})
    current["updated_at"] = _now_iso()
    tmp = HEARTBEAT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(HEARTBEAT_FILE)


def _skipped_ids_today(current: Dict[str, Any], today: str) -> List[int]:
    if current.get("skips_date") != today:
        return []
    raw = current.get("skipped_ids_today") or []
    out: List[int] = []
    if isinstance(raw, list):
        for item in raw:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
    return out


def was_skipped_today(ticket_id: Any) -> bool:
    """True se este ID já gerou skip hoje (evita spam ML / contador)."""
    current = read_heartbeat()
    today = datetime.now().date().isoformat()
    try:
        tid = int(ticket_id)
    except (TypeError, ValueError):
        return False
    ids = _skipped_ids_today(current, today)
    if tid in ids:
        return True
    try:
        return int(current.get("last_skip_id")) == tid and current.get("skips_date") == today
    except (TypeError, ValueError):
        return False


def note_skip(ticket_id: Any) -> bool:
    """
    Registra skip. Retorna True na primeira vez do ID no dia;
    False se já contado hoje (não incrementa de novo).
    """
    current = read_heartbeat()
    today = datetime.now().date().isoformat()
    skips = int(current.get("skips_today") or 0)
    if current.get("skips_date") != today:
        skips = 0
    try:
        last_skip = int(ticket_id)
    except (TypeError, ValueError):
        last_skip = None
    ids = _skipped_ids_today(current, today)
    if last_skip is not None and last_skip in ids:
        write_heartbeat(last_skip_id=last_skip, skips_date=today)
        return False
    if last_skip is not None:
        ids.append(last_skip)
    write_heartbeat(
        skips_today=skips + 1,
        skips_date=today,
        last_skip_id=last_skip,
        skipped_ids_today=ids[-80:],
    )
    return True


def maybe_daily_qtdc_reset(reset_fn) -> bool:
    """Uma vez por dia: chama reset_fn() e grava qtdc_reset_date no heartbeat."""
    today = datetime.now().date().isoformat()
    current = read_heartbeat()
    if current.get("qtdc_reset_date") == today:
        return False
    try:
        ok = bool(reset_fn())
    except Exception:
        ok = False
    if ok:
        write_heartbeat(qtdc_reset_date=today)
    return ok


def note_orphan(ticket_id: Any, tecnico: str = "", equipe: str = "") -> None:
    """GLPI atribuído mas INSERT em Tb_Ticket_new falhou — aguarda backfill."""
    try:
        orphan_id = int(ticket_id)
    except (TypeError, ValueError):
        orphan_id = None
    write_heartbeat(
        last_orphan_id=orphan_id,
        last_orphan_tecnico=(tecnico or "").strip()[:40] or None,
        last_orphan_equipe=(equipe or "").strip()[:10] or None,
        last_orphan_at=_now_iso(),
    )


def snapshot_for_api() -> Dict[str, Any]:
    data = read_heartbeat()
    updated = str(data.get("updated_at") or "")
    age: Optional[int] = None
    alive = False
    if updated:
        try:
            ts = datetime.fromisoformat(updated)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.now().astimezone().tzinfo)
            age = max(0, int((datetime.now(ts.tzinfo) - ts).total_seconds()))
            alive = age <= ALIVE_AFTER_SECONDS
        except ValueError:
            age = None
    err = str(data.get("last_error") or "").strip()
    return {
        "updated_at": updated or None,
        "age_seconds": age,
        "alive": alive,
        "glpi_ok": data.get("glpi_ok"),
        "novos_na_fila": data.get("novos_na_fila"),
        "last_assigned_id": data.get("last_assigned_id"),
        "last_skip_id": data.get("last_skip_id"),
        "last_orphan_id": data.get("last_orphan_id"),
        "skips_today": data.get("skips_today") if data.get("skips_date") == datetime.now().date().isoformat() else 0,
        "last_error": err or None,
        "agendador_auto": data.get("agendador_auto"),
        "fetch_truncated": bool(data.get("fetch_truncated")) if data.get("fetch_truncated") is not None else None,
    }
