# teste_conexao.py

from DAL import DAL
import pandas as pd

print("--- INICIANDO TESTE DE CONEXÃO E CONSULTA DIRETA ---")

try:
    # 1. Tenta inicializar o DAL, exatamente como a sua aplicação faz.
    print("\n[PASSO 1] Inicializando a classe DAL para 'sgc.dat'...")
    dal_sgc = DAL(app_name="TESTE_DIRETO_SGC", nome_arquivo_config="sgc.dat")
    print(">>> SUCESSO: Classe DAL inicializada.")

    # 2. Tenta fazer a consulta mais básica possível para ver se a tabela é acessível.
    print("\n[PASSO 2] Executando consulta básica: SELECT COUNT(*) FROM Tb_Atrib")
    try:
        df_count = dal_sgc.read("SELECT COUNT(*) FROM Tb_Atrib")
        if not df_count.empty:
            print(f">>> SUCESSO: A tabela Tb_Atrib é acessível e contém {df_count.iloc[0,0]} linhas.")
        else:
            print(">>> FALHA CRÍTICA: Não foi possível contar as linhas da tabela. Verifique o nome da tabela e as permissões do usuário.")

    except Exception as e:
        print(f">>> FALHA CRÍTICA no PASSO 2: {e}")


    # 3. Tenta fazer a consulta EXATA que está falhando na sua aplicação.
    equipe_teste = 'N1'
    sql_query = f"SELECT * FROM Tb_Atrib WHERE TRIM(Equipe) = '{equipe_teste}' AND Sit = 1"
    
    print(f"\n[PASSO 3] Executando a consulta problemática: {sql_query}")
    try:
        df_problema = dal_sgc.read(sql_query)

        # 4. Analisa o resultado
        print("\n[PASSO 4] Análise do resultado:")
        if not df_problema.empty:
            print(">>> SUCESSO INESPERADO! A consulta retornou os seguintes dados:")
            print(df_problema.to_string())
        else:
            print(">>> FALHA CONFIRMADA: A consulta executada pelo DAL não retornou nenhum dado.")
            print("Isso confirma que o problema está na comunicação DAL/JDBC/Oracle ou na configuração da conexão.")

    except Exception as e:
        print(f">>> FALHA CRÍTICA no PASSO 3: {e}")


except Exception as e:
    print(f"\nFALHA GERAL AO INICIALIZAR OU EXECUTAR O TESTE: {e}")

print("\n--- TESTE CONCLUÍDO ---")