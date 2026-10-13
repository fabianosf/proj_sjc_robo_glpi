# NotificacaoPainel.py — insert in-app (Tb_Notificacao). Usado pelo worker, sem FastAPI.

from __future__ import annotations

from typing import Any, Optional, Sequence

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


def _table_ok(dal: Any) -> bool:
    try:
        df = dal.read("SHOW TABLES LIKE 'Tb_Notificacao'")
        if df is not None and not getattr(df, "empty", True):
            return True
    except Exception:
        pass
    try:
        ok = dal.create(_DDL) if hasattr(dal, "create") else dal.execute_query(_DDL, fetch=False)
        return bool(ok)
    except Exception:
        return False


def create_notification(
    dal: Any,
    *,
    destinatario: str,
    titulo: str,
    mensagem: str,
    tipo: str = "TICKET_ASSIGNED",
    ref_ids: Optional[Sequence[int]] = None,
    criado_por: Optional[str] = None,
) -> bool:
    dest = (destinatario or "").strip()
    if not dest or not _table_ok(dal):
        return False
    ids_csv = None
    if ref_ids:
        ids_csv = ",".join(str(int(x)) for x in list(ref_ids)[:40])
        if len(ids_csv) > 500:
            ids_csv = ids_csv[:500].rsplit(",", 1)[0]
    try:
        return bool(
            dal.update(
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
        )
    except Exception:
        return False


def notify_ticket_assigned(
    dal: Any,
    *,
    tecnico: str,
    ticket_id: int,
    equipe: str = "",
) -> bool:
    tec = (tecnico or "").strip()
    if not tec:
        return False
    try:
        tid = int(ticket_id)
    except (TypeError, ValueError):
        return False
    eq = (equipe or "").strip()
    extra = f" Equipe {eq}." if eq else ""
    return create_notification(
        dal,
        destinatario=tec,
        titulo=f"Chamado #{tid} atribuído a você",
        mensagem=f"O SGC atribuiu o chamado {tid} a você.{extra}",
        tipo="TICKET_ASSIGNED",
        ref_ids=[tid],
        criado_por="worker",
    )
