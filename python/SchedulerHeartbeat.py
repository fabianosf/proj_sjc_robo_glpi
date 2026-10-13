# SchedulerHeartbeat.py — última execução dos jobs (log/, sem segredos)

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from paths import LOG_DIR

HEARTBEAT_FILE = LOG_DIR / "scheduler_heartbeat.json"
ALIVE_AFTER_SECONDS = 90


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


def _write(current: Dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    current["updated_at"] = _now_iso()
    tmp = HEARTBEAT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(HEARTBEAT_FILE)


def tick() -> None:
    current = read_heartbeat()
    if not isinstance(current.get("jobs"), dict):
        current["jobs"] = {}
    _write(current)


def note_job(job_id: str, ok: bool, message: str = "") -> None:
    jid = (job_id or "").strip()[:40]
    if not jid:
        return
    current = read_heartbeat()
    jobs = current.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}
    jobs[jid] = {
        "at": _now_iso(),
        "ok": bool(ok),
        "message": (message or "")[:300],
    }
    current["jobs"] = jobs
    _write(current)


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
    jobs_raw = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
    jobs: Dict[str, Any] = {}
    for key, val in jobs_raw.items():
        if not isinstance(val, dict):
            continue
        jobs[str(key)] = {
            "at": val.get("at"),
            "ok": val.get("ok"),
            "message": val.get("message"),
        }
    return {
        "updated_at": updated or None,
        "age_seconds": age,
        "alive": alive,
        "jobs": jobs,
    }
