# ML.py (Fase 1 + re-treino validado e sincronização com produção)

import re
import pickle
import shutil
from collections import Counter
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from DAL import DAL
from logger import ClLog
from FeedbackChamados import ClFeedbackChamados
from DbMigracao import ClDbMigracao
from ModelVersionamento import ClModelVersionamento
from CorrecaoFeedback import ClCorrecaoFeedback
from paths import MODEL_DIR

MODEL_VERSION = 3
PESO_CORRECAO_TREINO = ClCorrecaoFeedback.PESO_TREINO
MIN_TEXTO_TREINO = 20
TITULOS_IGNORADOS = {"teste", "test", "n/a", "...", "sem titulo", "sem título"}
MARGIN_MIN = 0.15
MAJORITY_THRESHOLD = 0.70
DEFAULT_THRESHOLD = 0.55
RARE_THRESHOLD = 0.40
MAJORITY_RATIO = 0.40
RARE_RATIO = 0.02
MIN_F1_MACRO = 0.35
MIN_SAMPLES_VALIDATION = 30
MIN_CLASS_SAMPLES_STRATIFY = 2
F1_REGRESSION_TOLERANCE = 0.01

MODELO_DIR = MODEL_DIR
MODELO_ATIVO = MODEL_DIR / "ModeloML.pkl"
MODELO_BACKUP = MODEL_DIR / "ModeloML_backup.pkl"
MODELO_CANDIDATO = MODEL_DIR / "ModeloML_candidato.pkl"


