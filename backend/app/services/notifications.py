"""Notificações in-app do painel (ex.: chamados redirecionados)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from ..db_meta import cell_to_python, columns_of, resolve_column, safe_read, table_exists
from ..schemas import NotificationItem, NotificationList, NotificationUnreadCount

logger = logging.getLogger("sgc_api")

_DDL = """
CREATE TABLE IF NOT EXISTS `Tb_Notificacao` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `destinatario` varchar(80) NOT NULL,
  `tipo` varchar(40) NOT NULL DEFAULT 'TICKETS_REDIRECTED',
  `titulo` varchar(160) NOT NULL,
  `mensagem` varchar(500) NOT NULL,
  `ref_ids` varchar(500) DEFAULT NULL,
  `lida` tinyint(1) NOT NULL DEFAULT 0,
  `criado_por` varchar(80) DEFAULT NULL,
  `criado_em` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `lida_em` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_notif_dest_lida` (`destinatario`, `lida`),
  KEY `idx_notif_criado` (`criado_em`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def ensure_notification_table(dal: Any) -> bool:
    if table_exists(dal, "Tb_Notificacao"):
        return True
    try:
        ok = dal.create(_DDL) if hasattr(dal, "create") else dal.execute_query(_DDL, fetch=False)
        if not ok:
            logger.warning("Tb_Notificacao não criada — rode sql/criar_Tb_Notificacao.sql")
    except Exception as exc:
        logger.warning("Falha ao criar Tb_Notificacao: %s — rode sql/criar_Tb_Notificacao.sql", exc)
    return table_exists(dal, "Tb_Notificacao")


def _aliases_for_user(dal: Any, username: str) -> List[str]:
    """Usuario AD e matrícula associados ao login atual."""
    raw = (username or "").strip()
    if not raw:
        return []
    aliases = {raw.lower()}
    if not table_exists(dal, "Tb_Atrib"):
        return list(aliases)

    cols = columns_of(dal, "Tb_Atrib")
    col_user = resolve_column(cols, "Usuario")
    col_mat = resolve_column(cols, "Matricula")
    if not col_user:
        return list(aliases)

    # Login = Usuario AD → pega matrícula
    df = safe_read(
        dal,
        f"""
        SELECT TRIM(`{col_user}`) AS usuario
             {f", TRIM(`{col_mat}`) AS matricula" if col_mat else ""}
        FROM Tb_Atrib
        WHERE UPPER(TRIM(`{col_user}`)) = %s
        LIMIT 5
        """,
        (raw.upper(),),
    )
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            u = str(cell_to_python(row.get("usuario")) or "").strip()
            if u:
                aliases.add(u.lower())
            if col_mat and "matricula" in row.index:
                m = str(cell_to_python(row.get("matricula")) or "").strip()
                if m and m not in ("0", "00000"):
                    aliases.add(m.lower())

    # Login = matrícula → pega Usuario AD
    if col_mat:
        df2 = safe_read(
            dal,
            f"""
            SELECT TRIM(`{col_user}`) AS usuario, TRIM(`{col_mat}`) AS matricula
            FROM Tb_Atrib
            WHERE TRIM(COALESCE(`{col_mat}`, '')) <> ''
              AND (
                UPPER(TRIM(`{col_mat}`)) = %s
                OR TRIM(LEADING '0' FROM TRIM(`{col_mat}`)) = %s
              )
            LIMIT 5
            """,
            (raw.upper(), raw.lstrip("0") or raw),
        )
        if df2 is not None and not df2.empty:
            for _, row in df2.iterrows():
                u = str(cell_to_python(row.get("usuario")) or "").strip()
                m = str(cell_to_python(row.get("matricula")) or "").strip()
                if u:
                    aliases.add(u.lower())
                if m and m not in ("0", "00000"):
                    aliases.add(m.lower())

    return sorted(aliases)


def create_notification(
    dal: Any,
    *,
    destinatario: str,
    titulo: str,
    mensagem: str,
    tipo: str = "TICKETS_REDIRECTED",
    ref_ids: Optional[Sequence[int]] = None,
    criado_por: Optional[str] = None,
) -> bool:
    if not ensure_notification_table(dal):
        return False
    dest = (destinatario or "").strip()
    if not dest:
        return False
    ids_csv = None
    if ref_ids:
        ids_csv = ",".join(str(int(x)) for x in list(ref_ids)[:40])
        if len(ids_csv) > 500:
            ids_csv = ids_csv[:500].rsplit(",", 1)[0]

    ok = dal.update(
        """
        INSERT INTO Tb_Notificacao
          (destinatario, tipo, titulo, mensagem, ref_ids, lida, criado_por)
        VALUES (%s, %s, %s, %s, %s, 0, %s)
        """,
        (
            dest[:80],
            (tipo or "INFO")[:40],
            (titulo or "Aviso")[:160],
            (mensagem or "")[:500],
            ids_csv,
            (criado_por or "")[:80] or None,
        ),
    )
    return bool(ok)


def notify_tickets_redirected(
    dal: Any,
    *,
    de: str,
    para: str,
    ticket_ids: Sequence[int],
    criado_por: Optional[str] = None,
) -> bool:
    n = len(ticket_ids)
    if n <= 0:
        # ainda avisa que o login/equipe foi redirecionado
        titulo = "Chamados redirecionados para você"
        mensagem = (
            f"O técnico {de} foi redirecionado para você. "
            f"Não havia chamados locais na base SGC."
        )
        return create_notification(
            dal,
            destinatario=para,
            titulo=titulo,
            mensagem=mensagem,
            tipo="TICKETS_REDIRECTED",
            ref_ids=[],
            criado_por=criado_por,
        )

    ids_preview = ", ".join(str(i) for i in list(ticket_ids)[:12])
    more = f" (+{n - 12})" if n > 12 else ""
    titulo = f"{n} chamado(s) redirecionado(s) para você"
    mensagem = (
        f"{n} chamado(s) de {de} foram atribuídos a você."
        f" IDs: {ids_preview}{more}."
    )
    return create_notification(
        dal,
        destinatario=para,
        titulo=titulo,
        mensagem=mensagem,
        tipo="TICKETS_REDIRECTED",
        ref_ids=ticket_ids,
        criado_por=criado_por,
    )


def notify_reassign_actor(
    dal: Any,
    *,
    actor: str,
    ticket_id: int,
    mode: str,
    equipe: Optional[str],
    tecnico: str,
    criado_por: Optional[str] = None,
) -> bool:
    """Avisa quem reatribuiu (ADMIN) — comprovante no sino."""
    dest = (actor or "").strip()
    if not dest:
        return False
    tid = int(ticket_id)
    if mode == "equipe" and equipe:
        titulo = f"Chamado #{tid} enviado para a fila {equipe}"
        mensagem = (
            f"Você enviou o chamado #{tid} para a fila {equipe} "
            f"(técnico: {tecnico})."
        )
    else:
        fila = f" · equipe {equipe}" if equipe else ""
        titulo = f"Chamado #{tid} enviado para {tecnico}"
        mensagem = f"Você enviou o chamado #{tid} para {tecnico}{fila}."
    return create_notification(
        dal,
        destinatario=dest,
        titulo=titulo,
        mensagem=mensagem,
        tipo="TICKET_REASSIGN_OK",
        ref_ids=[tid],
        criado_por=criado_por or dest,
    )


def _row_to_item(row: Dict[str, Any]) -> NotificationItem:
    ref_raw = cell_to_python(row.get("ref_ids"))
    ref_ids: List[int] = []
    if ref_raw:
        for part in str(ref_raw).split(","):
            part = part.strip()
            if part.isdigit():
                ref_ids.append(int(part))
    criado = cell_to_python(row.get("criado_em"))
    return NotificationItem(
        id=int(cell_to_python(row.get("id")) or 0),
        tipo=str(cell_to_python(row.get("tipo")) or ""),
        titulo=str(cell_to_python(row.get("titulo")) or ""),
        mensagem=str(cell_to_python(row.get("mensagem")) or ""),
        ref_ids=ref_ids,
        lida=bool(int(cell_to_python(row.get("lida")) or 0)),
        criado_por=str(cell_to_python(row.get("criado_por")) or "") or None,
        criado_em=str(criado) if criado is not None else None,
    )


def list_notifications(
    dal: Any,
    username: str,
    *,
    unread_only: bool = False,
    limit: int = 30,
) -> NotificationList:
    empty = NotificationList(items=[], unread=0)
    if not ensure_notification_table(dal):
        return empty

    aliases = _aliases_for_user(dal, username)
    if not aliases:
        return empty

    placeholders = ", ".join(["%s"] * len(aliases))
    where = f"LOWER(TRIM(destinatario)) IN ({placeholders})"
    params: list = list(aliases)
    if unread_only:
        where += " AND lida = 0"

    limit = max(1, min(100, int(limit)))
    df = safe_read(
        dal,
        f"""
        SELECT id, tipo, titulo, mensagem, ref_ids, lida, criado_por, criado_em
        FROM Tb_Notificacao
        WHERE {where}
        ORDER BY criado_em DESC, id DESC
        LIMIT %s
        """,
        tuple(params + [limit]),
    )
    items: List[NotificationItem] = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            items.append(_row_to_item({str(k): v for k, v in row.items()}))

    unread = unread_count(dal, username).unread
    return NotificationList(items=items, unread=unread)


def unread_count(dal: Any, username: str) -> NotificationUnreadCount:
    if not ensure_notification_table(dal):
        return NotificationUnreadCount(unread=0)
    aliases = _aliases_for_user(dal, username)
    if not aliases:
        return NotificationUnreadCount(unread=0)
    placeholders = ", ".join(["%s"] * len(aliases))
    df = safe_read(
        dal,
        f"""
        SELECT COUNT(*) AS cnt
        FROM Tb_Notificacao
        WHERE LOWER(TRIM(destinatario)) IN ({placeholders})
          AND lida = 0
        """,
        tuple(aliases),
    )
    n = int(cell_to_python(df.iloc[0]["cnt"]) or 0) if df is not None and not df.empty else 0
    return NotificationUnreadCount(unread=n)


def mark_read(dal: Any, username: str, notif_id: int) -> bool:
    if not ensure_notification_table(dal):
        return False
    aliases = _aliases_for_user(dal, username)
    if not aliases:
        return False
    placeholders = ", ".join(["%s"] * len(aliases))
    return bool(
        dal.update(
            f"""
            UPDATE Tb_Notificacao
            SET lida = 1, lida_em = %s
            WHERE id = %s
              AND LOWER(TRIM(destinatario)) IN ({placeholders})
              AND lida = 0
            """,
            tuple([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(notif_id)] + aliases),
        )
    )


def mark_all_read(dal: Any, username: str) -> int:
    if not ensure_notification_table(dal):
        return 0
    aliases = _aliases_for_user(dal, username)
    if not aliases:
        return 0
    placeholders = ", ".join(["%s"] * len(aliases))
    # conta antes
    before = unread_count(dal, username).unread
    dal.update(
        f"""
        UPDATE Tb_Notificacao
        SET lida = 1, lida_em = %s
        WHERE LOWER(TRIM(destinatario)) IN ({placeholders})
          AND lida = 0
        """,
        tuple([datetime.now().strftime("%Y-%m-%d %H:%M:%S")] + aliases),
    )
    return before
