# Arquivo: listar_chamados.py
# Diagnóstico GLPI — credenciais somente via conf/glpi.dat (ClTrade).

import sys
from trade import ClTrade


def executar_listagem():
    """
    Script de diagnóstico que se conecta ao GLPI e lista os chamados mais recentes
    para verificar se a comunicação com a API está funcionando corretamente.
    """
    print("=" * 60)
    print("INICIANDO SCRIPT DE DIAGNÓSTICO: LISTAGEM DE CHAMADOS GLPI")
    print("=" * 60)

    try:
        print("\n[PASSO 1] Tentando conectar ao GLPI via conf/glpi.dat...")
        trade = ClTrade()
        print("[SUCESSO] Conexão com o GLPI estabelecida.")

        print("\n[PASSO 2] Buscando chamados recentes via API...")
        chamados_encontrados = trade.listarChamadosRecentes(limit=50)

        print("\n[PASSO 3] Exibindo resultados...")
        if chamados_encontrados is None:
            print(
                "\n[RESULTADO] FALHA. Ocorreu um erro durante a busca. "
                "Verifique as mensagens acima."
            )
        elif not chamados_encontrados:
            print(
                "\n[RESULTADO] NENHUM chamado foi encontrado no GLPI "
                "com o usuário da API."
            )
        else:
            print(
                f"\n[RESULTADO] SUCESSO! {len(chamados_encontrados)} "
                "chamados encontrados. Listando abaixo:\n"
            )
            print(f"| {'ID DO CHAMADO'.ljust(15)} | {'STATUS'.ljust(28)} |")
            print(f"| {'-' * 15} | {'-' * 28} |")
            for chamado in chamados_encontrados:
                id_str = str(chamado["id"]).ljust(15)
                status_str = (
                    f"{chamado['status_nome']} (ID: {chamado['status_id']})"
                ).ljust(28)
                print(f"| {id_str} | {status_str} |")

        print("\n" + "=" * 60)
        print("FIM DO SCRIPT DE DIAGNÓSTICO")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERRO FATAL] Não foi possível conectar ao GLPI: {e}")
        print(
            "[DICA] Verifique conf/glpi.dat e chave.key "
            "(não use credenciais no código-fonte)."
        )
        sys.exit(1)


if __name__ == "__main__":
    executar_listagem()
