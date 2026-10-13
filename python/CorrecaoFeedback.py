# CorrecaoFeedback.py — divergências de equipe SGC vs fechamento GLPI (Fase 3)

from datetime import datetime

from DAL import DAL
from DbMigracao import ClDbMigracao
from EquipeAssertividade import errou_classificacao_equipe, normalizar_equipe
from logger import ClLog


class ClCorrecaoFeedback:
    logger = ClLog()
    PESO_TREINO = 3.0

    SQL_LIMPAR_ACERTOS = """
        DELETE FROM Tb_Correcao_Feedback
        WHERE UPPER(TRIM(Equipe_SGC)) = UPPER(TRIM(Equipe_Correta))
    """

    SQL_CANDIDATOS = """
        SELECT
            tn.Id AS Id_Glpi,
            tn.Titulo AS Titulo,
            tn.Categoria AS Categoria,
            tn.Descricao AS Descricao,
            fb.Localizacao AS Localizacao,
            UPPER(TRIM(tn.Equipe)) AS Equipe_SGC,
            UPPER(TRIM(ta.Equipe)) AS Equipe_Correta,
            fb.Tecnico AS Tecnico_Fechamento
        FROM Tb_Ticket_new tn
        INNER JOIN Tb_Ticket_Feedback_Temp fb ON fb.Id_Glpi = tn.Id
        INNER JOIN Tb_Atrib ta ON UPPER(TRIM(ta.Usuario)) = UPPER(TRIM(fb.Tecnico))
        WHERE tn.Equipe IS NOT NULL AND TRIM(tn.Equipe) <> ''
          AND ta.Equipe IS NOT NULL AND TRIM(ta.Equipe) <> ''
          AND UPPER(TRIM(tn.Equipe)) <> UPPER(TRIM(ta.Equipe))
    """

    SQL_UPSERT = """
        INSERT INTO Tb_Correcao_Feedback
            (Id_Glpi, Titulo, Categoria, Descricao, Localizacao,
             Equipe_SGC, Equipe_Correta, Tecnico_Fechamento, Data_Deteccao)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            Titulo = VALUES(Titulo),
            Categoria = VALUES(Categoria),
            Descricao = VALUES(Descricao),
            Localizacao = VALUES(Localizacao),
            Equipe_SGC = VALUES(Equipe_SGC),
            Equipe_Correta = VALUES(Equipe_Correta),
            Tecnico_Fechamento = VALUES(Tecnico_Fechamento),
            Data_Deteccao = VALUES(Data_Deteccao)
    """

    def __init__(self, dal: DAL = None):
        self.dal = dal or DAL(app_name="CorrecaoFeedback", nome_arquivo_config="sgc.dat")
        self.ultimo_total_detectado = 0
        self.ultimo_total_gravado = 0

    def detectar_e_gravar(self) -> int:
        ClDbMigracao(dal=self.dal).aplicar_fase3()
        gravados = 0
        try:
            self.dal.delete(self.SQL_LIMPAR_ACERTOS)

            df = self.dal.read(self.SQL_CANDIDATOS)
            if df is None or df.empty:
                self.ultimo_total_detectado = 0
                self.ultimo_total_gravado = 0
                return 0

            df = df[
                df.apply(
                    lambda row: errou_classificacao_equipe(
                        normalizar_equipe(row.get("Equipe_SGC", "")),
                        normalizar_equipe(row.get("Equipe_Correta", "")),
                    ),
                    axis=1,
                )
            ]
            if df.empty:
                self.ultimo_total_detectado = 0
                self.ultimo_total_gravado = 0
                return 0

            self.ultimo_total_detectado = len(df)
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for _, row in df.iterrows():
                params = (
                    int(row["Id_Glpi"]),
                    str(row.get("Titulo", ""))[:500],
                    str(row.get("Categoria", ""))[:500],
                    str(row.get("Descricao", ""))[:2500],
                    str(row.get("Localizacao", "") or "")[:500],
                    str(row.get("Equipe_SGC", ""))[:5],
                    str(row.get("Equipe_Correta", ""))[:5],
                    str(row.get("Tecnico_Fechamento", ""))[:20],
                    agora,
                )
                if self.dal.create(self.SQL_UPSERT, params):
                    gravados += 1

            self.ultimo_total_gravado = gravados
            self.logger.registrarActionLog(
                "CORRECAO",
                "ATIVIDADE",
                f"CORREÇÕES DETECTADAS: {self.ultimo_total_detectado} | GRAVADAS: {gravados}",
            )
            return gravados
        except Exception as e:
            self.logger.registarExceptionLog("CORRECAO", "EXCEPTION", "FALHA AO DETECTAR CORREÇÕES", e)
            return gravados

    def contar_correcoes(self) -> int:
        df = self.dal.read("SELECT COUNT(*) AS cnt FROM Tb_Correcao_Feedback")
        if df is None or df.empty:
            return 0
        return int(df.iloc[0]["cnt"])
