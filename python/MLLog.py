# MLLog.py — registro persistente de decisões de atribuição (Fase 3)

from datetime import datetime

from DAL import DAL
from logger import ClLog


class ClMLLog:
    logger = ClLog()

    SQL_INSERT = """
        INSERT INTO Tb_ML_Log
            (Id_Glpi, Metodo, Equipe_Prevista, Equipe_ML, Equipe_2a,
             Confianca, Margem, Motivo_Rejeicao, Motivo_Atrib, Categoria, Localizacao, Data_Registro)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Fallback se Motivo_Atrib ainda não existir (migração pendente)
    SQL_INSERT_LEGACY = """
        INSERT INTO Tb_ML_Log
            (Id_Glpi, Metodo, Equipe_Prevista, Equipe_ML, Equipe_2a,
             Confianca, Margem, Motivo_Rejeicao, Categoria, Localizacao, Data_Registro)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    def __init__(self, dal: DAL = None):
        self.dal = dal or DAL(app_name="MLLog", nome_arquivo_config="sgc.dat")

    def registrar(
        self,
        id_glpi: int,
        metodo: str,
        equipe_prevista: str,
        categoria: str = "",
        localizacao: str = "",
        equipe_ml: str = "",
        equipe_2a: str = "",
        confianca: float = 0.0,
        margem: float = 0.0,
        motivo_rejeicao: str = "",
        motivo_atrib: str = "",
    ) -> bool:
        try:
            base = (
                int(id_glpi),
                (metodo or "")[:20],
                (equipe_prevista or "")[:5] or None,
                (equipe_ml or "")[:5] or None,
                (equipe_2a or "")[:5] or None,
                round(float(confianca), 2) if confianca else None,
                round(float(margem), 2) if margem else None,
                (motivo_rejeicao or "")[:255] or None,
            )
            motivo_a = (motivo_atrib or "")[:500] or None
            tail = (
                (categoria or "")[:500] or None,
                (localizacao or "")[:500] or None,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            try:
                ok = self.dal.create(self.SQL_INSERT, base + (motivo_a,) + tail)
            except Exception:
                ok = self.dal.create(self.SQL_INSERT_LEGACY, base + tail)
            if ok:
                self.logger.registrarActionLog(
                    "ML_LOG",
                    "ATIVIDADE",
                    f"CHAMADO {id_glpi} | {metodo} | EQUIPE: {equipe_prevista or 'N/A'}",
                )
            return bool(ok)
        except Exception as e:
            self.logger.registarExceptionLog(
                "ML_LOG", "EXCEPTION", f"FALHA AO REGISTRAR LOG ML {id_glpi}", e
            )
            return False

    def atualizar_motivo_atrib(self, id_glpi: int, motivo_atrib: str) -> bool:
        """Atualiza Motivo_Atrib no log mais recente do chamado."""
        texto = (motivo_atrib or "").strip()
        if not texto:
            return False
        try:
            ok = self.dal.update(
                """
                UPDATE Tb_ML_Log
                SET Motivo_Atrib = %s
                WHERE Id_Glpi = %s
                ORDER BY Data_Registro DESC, idml DESC
                LIMIT 1
                """,
                (texto[:500], int(id_glpi)),
            )
            return bool(ok)
        except Exception as e:
            self.logger.registarExceptionLog(
                "ML_LOG",
                "EXCEPTION",
                f"FALHA AO ATUALIZAR Motivo_Atrib {id_glpi}",
                e,
            )
            return False
