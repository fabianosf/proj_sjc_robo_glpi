# MetodosGenericos.py (Versão com a Modificação Solicitada)

from datetime import datetime, timedelta
import pandas as pd
from DAL import DAL
from trade import ClTrade
import re
import os

from paths import ARQAUX_FILE
from arqaux_rules import load_rules_as_tuples
from typing import Optional


def _env_logins(env_key: str, default: tuple) -> tuple:
    raw = (os.getenv(env_key) or "").strip()
    if not raw:
        return default
    items = tuple(x.strip() for x in raw.split(",") if x.strip())
    return items or default


class ClMetodosGenericos:
    EQUIPE_FALLBACK = "N1"
    _EQUIPE_INVALIDA = "I"
    # Categorias de Comunicação Interna → somente estas técnicas (menor carga / no horário)
    KEYWORDS_COMUNICACAO_INTERNA = (
        "COMUNICAÇÃO INTERNA",
        "COMUNICACAO INTERNA",
        "SOLICITAÇÃO DE COMUNICAÇÃO INTERNA",
        "SOLICITACAO DE COMUNICACAO INTERNA",
        "ATUALIZAÇÃO DE MIDIA",
        "ATUALIZAÇÃO DE MÍDIA",
        "ATUALIZACAO DE MIDIA",
        "TELEVISORES",
    )
    # Override: SGC_TECNICOS_COMUNICACAO / SGC_TECNICOS_CELULAR (CSV de logins)
    TECNICOS_COMUNICACAO_INTERNA = _env_logins(
        "SGC_TECNICOS_COMUNICACAO", ("ana.neves", "maria.galdino")
    )
    TECNICOS_CELULAR_MANUTENCAO = _env_logins(
        "SGC_TECNICOS_CELULAR", ("samuel.jesus",)
    )

    def __init__(self, trade_instance: ClTrade):
        self.trade = trade_instance
        self._tem_dat_reg: Optional[bool] = None
        try:
            self.dal_sgc = DAL(app_name="SGC_DB", nome_arquivo_config="sgc.dat")
        except Exception as e:
            print(f"ERRO CRÍTICO NA INICIALIZAÇÃO DO DAL: {e}")
            raise

    @classmethod
    def _equipe_atribuivel(cls, equipe: str) -> bool:
        eq = (equipe or "").strip().upper()
        return bool(eq) and eq != cls._EQUIPE_INVALIDA

    @classmethod
    def _eh_chamado_comunicacao_interna(cls, titulo: str = "", categoria: str = "") -> bool:
        texto = f"{titulo or ''} {categoria or ''}"
        return any(
            cls._palavra_inteira_no_texto(kw, texto)
            for kw in cls.KEYWORDS_COMUNICACAO_INTERNA
        )

    @staticmethod
    def _hora_no_expediente(hora_atual, h1, h2) -> bool:
        """True se hora_atual está em [h1, h2], inclusive turnos que cruzam meia-noite."""
        if h1 <= h2:
            return h1 <= hora_atual <= h2
        return hora_atual >= h1 or hora_atual <= h2

    @staticmethod
    def _palavra_inteira_no_texto(palavra_chave: str, texto: str) -> bool:
        """Verifica se a palavra/frase-chave aparece como termo inteiro no texto."""
        palavra_chave = (palavra_chave or "").strip()
        texto = texto or ""
        if not palavra_chave or not texto:
            return False
        pattern = rf"(?<!\w){re.escape(palavra_chave)}(?!\w)"
        return bool(re.search(pattern, texto, re.IGNORECASE))

    @staticmethod
    def _limpar_descricao_html(descricao: str) -> str:
        return re.sub(re.compile("<.*?>"), "", descricao or "").replace("\xa0", " ")

    # ... (outros métodos permanecem inalterados) ...
    
    def _sql_tecnicos_equipe(self, ref_eq: str, ref_loc: str):
        """SQL da equipe ativa. Localização não filtra no SQL (Empresa é char curto)."""
        sql = (
            "SELECT TRIM(Usuario) as Usuario, H1, H2, QtdC, Empresa FROM Tb_Atrib "
            "WHERE UPPER(TRIM(Equipe)) = %s AND (Sit = 1 OR Sit = '1')"
        )
        return sql, (ref_eq.strip().upper(),)

    @staticmethod
    def _norm_loc(texto: str) -> str:
        t = (texto or "").strip().upper()
        for a, b in (
            ("ÇÃO", "CAO"),
            ("Á", "A"),
            ("Ã", "A"),
            ("É", "E"),
            ("Í", "I"),
            ("Ó", "O"),
            ("Ú", "U"),
        ):
            t = t.replace(a, b)
        return t

    def _empresa_casa_localizacao(self, empresa: str, localizacao: str) -> bool:
        loc = self._norm_loc(localizacao)
        emp = self._norm_loc(empresa)
        if not loc or loc in ("N/A",) or not emp:
            return False
        if emp in loc or loc in emp:
            return True
        for token in ("REDENTOR", "FUTURO", "BARRA"):
            if token in loc and token in emp:
                return True
        return False

    def _listar_tecnicos_fixos(self, logins: tuple) -> list:
        """Retorna logins ativos e no horário, ordenados por menor carga (QtdC)."""
        if not logins:
            return []
        try:
            hora_atual_obj = datetime.now().time()
            placeholders = ", ".join(["%s"] * len(logins))
            sql = (
                f"SELECT TRIM(Usuario) as Usuario, H1, H2, QtdC FROM Tb_Atrib "
                f"WHERE Sit = 1 AND UPPER(TRIM(Usuario)) IN ({placeholders})"
            )
            params = tuple(u.strip().upper() for u in logins)
            dteq = self.dal_sgc.read(sql, params)
            if dteq is None or dteq.empty:
                print(
                    f"--- [FALHA] Nenhum dos técnicos fixos {list(logins)} "
                    "está ativo (Sit=1) em Tb_Atrib."
                )
                return []

            candidatos_por_usuario = {}
            for _, row in dteq.iterrows():
                tecnico_nome = str(row["Usuario"]).strip()
                if not tecnico_nome:
                    continue
                try:
                    h1_str, h2_str = str(row["H1"]).strip(), str(row["H2"]).strip()
                    try:
                        h1_obj = datetime.strptime(h1_str, "%H:%M:%S").time()
                        h2_obj = datetime.strptime(h2_str, "%H:%M:%S").time()
                    except ValueError:
                        h1_obj = datetime.strptime(h1_str, "%H:%M").time()
                        h2_obj = datetime.strptime(h2_str, "%H:%M").time()

                    if self._hora_no_expediente(hora_atual_obj, h1_obj, h2_obj):
                        carga_atual = int(row["QtdC"]) if pd.notna(row["QtdC"]) else 0
                        if (
                            tecnico_nome not in candidatos_por_usuario
                            or carga_atual < candidatos_por_usuario[tecnico_nome]
                        ):
                            candidatos_por_usuario[tecnico_nome] = carga_atual
                except Exception as e:
                    print(
                        f"--- [ERRO] Falha ao processar horário do técnico '{tecnico_nome}': {e}. "
                        "O técnico será ignorado."
                    )

            if not candidatos_por_usuario:
                print(
                    f"--- [FALHA] Nenhum de {list(logins)} está no horário de trabalho atual."
                )
                return []

            return [
                usuario
                for usuario, _ in sorted(
                    candidatos_por_usuario.items(), key=lambda item: item[1]
                )
            ]
        except Exception as e:
            print(f"--- [ERRO FATAL] Erro ao listar técnicos fixos: {e}")
            return []

    def listar_tecnicos_elegiveis_equipe(
        self, ref_eq: str, ref_tit: str, ref_loc: str, categoria: str = ""
    ) -> list:
        """
        Retorna técnicos ativos da equipe, no horário de trabalho, ordenados por menor carga (QtdC).
        Sem duplicatas de login.
        """
        if self._eh_chamado_comunicacao_interna(ref_tit, categoria):
            print(
                "[ASSIGN-LOGIC] Comunicação Interna: candidatos fixos "
                f"{list(self.TECNICOS_COMUNICACAO_INTERNA)}"
            )
            return self._listar_tecnicos_fixos(self.TECNICOS_COMUNICACAO_INTERNA)

        if not ref_eq or not str(ref_eq).strip():
            return []

        palavras_chave_preferenciais = ["consert", "repar", "celular", "manutenção", "telefone", "tela"]
        if sum(1 for p in palavras_chave_preferenciais if p in (ref_tit or "").lower()) >= 2:
            print(
                "[ASSIGN-LOGIC] Preferência celular/manutenção: "
                f"{list(self.TECNICOS_CELULAR_MANUTENCAO)} (Sit=1 e horário)."
            )
            return self._listar_tecnicos_fixos(self.TECNICOS_CELULAR_MANUTENCAO)

        try:
            hora_atual_obj = datetime.now().time()
            sql_tecnicos_equipe, sql_params = self._sql_tecnicos_equipe(ref_eq, ref_loc)
            dteq = self.dal_sgc.read(sql_tecnicos_equipe, sql_params)

            if dteq is None or dteq.empty:
                print(
                    f"--- [FALHA] Nenhum técnico ATIVO (Sit=1) foi encontrado no banco de dados "
                    f"para a equipe '{ref_eq}'. Verifique a tabela Tb_Atrib."
                )
                return []

            candidatos_por_usuario = {}
            for _, row in dteq.iterrows():
                tecnico_nome = str(row["Usuario"]).strip()
                if not tecnico_nome:
                    continue
                try:
                    h1_str, h2_str = str(row["H1"]).strip(), str(row["H2"]).strip()
                    try:
                        h1_obj = datetime.strptime(h1_str, "%H:%M:%S").time()
                        h2_obj = datetime.strptime(h2_str, "%H:%M:%S").time()
                    except ValueError:
                        h1_obj = datetime.strptime(h1_str, "%H:%M").time()
                        h2_obj = datetime.strptime(h2_str, "%H:%M").time()

                    if self._hora_no_expediente(hora_atual_obj, h1_obj, h2_obj):
                        carga_atual = int(row["QtdC"]) if pd.notna(row["QtdC"]) else 0
                        emp = ""
                        if "Empresa" in row.index:
                            emp = str(row["Empresa"] or "").strip()
                        prev = candidatos_por_usuario.get(tecnico_nome)
                        if prev is None or carga_atual < prev[0]:
                            candidatos_por_usuario[tecnico_nome] = (carga_atual, emp)
                except Exception as e:
                    print(
                        f"--- [ERRO] Falha ao processar horário do técnico '{tecnico_nome}': {e}. "
                        "O técnico será ignorado."
                    )

            if not candidatos_por_usuario:
                print(
                    f"--- [FALHA] Nenhum técnico da equipe '{ref_eq}' foi encontrado "
                    "no horário de trabalho atual."
                )
                return []

            ordered = sorted(
                candidatos_por_usuario.items(), key=lambda item: item[1][0]
            )
            prefer = [
                usuario
                for usuario, (_carga, emp) in ordered
                if self._empresa_casa_localizacao(emp, ref_loc)
            ]
            todos = [usuario for usuario, _meta in ordered]
            if prefer:
                rest = [u for u in todos if u not in prefer]
                print(
                    f"[ASSIGN-LOGIC] Preferência de empresa para '{ref_loc}': {prefer} "
                    f"(fallback: {rest})"
                )
                return prefer + rest
            return todos
        except Exception as e:
            print(f"--- [ERRO FATAL] Erro inesperado ao listar técnicos da equipe: {e}")
            return []

    def verifica_atribuicao_chamado_usuario(
        self, rcha: str, ref_eq: str, ref_tit: str, ref_loc: str, categoria: str = ""
    ) -> str:
        if not ref_loc or ref_loc.strip() == "":
            print("valor localização vazio")

        candidatos = self.listar_tecnicos_elegiveis_equipe(
            ref_eq, ref_tit, ref_loc, categoria=categoria
        )
        return candidatos[0] if candidatos else ""

    # ... (o restante dos métodos de MetodosGenericos.py aqui) ...
    def reset_qtdc_diario(self) -> bool:
        """Zera QtdC de todos os técnicos (balanceamento diário local)."""
        try:
            return bool(self.dal_sgc.update("UPDATE Tb_Atrib SET QtdC = 0"))
        except Exception as e:
            print(f"ERRO AO RESETAR QtdC DIÁRIO: {e}")
            return False

    def decrementarCargaTecnico(self, nome_tecnico: str) -> bool:
        """Decrementa QtdC (mínimo 0) — usado ao sincronizar troca de técnico."""
        try:
            sql_read = "SELECT QtdC FROM Tb_Atrib WHERE UPPER(TRIM(Usuario)) = %s"
            df_qtd = self.dal_sgc.read(sql_read, (nome_tecnico.strip().upper(),))
            if df_qtd is None or df_qtd.empty:
                return False
            valor_atual = int(df_qtd.iloc[0]["QtdC"]) if pd.notna(df_qtd.iloc[0]["QtdC"]) else 0
            novo_valor = max(0, valor_atual - 1)
            return bool(
                self.dal_sgc.update(
                    "UPDATE Tb_Atrib SET QtdC = %s WHERE UPPER(TRIM(Usuario)) = %s",
                    (novo_valor, nome_tecnico.strip().upper()),
                )
            )
        except Exception as e:
            print(f"ERRO AO DECREMENTAR QTD CHAMADOS TÉCNICO: {e}")
            return False

    def _qtdc_tecnicos(self, logins: list) -> dict:
        """Mapa login -> QtdC atual (0 se ausente)."""
        out = {}
        if not logins:
            return out
        try:
            placeholders = ", ".join(["%s"] * len(logins))
            df = self.dal_sgc.read(
                f"SELECT TRIM(Usuario) AS Usuario, QtdC FROM Tb_Atrib "
                f"WHERE UPPER(TRIM(Usuario)) IN ({placeholders})",
                tuple(u.strip().upper() for u in logins),
            )
            if df is None or df.empty:
                return {str(u): 0 for u in logins}
            for _, row in df.iterrows():
                nome = str(row["Usuario"]).strip()
                try:
                    carga = int(row["QtdC"]) if pd.notna(row["QtdC"]) else 0
                except (TypeError, ValueError):
                    carga = 0
                out[nome] = carga
                out[nome.upper()] = carga
        except Exception:
            pass
        return out

    def montar_motivo_atribuicao_pessoa(
        self,
        *,
        equipe: str,
        metodo: str,
        escolhido: str,
        candidatos: list,
        tecnico_fixo: str = "",
        falhas_glpi: list = None,
    ) -> str:
        """Texto curto: por que este técnico ganhou o chamado."""
        eq = (equipe or "").strip().upper() or "?"
        met = (metodo or "").strip().upper() or "?"
        tec = (escolhido or "").strip()
        falhas = list(falhas_glpi or [])
        fixo = (tecnico_fixo or "").strip()

        if fixo and tec and fixo.upper() == tec.upper():
            base = (
                f'Técnico fixo da regra {met} na equipe {eq} '
                f'(pin "{fixo}") → {tec}.'
            )
        else:
            cargas = self._qtdc_tecnicos(list(candidatos or []))
            partes = []
            for c in list(candidatos or [])[:8]:
                q = cargas.get(c, cargas.get(str(c).upper(), 0))
                partes.append(f"{c}(QtdC={q})")
            lista = ", ".join(partes) if partes else "(lista vazia)"
            base = (
                f"Equipe {eq} por {met}. Elegíveis no horário: {lista}. "
                f"Escolhido {tec} (menor carga / ordem da lista)."
            )

        if falhas:
            base += " Falhou no GLPI antes: " + ", ".join(falhas[:5]) + "."
        return base[:500]

    def incrementarCargaTecnico(self, nome_tecnico: str) -> bool:
        try:
            #print(f"Nome técnico:{nome_tecnico}")
            sql_read = "SELECT QtdC FROM Tb_Atrib WHERE UPPER(TRIM(Usuario)) = %s"
            df_qtd = self.dal_sgc.read(sql_read, (nome_tecnico.strip().upper(),))
            if df_qtd is None or df_qtd.empty:
                print(f"FALHA ao ler carga para '{nome_tecnico}'. Usuário não encontrado no DB.")
                return False
            valor_atual = int(df_qtd.iloc[0]['QtdC']) if pd.notna(df_qtd.iloc[0]['QtdC']) else 0
            #print(f"Valor atual:{valor_atual}")
            novo_valor = valor_atual + 1
            #print(f"Valor atual:{novo_valor}")
            sql_update = "UPDATE Tb_Atrib SET QtdC = %s WHERE UPPER(TRIM(Usuario)) = %s"
            params_update = (novo_valor, nome_tecnico.strip().upper())
            return self.dal_sgc.update(sql_update, params_update)
        except Exception as e:
            print(f"ERRO AO ATUALIZAR QTD CHAMADOS TÉCNICO: {e}")
            return False

    def registrar_chamado_novo(
        self,
        ref_cod: int,
        ref_tit: str,
        ref_cat: str,
        ref_des: str,
        ref_dat: str,
        ref_tec: str,
        ref_sol: str,
        ref_dat_sol: str,
        ref_equipe: str = "",
    ) -> bool:
        try:
            if isinstance(ref_dat, pd.Timestamp): ref_dat = ref_dat.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(ref_dat_sol, pd.Timestamp): ref_dat_sol = ref_dat_sol.strftime("%Y-%m-%d %H:%M:%S")
            
            ref_sol_modificado = ref_sol.replace(' ', '.')
            ref_equipe_norm = str(ref_equipe).strip().upper()[:5] if ref_equipe else None
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if self._tem_dat_reg is None:
                try:
                    df_col = self.dal_sgc.read(
                        "SHOW COLUMNS FROM Tb_Ticket_new LIKE %s", ("Dat_Reg",)
                    )
                    self._tem_dat_reg = df_col is not None and not df_col.empty
                except Exception:
                    self._tem_dat_reg = False

            if self._tem_dat_reg:
                sql = (
                    "INSERT INTO Tb_Ticket_new "
                    "(Id, Titulo, Categoria, Descricao, Data, Tecnico, Equipe, Sit, sol, Dat_Sol, Dat_Reg) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, '1', %s, %s, %s)"
                )
                params = (
                    ref_cod, ref_tit.upper(), ref_cat, ref_des, ref_dat,
                    ref_tec, ref_equipe_norm, ref_sol_modificado, ref_dat_sol, agora,
                )
            else:
                sql = (
                    "INSERT INTO Tb_Ticket_new "
                    "(Id, Titulo, Categoria, Descricao, Data, Tecnico, Equipe, Sit, sol, Dat_Sol) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, '1', %s, %s)"
                )
                params = (
                    ref_cod, ref_tit.upper(), ref_cat, ref_des, ref_dat,
                    ref_tec, ref_equipe_norm, ref_sol_modificado, ref_dat_sol,
                )
            return self.dal_sgc.create(sql, params)
        except Exception as e:
            print(f"ERRO AO REGISTRAR CHAMADO: {e}")
            return False
        
    def chamadoExiste(self, ref_cod: int) -> bool:
        """
        True se o chamado já está na base.
        Fail-closed: erro de DB (None) → True (não reatribui no GLPI).
        """
        try:
            sql = "SELECT Id FROM Tb_Ticket_new WHERE Id = %s"
            dt = self.dal_sgc.read(sql, (ref_cod,))
            if dt is None:
                print(
                    f"ERRO AO VERIFICAR CHAMADO {ref_cod}: DAL retornou None "
                    "— fail-closed: tratando como EXISTENTE (não reatribui)."
                )
                return True
            return not dt.empty
        except Exception as e:
            print(
                f"ERRO AO VERIFICAR CHAMADO {ref_cod}: {e} "
                "— fail-closed: tratando como EXISTENTE (não reatribui)."
            )
            return True

    def pesquisar_codigo_usuario(self, ref_usu: str) -> int:
        try:
            user_id = self.trade._get_user_id_by_name(ref_usu)
            return user_id if user_id is not None else 0
        except Exception as e:
            print(f"ERRO AO PESQUISAR USUARIO VIA API: {e}")
            return 0

    def pesquisarChamadosFechados(self, refusu: str) -> int:
        try:
            return self.trade.count_user_tickets_by_status(nome_usuario=refusu, status_id=6)
        except Exception as e:
            print(f"ERRO AO PESQUISAR CHAMADOS FECHADOS VIA API: {e}")
            return 0

    def pesquisarChamadosAtribuidos(self) -> pd.DataFrame:
        try:
            df = self.trade.pesquisarChamadosSituacao(status_id=2)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"ERRO AO PESQUISAR CHAMADOS ATRIBUIDOS VIA API: {e}")
            return pd.DataFrame()

    def monitoraChamados(self, usuario: str):
        try:
            chamados_atribuidos = self.pesquisarChamadosAtribuidos()
            if not chamados_atribuidos.empty:
                for _, row in chamados_atribuidos.iterrows():
                    chaAt = row["ID"]
                    sql_update_sit = f"UPDATE Tb_Ticket_new SET Sit = '1' WHERE id = {chaAt}"
                    self.dal_sgc.update(sql_update_sit)
        except Exception as e:
            print(f"ERRO NO MONITORAMENTO: {e}")

    def pesquisarTecnicosCadastrados(self) -> pd.DataFrame:
        try:
            sql = "SELECT TRIM(Usuario) as Usuario FROM Tb_Atrib"
            df = self.dal_sgc.read(sql)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"ERRO AO PESQUISAR TECNICOS: {e}")
            return pd.DataFrame()

    def confirmar_recepcao_mensagem_tecnico(self, ref_id: int, ref_tip: str, ref_tec: str) -> bool:
        try:
            data_atual_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sql = "INSERT INTO Tb_C (Chamado, Sit, data, tecnico) VALUES (%s, %s, %s, %s)"
            params = (ref_id, ref_tip, data_atual_str, ref_tec)
            sucesso = self.dal_sgc.create(sql, params)
            return sucesso
        except Exception as e:
            print(f"ERRO ao confirmar recepção de mensagem para o chamado {ref_id}: {e}")
            return False
            
    def verifica_prazo_expirado_solucao(self, id_chamado: int) -> bool:
        try:
            data_atual = datetime.now()
            sql_query = "SELECT Dat_Sol FROM Tb_Ticket_new WHERE Id = %s"
            resultado_df = self.dal_sgc.read(sql_query, (id_chamado,))

            if resultado_df is None:
                print(
                    f"AVISO: Falha ao ler Dat_Sol do chamado '{id_chamado}' (DAL None)."
                )
                return False
            if resultado_df.empty:
                print(f"AVISO: Chamado com ID '{id_chamado}' não encontrado no banco de dados.")
                return False

            data_sol = resultado_df['Dat_Sol'].iloc[0]

            if pd.isna(data_sol):
                print(f"AVISO: O chamado ID '{id_chamado}' não possui uma data de solução registrada.")
                return False

            if not isinstance(data_sol, (datetime, pd.Timestamp)):
                 print(f"AVISO: Formato de data inválido para o chamado ID '{id_chamado}'.")
                 return False

            limite_de_tempo = timedelta(minutes=15)
            diferenca_real = abs(data_atual - data_sol)
            
            return diferenca_real < limite_de_tempo
        except Exception as e:
            print(f"ERRO em 'solucao_em_menos_de_15_min' para o chamado {id_chamado}: {e}")
            return False

    def _carregar_regras_arqaux(self):
        """Lista (equipe, keywords, tecnico_opcional) a partir de arqaux.txt."""
        return load_rules_as_tuples(ARQAUX_FILE)

    def definirAtribuicaoParcial(self, titulo: str, categoria: str, descricao: str = "") -> str:
        """Fallback: busca palavras-chave também na descrição; exige vencedor único."""
        descricao_limpa = self._limpar_descricao_html(descricao)
        texto = f"{titulo} {categoria} {descricao_limpa}"
        scores = {}
        for equipe, keywords, _tec in self._carregar_regras_arqaux():
            score = sum(1 for kw in keywords if self._palavra_inteira_no_texto(kw, texto))
            if score > 0:
                scores[equipe] = scores.get(equipe, 0) + score
        if not scores:
            return ""
        melhor = max(scores.values())
        lideres = [eq for eq, sc in scores.items() if sc == melhor]
        if len(lideres) != 1:
            return ""
        return lideres[0]

    def definirAtribuicaoFallbackCategoria(self, categoria: str) -> str:
        cat = (categoria or "").upper()
        mapa = (
            ("IMPRESSORA", "N1"),
            ("MANUTEN", "N1"),
            ("TONER", "N1"),
            ("COMUNICAÇÃO INTERNA", "N5"),
            ("COMUNICACAO INTERNA", "N5"),
            ("TELEVISORES", "N5"),
            ("ATUALIZAÇÃO DE MIDIA", "N5"),
            ("ATUALIZAÇÃO DE MÍDIA", "N5"),
            ("E-MAIL", "N3"),
            ("EMAIL", "N3"),
            ("SENHA", "N3"),
            ("ACESSO REMOTO", "N3"),
            ("CELULAR", "N2"),
            ("NOBREAK", "N2"),
            ("CABEAMENTO", "N2"),
            ("LIMPEZA", "N9"),
            ("AR CONDICIONADO", "N8"),
            ("TREINAMENTO", "N6"),
        )
        for chave, equipe in mapa:
            if chave in cat:
                return equipe
        return ""

    def resolver_equipe_chamado(self, ml, modelo, titulo, categoria, descricao, localizacao):
        """
        Pipeline híbrido Fase 3: arqaux (direto → parcial) → ML → fallback categoria → N1.
        A lista arqaux.txt tem prioridade; ML só quando nenhum termo da lista for localizado.
        Retorna dict com equipe final e metadados para Tb_ML_Log.
        """
        resultado = {
            "equipe": "",
            "metodo": "",
            "equipe_ml": "",
            "equipe_ml_bruta": "",
            "equipe_2a": "",
            "confianca": 0.0,
            "margem": 0.0,
            "motivo_rejeicao": "",
            "tecnico_fixo": "",
        }

        equipe_direta, tecnico_fixo = self.definirAtribuicaoDiretaDetalhada(
            titulo, categoria, descricao
        )
        if self._equipe_atribuivel(equipe_direta):
            resultado["equipe"] = equipe_direta
            resultado["metodo"] = "DIRETO"
            resultado["tecnico_fixo"] = (tecnico_fixo or "").strip()
            return resultado

        parcial = self.definirAtribuicaoParcial(titulo, categoria, descricao)
        if self._equipe_atribuivel(parcial):
            resultado["equipe"] = parcial
            resultado["metodo"] = "FALLBACK_PARCIAL"
            return resultado

        if modelo and modelo[0] is not None:
            det = ml.classificar_chamado_detalhado(modelo, titulo, categoria, descricao, localizacao)
            resultado["equipe_ml"] = det.get("equipe_ml_bruta", "")
            resultado["equipe_ml_bruta"] = det.get("equipe_ml_bruta", "")
            resultado["equipe_2a"] = det.get("equipe_2a", "")
            resultado["confianca"] = det.get("confianca", 0.0)
            resultado["margem"] = det.get("margem", 0.0)
            resultado["motivo_rejeicao"] = det.get("motivo_rejeicao", "")
            equipe_ml = det.get("equipe", "")
            if self._equipe_atribuivel(equipe_ml):
                resultado["equipe"] = equipe_ml
                resultado["metodo"] = "ML"
                return resultado

        fallback = self.definirAtribuicaoFallbackCategoria(categoria)
        if self._equipe_atribuivel(fallback):
            resultado["equipe"] = fallback
            resultado["metodo"] = "FALLBACK_CATEGORIA"
            return resultado

        resultado["equipe"] = self.EQUIPE_FALLBACK
        resultado["metodo"] = "FALLBACK_N1"
        return resultado

    def definirAtribuicaoDiretaDetalhada(
        self, titulo: str, categoria: str, descricao: str = ""
    ):
        """
        Retorna (equipe, tecnico_fixo) pela primeira palavra-chave encontrada em arqaux.
        tecnico_fixo pode ser "" se a regra não pinou pessoa.
        """
        try:
            descricao_limpa = self._limpar_descricao_html(descricao)
            for equipe, keywords, tecnico in self._carregar_regras_arqaux():
                for palavra_chave in keywords:
                    if not palavra_chave:
                        continue
                    if (
                        self._palavra_inteira_no_texto(palavra_chave, titulo)
                        or self._palavra_inteira_no_texto(palavra_chave, categoria)
                        or self._palavra_inteira_no_texto(palavra_chave, descricao_limpa)
                    ):
                        return equipe, (tecnico or "")
            return "", ""
        except Exception as e:
            print(f"--- [definirAtribuicaoDiretaDetalhada] ERRO: {e}")
            return "", ""

    def definirAtribuicaoDireta(self, id: int, titulo: str, categoria: str, descricao: str = "") -> str:
        """Compatível com código legado — só a equipe."""
        equipe, _tec = self.definirAtribuicaoDiretaDetalhada(titulo, categoria, descricao)
        return equipe
