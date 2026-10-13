# LiberarChamadosGLPI.py — remove da base local chamados Novo elegíveis no GLPI
# para permitir reprocessamento pelo main.py

import sys

from DAL import DAL
from GLPI_API import DIAS_CHAMADOS_ABERTOS, carregar_config_glpi
from trade import ClTrade


def main():
    cfg = carregar_config_glpi()
    print("=" * 60)
    print("LIBERAR CHAMADOS PARA REPROCESSAMENTO")
    print("=" * 60)
    print(f"GLPI      : {cfg['api_url']}")
    print(f"Janela    : últimos {DIAS_CHAMADOS_ABERTOS} dias | status Novo (1)")
    print()

    trade = ClTrade()
    df = trade.pesquisarChamadosSituacao(1)
    if df is None:
        print("[ERRO] Falha ao consultar GLPI.")
        sys.exit(1)
    if df.empty:
        print("Nenhum chamado Novo elegível no GLPI.")
        return

    ids_glpi = [int(x) for x in df["ID"].tolist()]
    print(f"Chamados elegíveis no GLPI ({len(ids_glpi)}):")
    for ticket_id in ids_glpi:
        tit = str(df.loc[df["ID"] == ticket_id, "Titulo"].iloc[0])[:70]
        print(f"  {ticket_id} — {tit}")
    print()

    dal = DAL(app_name="LiberarChamados", nome_arquivo_config="sgc.dat")
    placeholders = ",".join(["%s"] * len(ids_glpi))

    def _count(tabela, coluna):
        sql = f"SELECT COUNT(*) AS cnt FROM {tabela} WHERE {coluna} IN ({placeholders})"
        r = dal.read(sql, tuple(ids_glpi))
        return int(r.iloc[0]["cnt"]) if r is not None and not r.empty else 0

    antes = {
        "Tb_Ticket_new": _count("Tb_Ticket_new", "Id"),
        "Tb_ML_Log": _count("Tb_ML_Log", "Id_Glpi"),
        "Tb_Correcao_Feedback": _count("Tb_Correcao_Feedback", "Id_Glpi"),
    }
    print("Registros existentes na base local (antes):")
    for tabela, cnt in antes.items():
        print(f"  {tabela}: {cnt}")

    if sum(antes.values()) == 0:
        print("\nNenhum registro local para remover. Chamados já podem ser processados.")
        return

    print("\nRemovendo registros...")
    dal.delete(f"DELETE FROM Tb_ML_Log WHERE Id_Glpi IN ({placeholders})", tuple(ids_glpi))
    dal.delete(
        f"DELETE FROM Tb_Correcao_Feedback WHERE Id_Glpi IN ({placeholders})",
        tuple(ids_glpi),
    )
    dal.delete(f"DELETE FROM Tb_Ticket_new WHERE Id IN ({placeholders})", tuple(ids_glpi))

    depois = {
        "Tb_Ticket_new": _count("Tb_Ticket_new", "Id"),
        "Tb_ML_Log": _count("Tb_ML_Log", "Id_Glpi"),
        "Tb_Correcao_Feedback": _count("Tb_Correcao_Feedback", "Id_Glpi"),
    }
    print("\nRegistros restantes (depois):")
    for tabela, cnt in depois.items():
        print(f"  {tabela}: {cnt}")

    print("\n[OK] Chamados liberados para reprocessamento:")
    print(", ".join(str(i) for i in ids_glpi))
    print("=" * 60)


if __name__ == "__main__":
    main()
