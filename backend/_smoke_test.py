"""Testes manuais da SGC API (JWT + allowlist). Servidor precisa estar no ar.

Uso:
  set SGC_SMOKE_USER=59817
  set SGC_SMOKE_PASSWORD=...
  venv\\Scripts\\python.exe backend\\_smoke_test.py http://127.0.0.1:8001
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
LEAK_RE = re.compile(
    r"(password|senha|chave\.key|app_token|fernet|\"token\"\s*:)",
    re.I,
)
results: list[tuple[str, bool, str]] = []


def req(
    method: str,
    path: str,
    expect: int,
    *,
    data: dict | None = None,
    token: str | None = None,
) -> tuple[int, str]:
    url = f"{BASE}{path}"
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            code = resp.status
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        code = e.code
    except Exception as e:
        results.append((f"{method} {path}", False, f"EXC {e}"))
        return 0, ""
    ok = code == expect
    results.append((f"{method} {path}", ok, f"{code} (esperado {expect})"))
    return code, text


def main() -> int:
    print(f"BASE={BASE}")
    _, health = req("GET", "/health", 200)

    # Rotas protegidas sem token → 401
    req("GET", "/api/v1/dashboard/summary", 401)
    req("GET", "/api/v1/tickets?page=1&page_size=5", 401)
    req("GET", "/api/v1/teams", 401)

    # Allowlist: usuário fora → 401
    req(
        "POST",
        "/api/v1/auth/login",
        401,
        data={"username": "99999999", "password": "x"},
    )

    user = (os.getenv("SGC_SMOKE_USER") or "").strip()
    password = os.getenv("SGC_SMOKE_PASSWORD") or ""
    token = None
    if user and password:
        code, login_body = req(
            "POST",
            "/api/v1/auth/login",
            200,
            data={"username": user, "password": password},
        )
        try:
            token = json.loads(login_body).get("access_token")
        except Exception:
            token = None
        if token:
            req("GET", "/api/v1/auth/me", 200, token=token)
            _, dash = req("GET", "/api/v1/dashboard/summary", 200, token=token)
            _, tickets = req(
                "GET", "/api/v1/tickets?page=1&page_size=5", 200, token=token
            )
            req("GET", "/api/v1/teams", 200, token=token)
            req("GET", "/api/v1/technicians", 200, token=token)
            tid = None
            try:
                items = json.loads(tickets).get("items") or []
                if items:
                    tid = items[0].get("id")
            except Exception:
                pass
            if tid is not None:
                req("GET", f"/api/v1/tickets/{tid}", 200, token=token)
            req("POST", "/api/v1/auth/logout", 200, data={}, token=token)
            # token revogado
            req("GET", "/api/v1/auth/me", 401, token=token)
            results.append(("login_flow", True, f"user={user}"))
            leaks = []
            for label, body in (("health", health), ("dashboard", dash), ("tickets", tickets)):
                if body and LEAK_RE.search(body):
                    leaks.append(label)
            results.append(("no_credentials", not leaks, "clean" if not leaks else ",".join(leaks)))
        else:
            results.append(("login_flow", False, "sem token"))
    else:
        results.append(
            (
                "login_flow",
                True,
                "SKIP — defina SGC_SMOKE_USER e SGC_SMOKE_PASSWORD para teste autenticado",
            )
        )

    req("GET", "/api/v1/tickets/0", 401)  # auth before path validation typically
    req("POST", "/api/v1/jobs", 401)

    try:
        h = json.loads(health)
        db_ok = h.get("database") == "ok"
        results.append(("db_connection", db_ok, json.dumps(h, ensure_ascii=False)))
    except Exception as e:
        results.append(("db_connection", False, str(e)))

    print()
    failed = 0
    for name, ok, detail in results:
        mark = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{mark}] {name} — {detail}")
    print(f"\nTOTAL fail={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