class ClML:
    logger = ClLog()

    def __init__(self):
        self._precisao = 0.0
        self._ultima_margem = 0.0
        self._ultima_equipe_segunda = ""
        self._ultima_equipe_ml_bruta = ""
        self._ultimo_motivo_rejeicao = ""
        self._ultimo_f1_macro = None
        self._ultimos_feedback_sync = 0
        self._ultimos_feedback_treino = 0
        self.dal = DAL(app_name="Modulo_ML", nome_arquivo_config="sgc.dat")

    @property
    def precisao(self):
        return self._precisao

    @precisao.setter
    def precisao(self, value):
        self._precisao = value

    @property
    def ultima_margem(self):
        return self._ultima_margem

    @property
    def ultima_equipe_segunda(self):
        return self._ultima_equipe_segunda

    @property
    def ultima_equipe_ml_bruta(self):
        return self._ultima_equipe_ml_bruta

    @property
    def ultimo_motivo_rejeicao(self):
        return self._ultimo_motivo_rejeicao

    @property
    def ultimo_f1_macro(self):
        return self._ultimo_f1_macro

    @property
    def ultimos_feedback_sync(self):
        return self._ultimos_feedback_sync

    @property
    def ultimos_feedback_treino(self):
        return self._ultimos_feedback_treino

    @staticmethod
    def preparar_texto_ml(titulo, categoria, descricao, localizacao=None) -> str:
        """Normaliza campos de forma idêntica no treino e na inferência (Fase 2: + localização)."""
        partes = []

        def _norm(valor):
            texto = BeautifulSoup(str(valor), "html.parser").get_text(separator=" ")
            return re.sub(r"\s+", " ", texto).strip().lower()

        loc = _norm(localizacao) if localizacao else ""
        if loc and loc not in ("n/a", "na"):
            partes.append(f"[loc] {loc}")

        cat = _norm(categoria)
        if cat and cat not in ("n/a", "na"):
            partes.append(f"[cat] {cat}")

        for campo in (titulo, descricao):
            texto = _norm(campo)
            if texto and texto not in ("n/a", "na"):
                partes.append(texto)

        return " ".join(partes)

    @classmethod
    def _registro_valido_treino(cls, titulo, categoria, descricao, localizacao=None) -> bool:
        titulo_limpo = str(titulo).strip().lower()
        if titulo_limpo in TITULOS_IGNORADOS or len(titulo_limpo) < 3:
            return False
        texto = cls.preparar_texto_ml(titulo, categoria, descricao, localizacao)
        return len(texto) >= MIN_TEXTO_TREINO

    @staticmethod
    def _calcular_limiares(classes):
        counts = Counter(classes)
        total = len(classes)
        thresholds = {}

        for cls, count in counts.items():
            ratio = count / total
            if ratio >= MAJORITY_RATIO:
                thresholds[cls] = MAJORITY_THRESHOLD
            elif ratio <= RARE_RATIO:
                thresholds[cls] = RARE_THRESHOLD
            else:
                thresholds[cls] = DEFAULT_THRESHOLD

        return thresholds, dict(counts)

    def _ler_f1_modelo_arquivo(self, caminho: Path):
        if not caminho.exists():
            return None
        try:
            with open(caminho, "rb") as f:
                loaded = pickle.load(f)
            if isinstance(loaded, tuple) and len(loaded) == 4:
                return loaded[3].get("f1_macro")
        except Exception:
            return None
        return None

    def _ler_f1_modelo_atual(self):
        return self._ler_f1_modelo_arquivo(MODELO_ATIVO)

    def _preparar_dataset(self, datatable):
        texts = []
        labels = []
        weights = []
        for _, row in datatable.iterrows():
            loc = row.get("Localizacao") if "Localizacao" in row.index else None
            if not self._registro_valido_treino(row["t1"], row["t2"], row["t3"], loc):
                continue
            texts.append(self.preparar_texto_ml(row["t1"], row["t2"], row["t3"], loc))
            labels.append(str(row["cl"]).strip().upper())
            peso = row.get("_peso", 1.0) if "_peso" in row.index else 1.0
            try:
                weights.append(float(peso))
            except (TypeError, ValueError):
                weights.append(1.0)
        return texts, labels, weights

    def _fit_modelo(self, texts, labels, f1_macro=None, row_weights=None):
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
        )
        X = vectorizer.fit_transform(texts)

        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(labels)
        sample_weight = compute_sample_weight(class_weight="balanced", y=y)
        if row_weights is not None and len(row_weights) == len(sample_weight):
            sample_weight = [sw * rw for sw, rw in zip(sample_weight, row_weights)]

        classifier = ComplementNB()
        classifier.fit(X, y, sample_weight=sample_weight)

        thresholds, class_counts = self._calcular_limiares(labels)
        metadata = {
            "version": MODEL_VERSION,
            "margin_min": MARGIN_MIN,
            "thresholds": thresholds,
            "class_counts": class_counts,
            "f1_macro": f1_macro,
            "train_samples": len(texts),
        }
        return classifier, vectorizer, label_encoder, metadata

    def _avaliar_f1_macro_holdout(self, texts, labels):
        counts = Counter(labels)
        if len(texts) < MIN_SAMPLES_VALIDATION:
            return None
        if len(counts) < 2:
            return None
        if min(counts.values()) < MIN_CLASS_SAMPLES_STRATIFY:
            return None

        indices = list(range(len(texts)))
        train_idx, test_idx = train_test_split(
            indices,
            test_size=0.2,
            random_state=42,
            stratify=labels,
        )

        train_texts = [texts[i] for i in train_idx]
        train_labels = [labels[i] for i in train_idx]
        test_texts = [texts[i] for i in test_idx]
        test_labels = [labels[i] for i in test_idx]

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
        )
        X_train = vectorizer.fit_transform(train_texts)
        X_test = vectorizer.transform(test_texts)

        label_encoder = LabelEncoder()
        y_train = label_encoder.fit_transform(train_labels)
        y_test = label_encoder.transform(test_labels)
        sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)

        classifier = ComplementNB()
        classifier.fit(X_train, y_train, sample_weight=sample_weight)
        y_pred = classifier.predict(X_test)
        return float(f1_score(y_test, y_pred, average="macro", zero_division=0))

    def _salvar_modelo(self, pacote, destino=MODELO_ATIVO):
        MODELO_DIR.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as f:
            pickle.dump(pacote, f)

    def _implantar_modelo(self, pacote):
        MODELO_DIR.mkdir(parents=True, exist_ok=True)
        if MODELO_ATIVO.exists():
            shutil.copy2(MODELO_ATIVO, MODELO_BACKUP)
        self._salvar_modelo(pacote, MODELO_ATIVO)
        ClModelVersionamento().registrar_implantacao(pacote[3])

    def _modelo_pode_ser_implantado(self, f1_novo, forcar_implantacao=False):
        f1_anterior = self._ler_f1_modelo_atual()

        if forcar_implantacao:
            if f1_novo is not None and f1_novo < MIN_F1_MACRO:
                return False, f"F1-macro {f1_novo:.3f} abaixo do mínimo {MIN_F1_MACRO:.3f}"
            f1_msg = f"{f1_novo:.3f}" if f1_novo is not None else "N/A"
            return True, f"implantação forçada (F1-macro={f1_msg})"

        if f1_novo is None:
            if f1_anterior is None:
                return True, "primeiro modelo (validação hold-out indisponível)"
            return False, "validação indisponível e já existe modelo ativo"

        if f1_novo < MIN_F1_MACRO:
            return False, f"F1-macro {f1_novo:.3f} abaixo do mínimo {MIN_F1_MACRO:.3f}"

        if f1_anterior is not None and f1_novo < (f1_anterior - F1_REGRESSION_TOLERANCE):
            return (
                False,
                f"F1-macro {f1_novo:.3f} pior que o modelo ativo {f1_anterior:.3f}",
            )

        if f1_anterior is None:
            return True, f"primeiro modelo aprovado (F1-macro={f1_novo:.3f})"

        return True, f"modelo aprovado (F1-macro {f1_novo:.3f} | anterior {f1_anterior:.3f})"

    def pesquisar_dados_treinamento_ml(self):
        """
        Dataset de treino exclusivamente a partir de chamados FECHADOS no GLPI.
        A equipe (cl) é inferida pelo técnico atribuído via Tb_Atrib — o GLPI não informa equipe.
        """
        try:
            sql_feedback = """
                SELECT
                    fb.Titulo AS t1,
                    fb.Categoria AS t2,
                    fb.Descricao AS t3,
                    fb.Localizacao AS Localizacao,
                    UPPER(TRIM(ta.Equipe)) AS cl
                FROM Tb_Ticket_Feedback_Temp fb
                INNER JOIN Tb_Atrib ta ON UPPER(TRIM(ta.Usuario)) = UPPER(TRIM(fb.Tecnico))
                WHERE fb.Tecnico IS NOT NULL
                  AND TRIM(fb.Tecnico) <> ''
                  AND ta.Equipe IS NOT NULL
                  AND TRIM(ta.Equipe) <> ''
            """
            df = self.dal.read(sql_feedback)
            if df is None or df.empty:
                self._ultimos_feedback_treino = 0
                self.logger.registrarActionLog(
                    "ML",
                    "AVISO",
                    "NENHUM CHAMADO FECHADO DO GLPI COM EQUIPE IDENTIFICADA (Tb_Atrib).",
                )
                return pd.DataFrame()

            df = df.copy()
            df["cl"] = df["cl"].astype(str).str.strip().str.upper()
            df = df[df["cl"] != ""]
            df["_peso"] = 1.0

            if self._tabela_existe("Tb_Correcao_Feedback"):
                sql_cor = """
                    SELECT
                        cf.Titulo AS t1,
                        cf.Categoria AS t2,
                        cf.Descricao AS t3,
                        cf.Localizacao AS Localizacao,
                        UPPER(TRIM(cf.Equipe_Correta)) AS cl
                    FROM Tb_Correcao_Feedback cf
                    WHERE cf.Equipe_Correta IS NOT NULL AND TRIM(cf.Equipe_Correta) <> ''
                """
                df_cor = self.dal.read(sql_cor)
                if df_cor is not None and not df_cor.empty:
                    df_cor = df_cor.copy()
                    df_cor["cl"] = df_cor["cl"].astype(str).str.strip().str.upper()
                    df_cor = df_cor[df_cor["cl"] != ""]
                    df_cor["_peso"] = PESO_CORRECAO_TREINO
                    df = pd.concat([df, df_cor], ignore_index=True)
                    self.logger.registrarActionLog(
                        "ML",
                        "ATIVIDADE",
                        f"CORREÇÕES INCLUÍDAS NO TREINO: {len(df_cor)} (PESO {PESO_CORRECAO_TREINO}x)",
                    )

            chaves = []
            for _, row in df.iterrows():
                loc = row.get("Localizacao") if "Localizacao" in row.index else None
                chaves.append(f"{self.preparar_texto_ml(row['t1'], row['t2'], row['t3'], loc)}|{row['cl']}")
            df["_chave"] = chaves
            df = df.sort_values("_peso", ascending=False)
            df = df.drop_duplicates(subset=["_chave"], keep="first")
            df = df.drop(columns=["_chave"], errors="ignore")

            self._ultimos_feedback_treino = len(df)
            self.logger.registrarActionLog(
                "ML",
                "ATIVIDADE",
                f"DATASET TREINO (SOMENTE GLPI FECHADO): {len(df)} REGISTROS",
            )
            return df
        except Exception as e:
            self.logger.registarExceptionLog("ML", "EXCEPTION", "Falha ao pesquisar dados de treinamento via DAL", e)
            return pd.DataFrame()

    def _tabela_existe(self, tabela: str) -> bool:
        df = self.dal.read("SHOW TABLES LIKE %s", (tabela,))
        return df is not None and not df.empty

    def sincronizar_feedback_glpi(self, trade, meses: int = 6) -> int:
        if trade is None:
            self.logger.registrarActionLog("ML", "AVISO", "SYNC FEEDBACK IGNORADO: CONEXÃO GLPI INDISPONÍVEL")
            return 0
        feedback = ClFeedbackChamados(trade=trade, dal=self.dal)
        total = feedback.sincronizar_glpi(meses=meses)
        self._ultimos_feedback_sync = total
        return total

    def treinar_modelo(self, datatable, forcar_implantacao=False):
        try:
            if datatable is None or datatable.empty:
                self.logger.registrarActionLog("ML", "AVISO", "O DataFrame para treinamento está vazio. O treinamento foi ignorado.")
                return False

            texts, labels, weights = self._preparar_dataset(datatable)
            if not texts:
                self.logger.registrarActionLog("ML", "AVISO", "Nenhum registro válido após pré-processamento.")
                return False

            f1_novo = self._avaliar_f1_macro_holdout(texts, labels)
            self._ultimo_f1_macro = f1_novo

            pode_implantar, motivo = self._modelo_pode_ser_implantado(f1_novo, forcar_implantacao)
            if not pode_implantar:
                self.logger.registrarActionLog("ML", "AVISO", f"MODELO NÃO IMPLANTADO: {motivo}")
                return False

            pacote = self._fit_modelo(texts, labels, f1_macro=f1_novo, row_weights=weights)
            self._implantar_modelo(pacote)

            f1_msg = f"{f1_novo:.3f}" if f1_novo is not None else "N/A"
            self.logger.registrarActionLog(
                "ML",
                "ATIVIDADE",
                (
                    f"MODELO IMPLANTADO: {len(texts)} REGISTROS | CLASSES: {len(pacote[3]['class_counts'])} | "
                    f"F1-MACRO: {f1_msg} | {motivo.upper()}"
                ),
            )
            return True
        except Exception as e:
            self.logger.registarExceptionLog("ML", "EXCEPTION", "Erro ao treinar modelo", e)
            return False

    def le_modelo_ml(self):
        try:
            if not MODELO_ATIVO.exists():
                self.logger.registrarActionLog("ML", "AVISO", f"Arquivo de modelo não encontrado em: {MODELO_ATIVO}")
                return None, None, None, None

            with open(MODELO_ATIVO, "rb") as f:
                loaded = pickle.load(f)

            if not isinstance(loaded, tuple):
                self.logger.registrarActionLog("ML", "AVISO", "Formato de modelo inválido. Re-treine o modelo.")
                return None, None, None, None

            if len(loaded) == 3:
                self.logger.registrarActionLog(
                    "ML",
                    "AVISO",
                    "Modelo legado (Hummingbird) detectado. Execute geracao_automatica_modelo para atualizar.",
                )
                return None, None, None, None

            if len(loaded) != 4:
                self.logger.registrarActionLog("ML", "AVISO", "Estrutura do modelo incompatível. Re-treine o modelo.")
                return None, None, None, None

            classifier, vectorizer, label_encoder, metadata = loaded
            if metadata.get("version") != MODEL_VERSION:
                self.logger.registrarActionLog(
                    "ML",
                    "AVISO",
                    (
                        f"Modelo v{metadata.get('version')} incompatível com v{MODEL_VERSION}. "
                        "Execute TreinarModeloNovo.py para atualizar."
                    ),
                )
                return None, None, None, None

            self.logger.registrarActionLog("ML", "ATIVIDADE", "Modelo de Machine Learning carregado com sucesso.")
            return classifier, vectorizer, label_encoder, metadata
        except Exception as e:
            self.logger.registarExceptionLog("ML", "EXCEPTION", f"Erro inesperado ao ler o modelo: {MODELO_ATIVO}", e)
            return None, None, None, None

    def _avaliar_predicao(self, proba, label_encoder, metadata):
        top_indices = proba.argsort()[-2:][::-1]
        top1_idx = top_indices[0]
        top1_prob = float(proba[top1_idx])
        top2_prob = float(proba[top_indices[1]]) if len(top_indices) > 1 else 0.0
        margin = top1_prob - top2_prob

        predicted_class = label_encoder.inverse_transform([top1_idx])[0]
        self._ultima_equipe_ml_bruta = predicted_class
        self._precisao = top1_prob * 100
        self._ultima_margem = margin * 100
        self._ultima_equipe_segunda = (
            label_encoder.inverse_transform([top_indices[1]])[0] if len(top_indices) > 1 else ""
        )

        margin_min = metadata.get("margin_min", MARGIN_MIN)
        threshold = metadata.get("thresholds", {}).get(predicted_class, DEFAULT_THRESHOLD)

        if margin < margin_min:
            self._ultimo_motivo_rejeicao = (
                f"margem baixa entre '{predicted_class}' e '{self._ultima_equipe_segunda}' ({margin:.1%})"
            )
            return "I"

        if top1_prob < threshold:
            self._ultimo_motivo_rejeicao = (
                f"confiança {top1_prob:.1%} abaixo do limiar {threshold:.1%} para equipe '{predicted_class}'"
            )
            return "I"

        self._ultimo_motivo_rejeicao = ""
        return predicted_class

    def executar_classificacao_texto(self, modelo_completo, texto):
        try:
            if not modelo_completo or modelo_completo[0] is None:
                self.logger.registrarActionLog("ML", "AVISO", "Modelo não carregado. Classificação ignorada.")
                return ""

            if not texto or not str(texto).strip():
                self.logger.registrarActionLog("ML", "AVISO", "Texto vazio para classificação.")
                return ""

            classifier, vectorizer, label_encoder, metadata = modelo_completo
            input_data = vectorizer.transform([texto])
            proba = classifier.predict_proba(input_data)[0]
            equipe = self._avaliar_predicao(proba, label_encoder, metadata)

            if equipe == "I":
                self.logger.registrarActionLog(
                    "ML",
                    "AVISO",
                    f"CLASSIFICAÇÃO REJEITADA: {self._ultimo_motivo_rejeicao}",
                )
            else:
                self.logger.registrarActionLog(
                    "ML",
                    "ATIVIDADE",
                    (
                        f"EQUIPE PREVISTA: {equipe} | CONFIANÇA: {self._precisao:.1f}% | "
                        f"MARGEM: {self._ultima_margem:.1f}% | 2ª OPÇÃO: {self._ultima_equipe_segunda}"
                    ),
                )

            return equipe
        except Exception as e:
            self.logger.registarExceptionLog("ML", "EXCEPTION", "ERRO NA CLASSIFICAÇÃO DE TEXTO", e)
            print(f"erro no ML:{e}")
            return ""

    def classificar_chamado(self, modelo_completo, titulo, categoria, descricao, localizacao=None):
        """Pré-processa o chamado e executa a classificação com o pipeline unificado."""
        det = self.classificar_chamado_detalhado(modelo_completo, titulo, categoria, descricao, localizacao)
        return det.get("equipe", "")

    def classificar_chamado_detalhado(self, modelo_completo, titulo, categoria, descricao, localizacao=None):
        """Retorna equipe e metadados da predição (inclusive quando rejeitada)."""
        det = {
            "equipe": "",
            "equipe_ml_bruta": "",
            "equipe_2a": "",
            "confianca": 0.0,
            "margem": 0.0,
            "motivo_rejeicao": "",
        }
        if not modelo_completo or modelo_completo[0] is None:
            return det

        texto = self.preparar_texto_ml(titulo, categoria, descricao, localizacao)
        if not texto or not str(texto).strip():
            return det

        equipe = self.executar_classificacao_texto(modelo_completo, texto)
        det["equipe"] = equipe
        det["equipe_ml_bruta"] = self._ultima_equipe_ml_bruta or equipe
        det["equipe_2a"] = self._ultima_equipe_segunda
        det["confianca"] = self._precisao
        det["margem"] = self._ultima_margem
        det["motivo_rejeicao"] = self._ultimo_motivo_rejeicao
        return det

    def geracao_automatica_modelo(
        self,
        trade=None,
        meses_feedback=6,
        sincronizar_feedback=True,
        forcar_implantacao=False,
    ):
        """
        Pipeline de aprendizado: importa chamados FECHADOS do GLPI e treina o modelo
        exclusivamente com esses dados. A equipe é derivada do técnico via Tb_Atrib.
        """
        try:
            ClDbMigracao(dal=self.dal).aplicar_migracao_ambiente()

            if sincronizar_feedback:
                if trade is None:
                    self.logger.registrarActionLog(
                        "ML",
                        "AVISO",
                        "SYNC FEEDBACK GLPI IGNORADA (SEM CONEXÃO). USANDO DADOS LOCAIS EXISTENTES.",
                    )
                else:
                    self.logger.registrarActionLog(
                        "ML",
                        "AUTO-APRENDIZADO",
                        "SINCRONIZANDO CHAMADOS FECHADOS DO GLPI (ÚNICA FONTE DE APRENDIZADO)...",
                    )
                    self.sincronizar_feedback_glpi(trade, meses=meses_feedback)

            ClCorrecaoFeedback(dal=self.dal).detectar_e_gravar()

            self.logger.registrarActionLog("ML", "AUTO-APRENDIZADO", "Montando dataset a partir do GLPI fechado...")
            dt = self.pesquisar_dados_treinamento_ml()

            if dt is not None and not dt.empty:
                self.logger.registrarActionLog(
                    "ML",
                    "AUTO-APRENDIZADO",
                    f"Total de {len(dt)} registros encontrados para treinamento.",
                )
                self.logger.registrarActionLog("ML", "AUTO-APRENDIZADO", "Iniciando treinamento do modelo...")

                if self.treinar_modelo(dt, forcar_implantacao=forcar_implantacao):
                    self.logger.registrarActionLog("ML", "AUTO-APRENDIZADO", "Modelo treinado e implantado com sucesso!")
                    return True

                self.logger.registrarActionLog("ML", "ERRO", "Treinamento concluído sem implantar novo modelo.")
                return False

            self.logger.registrarActionLog(
                "ML",
                "AVISO",
                "TREINO ABORTADO: SINCRONIZE CHAMADOS FECHADOS DO GLPI (SincronizarFeedbackGLPI.py).",
            )
            return False
        except Exception as e:
            self.logger.registarExceptionLog(
                "ML",
                "EXCEPTION",
                "Um erro crítico ocorreu durante a geração automática do modelo.",
                e,
            )
            return False


if __name__ == "__main__":
    try:
        print("Iniciando processo de treinamento manual...")
        clml = ClML()
        clml.geracao_automatica_modelo(forcar_implantacao=True)
        print("Processo finalizado.")
    except Exception as e:
        print(f"Ocorreu um erro na execução principal: {e}")
