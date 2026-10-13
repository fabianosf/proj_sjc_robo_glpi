# main.py (Versão Completa com Correção de Concorrência de Threads e Ordem de Atribuição)

from datetime import datetime
import time
import warnings
import pandas as pd
from trade import ClTrade
import ML
from MetodosGenericos import ClMetodosGenericos
import threading
from logger import ClLog
import sys
import os
from DbMigracao import ClDbMigracao
from MLLog import ClMLLog
from AgendadorSGC import AgendadorSGC

warnings.filterwarnings("ignore", message=".*urllib3.*chardet.*")
warnings.filterwarnings("ignore", module="requests")

class Main:
    AGENDADOR_AUTO = os.getenv("SGC_AGENDADOR_AUTO", "1").lower() in ("1", "true", "yes")
    INTERVALO_VARREDURA_SEG = int(os.getenv("SGC_INTERVALO_VARREDURA", "30"))
    HEARTBEAT_MONITOR_SEG = int(os.getenv("SGC_MONITOR_HEARTBEAT", "60"))
    INTERVALO_VERIFICA_USUARIOS_SEG = 15 * 60

    def __init__(self):
        self.running = True
        self.trade = None
        self.M = None
        self._model_lock = threading.Lock()
        self._model_mtime = 0.0
        self._agendador = None
        self._ultimo_heartbeat_monitor = 0.0
        self._ultima_verifica_usuarios = 0.0

    def Verifica_Usuarios_Atribuidos(self, met: ClMetodosGenericos) -> None:
        """
        Sincroniza o técnico de Tb_Ticket_new com o técnico atribuído no GLPI
        (somente chamados com status Atribuído).
        """
        logger = ClLog()
        try:
            df_glpi = self.trade.pesquisarChamadosSituacao(2)
            if df_glpi is None:
                print("[VERIFICA_ATRIB] AVISO: Falha ao consultar chamados atribuídos no GLPI.")
                return
            if df_glpi.empty:
                return

            lista = []
            for _, row in df_glpi.iterrows():
                id_chamado = int(row["ID"])
                # Login do técnico ATRIBUÍDO no GLPI (não o solicitante)
                tecnico_glpi = (self.trade.pesquisarTecnicoDoChamado(id_chamado) or "").strip()
                # Nome de exibição do mesmo técnico atribuído
                nome_usuario = str(row.get("Usuario") or tecnico_glpi or "N/A").strip()
                if not tecnico_glpi:
                    continue
                lista.append(
                    {
                        "chamado": id_chamado,
                        "tecnico": tecnico_glpi,
                        "nome_usuario": nome_usuario,
                        "titulo": str(row.get("Titulo") or ""),
                        "categoria": str(row.get("Categoria") or ""),
                        "descricao": str(row.get("Descricao") or ""),
                        "solicitante": str(row.get("Solicitante") or "N/A"),
                        "data": row.get("Data"),
                        "datsol": row.get("Datsol"),
                    }
                )

            if not lista:
                return

            atualizados = 0
            backfills = 0
            for item in lista:
                id_chamado = item["chamado"]
                tecnico_glpi = item["tecnico"]
                df_db = met.dal_sgc.read(
                    "SELECT Id, Tecnico FROM Tb_Ticket_new WHERE Id = %s",
                    (id_chamado,),
                )
                if df_db is None:
                    # Erro de DB — não inventar INSERT
                    continue
                if df_db.empty:
                    ok_ins = met.registrar_chamado_novo(
                        id_chamado,
                        item["titulo"] or f"CHAMADO {id_chamado}",
                        item["categoria"] or "",
                        item["descricao"] or "",
                        item["data"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        tecnico_glpi,
                        item["solicitante"] or "N/A",
                        item["datsol"] or item["data"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "",
                    )
                    if ok_ins:
                        backfills += 1
                        met.incrementarCargaTecnico(tecnico_glpi)
                        logger.registrarActionLog(
                            "MAIN",
                            "MONITOR",
                            f"VERIFICA_ATRIB | BACKFILL | CHAMADO {id_chamado} | "
                            f"TECNICO {tecnico_glpi} inserido em Tb_Ticket_new",
                        )
                        print(
                            f"[VERIFICA_ATRIB] Backfill: chamado {id_chamado} "
                            f"inserido com técnico '{tecnico_glpi}'."
                        )
                    continue

                tecnico_db = str(df_db.iloc[0]["Tecnico"] or "").strip()
                if tecnico_db.upper() == tecnico_glpi.upper():
                    continue

                ok = met.dal_sgc.update(
                    "UPDATE Tb_Ticket_new SET Tecnico = %s WHERE Id = %s",
                    (tecnico_glpi[:20], id_chamado),
                )
                if ok:
                    atualizados += 1
                    if tecnico_db:
                        met.decrementarCargaTecnico(tecnico_db)
                    met.incrementarCargaTecnico(tecnico_glpi)
                    logger.registrarActionLog(
                        "MAIN",
                        "MONITOR",
                        f"VERIFICA_ATRIB | CHAMADO {id_chamado} | "
                        f"TECNICO {tecnico_db} -> {tecnico_glpi} | USUARIO {item['nome_usuario']}",
                    )
                    print(
                        f"[VERIFICA_ATRIB] Chamado {id_chamado}: "
                        f"técnico '{tecnico_db}' substituído por '{tecnico_glpi}'."
                    )

            if atualizados or backfills:
                print(
                    f"[VERIFICA_ATRIB] {atualizados} sincronizado(s), "
                    f"{backfills} backfill(s) com o GLPI."
                )
            try:
                from SchedulerHeartbeat import note_job

                note_job(
                    "verifica_atribuicoes",
                    True,
                    f"{atualizados} sync, {backfills} backfill",
                )
            except Exception:
                pass
        except Exception as e:
            logger.registarExceptionLog(
                "MAIN", "EXCEPTION", "ERRO EM Verifica_Usuarios_Atribuidos", e
            )
            print(f"[VERIFICA_ATRIB] ERRO: {e}")
            try:
                from SchedulerHeartbeat import note_job

                note_job("verifica_atribuicoes", False, str(e)[:300])
            except Exception:
                pass

    def _iniciar_agendador_background(self, logger):
        if not self.AGENDADOR_AUTO:
            print("[INFO] AgendadorSGC desligado (SGC_AGENDADOR_AUTO=0).")
            return

        self._agendador = AgendadorSGC()

        def _executar():
            self._agendador.loop(silencioso=True)

        thread = threading.Thread(target=_executar, name="AgendadorSGC", daemon=True)
        thread.start()
        logger.registrarActionLog("MAIN", "AGENDADOR", "AGENDADOR SGC INICIADO EM BACKGROUND")
        print(
            f"[INFO] AgendadorSGC ativo em background "
            f"(re-treino {AgendadorSGC.RETRAIN_HOUR:02d}:00 | PDF {AgendadorSGC.REPORT_HOUR:02d}:00)."
        )

    def _recarregar_modelo_se_necessario(self, ml, logger):
        caminho = ML.MODELO_ATIVO
        if not caminho.exists():
            return
        mtime = caminho.stat().st_mtime
        if mtime <= self._model_mtime:
            return
        with self._model_lock:
            if mtime <= self._model_mtime:
                return
            self.M = ml.le_modelo_ml()
            self._model_mtime = mtime
            logger.registrarActionLog("MAIN", "ML", "MODELO ML RECARREGADO DO DISCO")
            print("[ML] Modelo recarregado (arquivo atualizado pelo AgendadorSGC).")

    def main_loop(self):
        logger = ClLog()
        #print("[INFO] Iniciando a aplicação SGC...")

        try:
            # GLPI via conf/glpi.dat (GLPI_API)
            self.trade = ClTrade()
            met = ClMetodosGenericos(self.trade)
            ml_log = ClMLLog()
            if not ClDbMigracao().aplicar_migracao_ambiente():
                print("[AVISO] Migração incompleta. Verifique logs e conf/sgc.dat.")
                logger.registrarActionLog("MAIN", "AVISO", "MIGRAÇÃO INCOMPLETA")

        except Exception as e:
            error_msg = f"ERRO FATAL ao inicializar a aplicação: {e}"
            print(error_msg)
            logger.registarExceptionLog("MAIN", "EXCEPTION", "ERRO NA INICIALIZAÇÃO", e)
            sys.exit()

        ml = ML.ClML()
        self.M = ml.le_modelo_ml()
        if ML.MODELO_ATIVO.exists():
            self._model_mtime = ML.MODELO_ATIVO.stat().st_mtime
        if self.M[0] is None:
            print("[ML] Modelo não encontrado ou incompatível. Treinando na inicialização...")
            logger.registrarActionLog("MAIN", "ATIVIDADE", "TREINAMENTO INICIAL DO MODELO ML")
            if ml.geracao_automatica_modelo(
                forcar_implantacao=True,
                trade=self.trade,
                sincronizar_feedback=True,
            ):
                self.M = ml.le_modelo_ml()
                if ML.MODELO_ATIVO.exists():
                    self._model_mtime = ML.MODELO_ATIVO.stat().st_mtime
                print("[ML] Modelo inicial treinado e carregado com sucesso.")
            else:
                print("[ML] AVISO: Não foi possível treinar o modelo na inicialização.")

        self._iniciar_agendador_background(logger)

        print("Iniciar Monitoramento...")
        logger.registrarActionLog("MAIN", "MONITOR", "MONITORAMENTO DE CHAMADOS INICIADO")

        while self.running:
            self._recarregar_modelo_se_necessario(ml, logger)

            with self._model_lock:
                M = self.M

            try:
                df_chamados = self.trade.pesquisarChamadosSituacao(1)
            except Exception as e:
                logger.registarExceptionLog("MAIN", "MONITOR", "FALHA AO CONSULTAR GLPI", e)
                print(f"[GLPI-FETCH] ERRO: {e}")
                df_chamados = None

            try:
                from WorkerHeartbeat import maybe_daily_qtdc_reset, write_heartbeat
                from SchedulerHeartbeat import note_job

                fetch_truncated = False
                if df_chamados is not None:
                    try:
                        fetch_truncated = bool(df_chamados.attrs.get("fetch_truncated"))
                    except Exception:
                        fetch_truncated = False
                write_heartbeat(
                    glpi_ok=df_chamados is not None,
                    novos_na_fila=0 if df_chamados is None else int(len(df_chamados)),
                    last_error="" if df_chamados is not None else "GLPI indisponível",
                    agendador_auto=bool(self.AGENDADOR_AUTO),
                    fetch_truncated=bool(fetch_truncated),
                )
                if maybe_daily_qtdc_reset(met.reset_qtdc_diario):
                    logger.registrarActionLog(
                        "MAIN", "MONITOR", "QtdC ZERADO (reset diário)"
                    )
                    print("[ASSIGN-LOGIC] QtdC zerado (reset diário).")
                n_novos = 0 if df_chamados is None else int(len(df_chamados))
                note_job(
                    "monitor_chamados",
                    df_chamados is not None,
                    "GLPI indisponível" if df_chamados is None else f"{n_novos} novos na fila",
                )
            except Exception:
                pass

            agora = time.time()
            if agora - self._ultimo_heartbeat_monitor >= self.HEARTBEAT_MONITOR_SEG:
                if df_chamados is None:
                    logger.registrarActionLog("MAIN", "MONITOR", "HEARTBEAT | GLPI INDISPONÍVEL")
                elif df_chamados.empty:
                    logger.registrarActionLog("MAIN", "MONITOR", "HEARTBEAT | NENHUM CHAMADO NOVO")
                else:
                    ids = ",".join(str(x) for x in df_chamados["ID"].tolist())
                    logger.registrarActionLog(
                        "MAIN",
                        "MONITOR",
                        f"HEARTBEAT | {len(df_chamados)} CHAMADO(S) NOVO(S): {ids}",
                    )
                self._ultimo_heartbeat_monitor = agora
            
            if df_chamados is not None and not df_chamados.empty:
                logger.registrarActionLog(
                    "MAIN",
                    "MONITOR",
                    f"DETECTADOS {len(df_chamados)} CHAMADO(S) NOVO(S)",
                )
                print(f"Detectado chamado:")
                
                for i, row in df_chamados.iterrows():
                    CodC = row['ID']
                    titulo = row['Titulo']
                    categoria = row['Categoria']
                    descricao = row['Descricao']
                    solicitante = row['Solicitante']
                    DatAt = row['Data']
                    DatSol = row['Datsol']
                    # NOVA LINHA: Extraindo a localização do DataFrame
                    localizacao = row['Localizacao']

                    #print(f"\n--- [PROCESSANDO CHAMADO ID: {CodC}] ---")
                    # LINHA MODIFICADA: Adicionada a impressão da localização
                    #print(f"[DATA] Título: {titulo} | Categoria: {categoria} | Solicitante: {solicitante} | Localização: {localizacao}")
                    
                    try:
                        if met.chamadoExiste(CodC):
                            logger.registrarActionLog(
                                "MAIN",
                                "MONITOR",
                                f"CHAMADO {CodC} JÁ EXISTE NA BASE — IGNORADO",
                            )
                            print(f"[DB-CHECK] AVISO: Chamado {CodC} já consta na base de dados. Ignorando.")
                            continue

                        # --- Atribuição híbrida Fase 3 ---
                        res = met.resolver_equipe_chamado(
                            ml, M, titulo, categoria, descricao, localizacao
                        )
                        equipe_prevista = res.get("equipe", "")
                        metodo = res.get("metodo", "")

                        if metodo == "DIRETO":
                            print(f"Método: Direto: '{equipe_prevista}'")
                        elif metodo == "ML":
                            print(f"Método: ML: '{equipe_prevista}' (confiança: {res.get('confianca', 0):.1f}%)")
                        elif metodo.startswith("FALLBACK"):
                            print(f"Método: {metodo}: '{equipe_prevista}'")
                        elif res.get("motivo_rejeicao"):
                            print(f"[ML] AVISO: {res.get('motivo_rejeicao')}")

                        candidatos = []
                        if equipe_prevista:
                            candidatos = met.listar_tecnicos_elegiveis_equipe(
                                equipe_prevista, titulo, localizacao, categoria=categoria
                            )

                            # Pin opcional da regra DIRETO (arqaux N8@pessoa-"PALAVRA")
                            tecnico_fixo = (res.get("tecnico_fixo") or "").strip()
                            if tecnico_fixo:
                                if tecnico_fixo in candidatos:
                                    candidatos = [tecnico_fixo] + [
                                        c for c in candidatos if c != tecnico_fixo
                                    ]
                                else:
                                    print(
                                        f"[ASSIGN-LOGIC] AVISO: Técnico fixo '{tecnico_fixo}' "
                                        f"não elegível na equipe '{equipe_prevista}'. "
                                        "Usando lista normal."
                                    )

                            if not candidatos:
                                from WorkerHeartbeat import note_skip, was_skipped_today

                                ja_skip = was_skipped_today(CodC)
                                if not ja_skip:
                                    ml_log.registrar(
                                        id_glpi=CodC,
                                        metodo=metodo or "SEM_EQUIPE",
                                        equipe_prevista=equipe_prevista,
                                        categoria=categoria,
                                        localizacao=localizacao,
                                        equipe_ml=res.get("equipe_ml_bruta", ""),
                                        equipe_2a=res.get("equipe_2a", ""),
                                        confianca=res.get("confianca", 0.0),
                                        margem=res.get("margem", 0.0),
                                        motivo_rejeicao=res.get("motivo_rejeicao", ""),
                                    )
                                    logger.registrarActionLog(
                                        "MAIN",
                                        "MONITOR",
                                        f"CHAMADO {CodC} SEM TÉCNICO ELEGÍVEL | "
                                        f"EQUIPE {equipe_prevista} — NÃO ATRIBUÍDO",
                                    )
                                    print(
                                        f"[ASSIGN-LOGIC] AVISO: Nenhum técnico elegível "
                                        f"(Sit=1 no horário) na equipe '{equipe_prevista}'. "
                                        f"Chamado {CodC} permanece Novo no GLPI."
                                    )
                                    note_skip(CodC)
                                continue

                        ml_log.registrar(
                            id_glpi=CodC,
                            metodo=metodo or "SEM_EQUIPE",
                            equipe_prevista=equipe_prevista,
                            categoria=categoria,
                            localizacao=localizacao,
                            equipe_ml=res.get("equipe_ml_bruta", ""),
                            equipe_2a=res.get("equipe_2a", ""),
                            confianca=res.get("confianca", 0.0),
                            margem=res.get("margem", 0.0),
                            motivo_rejeicao=res.get("motivo_rejeicao", ""),
                        )

                        if equipe_prevista:
                            tecnico_atribuir = ""
                            sucesso_api = None
                            falhas_glpi = []
                            for candidato in candidatos:
                                if not self.trade.tecnico_existe_glpi(candidato):
                                    print(
                                        f"[ASSIGN-LOGIC] AVISO: Técnico '{candidato}' não encontrado no GLPI. "
                                        "Tentando próximo da equipe..."
                                    )
                                    falhas_glpi.append(f"{candidato}(sem GLPI)")
                                    continue

                                print(f"Técnico:{candidato}")
                                sucesso_api = self.trade.atribuirChamadoTecnico(CodC, candidato)
                                if sucesso_api:
                                    tecnico_atribuir = candidato
                                    break

                                falhas_glpi.append(candidato)
                                print(
                                    f"[ASSIGN-LOGIC] AVISO: Falha ao atribuir para '{candidato}'. "
                                    "Tentando próximo da equipe..."
                                )

                            if sucesso_api:
                                logger.registrarActionLog(
                                    "MAIN",
                                    "MONITOR",
                                    f"CHAMADO {CodC} ATRIBUÍDO A {tecnico_atribuir} | EQUIPE {equipe_prevista}",
                                )
                                try:
                                    motivo_pessoa = met.montar_motivo_atribuicao_pessoa(
                                        equipe=equipe_prevista,
                                        metodo=metodo or "",
                                        escolhido=tecnico_atribuir,
                                        candidatos=candidatos,
                                        tecnico_fixo=(res.get("tecnico_fixo") or ""),
                                        falhas_glpi=falhas_glpi,
                                    )
                                    ml_log.atualizar_motivo_atrib(CodC, motivo_pessoa)
                                    print(f"[ASSIGN-LOGIC] Motivo pessoa: {motivo_pessoa}")
                                except Exception as e_mot:
                                    print(f"[ASSIGN-LOGIC] AVISO: falha ao gravar Motivo_Atrib: {e_mot}")
                                ok_db = met.registrar_chamado_novo(
                                    CodC, titulo, categoria, descricao, DatAt,
                                    tecnico_atribuir, solicitante, DatSol, equipe_prevista,
                                )
                                if not ok_db:
                                    time.sleep(0.4)
                                    ok_db = met.registrar_chamado_novo(
                                        CodC, titulo, categoria, descricao, DatAt,
                                        tecnico_atribuir, solicitante, DatSol, equipe_prevista,
                                    )
                                if not ok_db:
                                    logger.registrarActionLog(
                                        "MAIN",
                                        "ERRO",
                                        f"CHAMADO {CodC} ATRIBUÍDO NO GLPI MAS FALHA AO PERSISTIR "
                                        f"EM Tb_Ticket_new (técnico={tecnico_atribuir}) "
                                        "após retry",
                                    )
                                    print(
                                        f"[DB-ACTION] ERRO CRÍTICO: Chamado {CodC} atribuído no GLPI "
                                        f"a '{tecnico_atribuir}', mas INSERT local falhou (2 tentativas). "
                                        "Carga NÃO atualizada. "
                                        "Verifica_Usuarios tentará backfill."
                                    )
                                    try:
                                        from WorkerHeartbeat import note_orphan

                                        note_orphan(
                                            CodC,
                                            tecnico=tecnico_atribuir,
                                            equipe=equipe_prevista or "",
                                        )
                                    except Exception:
                                        pass
                                    continue

                                met.incrementarCargaTecnico(tecnico_atribuir)
                                try:
                                    from NotificacaoPainel import notify_ticket_assigned
                                    from WorkerHeartbeat import write_heartbeat

                                    notify_ticket_assigned(
                                        met.dal_sgc,
                                        tecnico=tecnico_atribuir,
                                        ticket_id=int(CodC),
                                        equipe=equipe_prevista or "",
                                    )
                                    write_heartbeat(last_assigned_id=int(CodC))
                                except Exception:
                                    pass
                            else:
                                logger.registrarActionLog(
                                    "MAIN",
                                    "MONITOR",
                                    f"FALHA ATRIBUIÇÃO CHAMADO {CodC} | EQUIPE {equipe_prevista}",
                                )
                                print(
                                    f"[API-ACTION] ERRO: Não foi possível atribuir o chamado {CodC} "
                                    f"para nenhum técnico da equipe '{equipe_prevista}'."
                                )

                    except Exception as e:
                        print(f"[ERRO GERAL] Ocorreu um erro inesperado ao processar o chamado {CodC}: {e}")
            
            elif df_chamados is None:
                logger.registrarActionLog(
                    "MAIN",
                    "MONITOR",
                    "GLPI RETORNOU NONE — VERIFIQUE CONEXÃO/AUTENTICAÇÃO",
                )
                print("[GLPI-FETCH] ERRO: A chamada à API do GLPI retornou 'None'. Verifique a conexão e os logs da classe ClTrade para possíveis erros de autenticação ou de rede.")
            
            else: # df_chamados.empty
                pass#print(f"[{datetime.now().strftime('%H:%M:%S')}] [GLPI-FETCH] Nenhum chamado com status 'Novo' (ID 1) foi encontrado no GLPI.")

            agora_verifica = time.time()
            if agora_verifica - self._ultima_verifica_usuarios >= self.INTERVALO_VERIFICA_USUARIOS_SEG:
                self.Verifica_Usuarios_Atribuidos(met)
                self._ultima_verifica_usuarios = agora_verifica
            
            #print(f"[{datetime.now().strftime('%H:%M:%S')}] [CYCLE END] Aguardando {self.INTERVALO_VARREDURA_SEG} segundos para o próximo ciclo...")
            time.sleep(self.INTERVALO_VARREDURA_SEG)

if __name__ == "__main__":
    app = Main()
    try:
        app.main_loop()
    except KeyboardInterrupt:
        print("\n[INFO] Aplicação interrompida pelo usuário. Encerrando...")
        app.running = False
        if app._agendador:
            app._agendador.running = False
        sys.exit(0)