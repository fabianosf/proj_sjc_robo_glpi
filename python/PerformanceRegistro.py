# PerformanceRegistro.py — persiste assertividade diária em tb_performance

from datetime import datetime

from DAL import DAL
from logger import ClLog


class ClPerformanceRegistro:
    logger = ClLog()

    SQL_UPSERT = """
        INSERT INTO tb_performance (Performance, Data)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE Performance = VALUES(Performance)
    """

    def __init__(self, dal: DAL = None):
        self.dal = dal or DAL(app_name="Performance", nome_arquivo_config="sgc.dat")

    @staticmethod
    def _parse_data_referencia(data_referencia: str):
        if not data_referencia:
            return datetime.now().date()
        try:
            return datetime.strptime(data_referencia.strip(), "%d/%m/%Y").date()
        except ValueError:
            return datetime.now().date()

    def registrar(self, performance_pct: float, data_referencia: str) -> bool:
        """Grava ou atualiza a performance (%) do dia de referência."""
        try:
            data_dia = self._parse_data_referencia(data_referencia)
            valor = round(float(performance_pct or 0), 2)
            ok = self.dal.create(self.SQL_UPSERT, (valor, data_dia.strftime("%Y-%m-%d")))
            if ok:
                self.logger.registrarActionLog(
                    "PERFORMANCE",
                    "ATIVIDADE",
                    f"Performance {valor:.2f}% registrada para {data_dia.strftime('%d/%m/%Y')}",
                )
            return bool(ok)
        except Exception as e:
            self.logger.registarExceptionLog(
                "PERFORMANCE",
                "registrar",
                "FALHA AO GRAVAR tb_performance",
                e,
            )
            return False
