# VerificarFase2Local.py — diagnóstico rápido do ambiente local (Fase 2)

import os
import sys

from DbMigracao import ClDbMigracao
from DAL import DAL
from ML import ClML, MODEL_VERSION, MODELO_ATIVO
from paths import CONF_DIR


def _ok(msg):
    print(f"  [OK] {msg}")


def _aviso(msg):
    print(f"  [AVISO] {msg}")


def _erro(msg):
    print(f"  [ERRO] {msg}")


def main():
    print("=" * 60)
    print("VERIFICAÇÃO LOCAL — FASE 2 SGC")
    print("=" * 60)
    erros = 0

    print("\n1. Dependências Python")
    try:
        import mysql.connector  # noqa: F401
        _ok("mysql-connector-python")
    except ImportError:
        _erro("mysql-connector-python ausente — pip install -r requirements.txt")
        erros += 1

    try:
        import reportlab  # noqa: F401
        _ok("reportlab (PDF assertividade)")
    except ImportError:
        _erro("reportlab ausente — pip install reportlab")
        erros += 1

    try:
        import requests  # noqa: F401
        _ok("requests (GLPI)")
    except ImportError:
        _erro("requests ausente — pip install requests")
        erros += 1

    print("\n2. Configuração local")
    conf = CONF_DIR / "sgc.dat"
    chave = CONF_DIR / "chave.key"
    if conf.exists():
        _ok(f"config: {conf}")
    else:
        _erro(f"arquivo não encontrado: {conf}")
        erros += 1
    if chave.exists():
        _ok(f"chave: {chave}")
    else:
        _erro(f"arquivo não encontrado: {chave}")
        erros += 1

    print("\n3. Banco de dados / schema Fase 2")
    try:
        mig = ClDbMigracao()
        if mig.aplicar_migracao_ambiente():
            _ok("migração ambiente aplicada (Fase 3; Fase 2 se SGC_MIGRACAO_COMPLETA=1)")
            if mig.ultimo_backfill_equipe:
                _ok(f"backfill Equipe: {mig.ultimo_backfill_equipe} registro(s)")
        else:
            _erro("migração Fase 2 falhou")
            erros += 1

        dal = DAL(app_name="Verificacao", nome_arquivo_config="sgc.dat")
        for tabela, coluna in (
            ("Tb_Ticket_new", "Equipe"),
            ("Tb_Ticket_Feedback_Temp", "Localizacao"),
            ("Tb_ML_Log", "Metodo"),
            ("Tb_Correcao_Feedback", "Equipe_Correta"),
        ):
            df = dal.read(f"SHOW COLUMNS FROM {tabela} LIKE %s", (coluna,))
            if df is not None and not df.empty:
                _ok(f"{tabela}.{coluna}")
            else:
                _erro(f"coluna ausente: {tabela}.{coluna}")
                erros += 1

        fb = dal.read("SELECT COUNT(*) AS cnt FROM Tb_Ticket_Feedback_Temp")
        total_fb = int(fb.iloc[0]["cnt"]) if fb is not None and not fb.empty else 0
        if total_fb > 0:
            _ok(f"feedback GLPI: {total_fb} registro(s)")
        else:
            _aviso("feedback GLPI vazio — execute SincronizarFeedbackGLPI.py")

        tn = dal.read(
            "SELECT COUNT(*) AS cnt FROM Tb_Ticket_new "
            "WHERE Equipe IS NOT NULL AND TRIM(Equipe) <> ''"
        )
        total_eq = int(tn.iloc[0]["cnt"]) if tn is not None and not tn.empty else 0
        if total_eq > 0:
            _ok(f"Tb_Ticket_new com Equipe: {total_eq} registro(s)")
        else:
            _aviso("nenhum chamado com Equipe — normal antes de novas atribuições")

        perf = dal.read("SHOW TABLES LIKE 'tb_performance'")
        if perf is not None and not perf.empty:
            _ok("tb_performance")
        else:
            _erro("tabela ausente: tb_performance")
            erros += 1
    except Exception as e:
        _erro(f"conexão/migração: {e}")
        erros += 1

    print("\n4. Modelo ML")
    if MODELO_ATIVO.exists():
        clml = ClML()
        modelo = clml.le_modelo_ml()
        if modelo[0] is not None:
            versao = modelo[3].get("version")
            f1 = modelo[3].get("f1_macro")
            _ok(f"ModeloML.pkl v{versao} (F1-macro: {f1})")
            if versao != MODEL_VERSION:
                _erro(f"modelo v{versao} incompatível — esperado v{MODEL_VERSION}")
                erros += 1
        else:
            _erro("ModeloML.pkl presente mas incompatível — execute TreinarModeloNovo.py")
            erros += 1
    else:
        _aviso(f"modelo ausente ({MODELO_ATIVO}) — execute PrepararFase2Local.py ou TreinarModeloNovo.py")

    print("\n5. Relatório PDF")
    try:
        from RelatorioAssertividade import ClRelatorioAssertividade
        _ok("RelatorioAssertividade importável")
        _aviso("geração manual: sgc_python.bat python\\GerarRelatorioAssertividade.py")
    except Exception as e:
        _erro(f"RelatorioAssertividade: {e}")
        erros += 1

    print("\n" + "=" * 60)
    if erros:
        print(f"Resultado: {erros} problema(s) encontrado(s).")
        sys.exit(1)
    print("Resultado: ambiente local OK para Fase 2 (avisos podem ser normais em primeiro deploy).")
    print("=" * 60)


if __name__ == "__main__":
    main()
