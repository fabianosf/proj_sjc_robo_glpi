# Arquivo: ClTelegram.py (VERSÃO COMPLETA E CORRIGIDA)

import requests
import datetime
from urllib.parse import quote_plus
from DAL import DAL

class ClTelegram:
    def __init__(self, token_robo: str, db_config_file: str):
        if not token_robo or not db_config_file:
            raise ValueError("O token do robô e o arquivo de configuração do DB são obrigatórios.")
        
        self.TOKEN_ROBO = token_robo
        self.dal = DAL(app_name="TelegramBot", nome_arquivo_config=db_config_file)

    def pesquisa_token_tecnico(self, ref_tec: str) -> str:
        """
        Pesquisa e retorna o token (chat_id) de um usuário no banco de dados
        de forma robusta, padronizando o nome antes da busca.
        """
        try:
            #print(f"\n--- [DEPURAÇÃO DB] Iniciando busca de token...")
            #print(f"--- [DEPURAÇÃO DB] Parâmetro de busca recebido (bruto): '{ref_tec}' (Comprimento: {len(ref_tec)})")

            param_limpo = ref_tec.strip()
            #print(f"--- [DEPURAÇÃO DB] Parâmetro após .strip(): '{param_limpo}'")

            # Padroniza o nome trocando espaço por ponto
            param_padronizado = param_limpo.replace(' ', '.')
            #print(f"--- [DEPURAÇÃO DB] Parâmetro padronizado para busca (.replace(' ', '.')): '{param_padronizado}'")

            # Agora a busca usa o nome padronizado
            sql_query = "SELECT token FROM Tb_Atrib WHERE UPPER(TRIM(Usuario)) = %s"
            params = (param_padronizado.upper(),)
            
            #print(f"--- [DEPURAÇÃO DB] Executando SQL: {sql_query} com parâmetro: {params}")

            resultado_df = self.dal.read(sql_query, params)

            if not resultado_df.empty:
                chat_id = resultado_df['token'].iloc[0]
                #print(f"--- [SUCESSO DB] Token encontrado no banco de dados: '{chat_id}'")
                return str(chat_id) if chat_id else ""
            else:
                #print(f"--- [FALHA DB] Nenhum token encontrado para o usuário correspondente a '{param_padronizado.upper()}' na tabela 'Tb_Atrib'.")
                #print("--- [DICA] Verifique se o valor acima corresponde EXATAMENTE ao que está na coluna 'Usuario' do banco de dados.")
                return ""
        except Exception as e:
            print(f"--- [ERRO DB] Ocorreu uma exceção grave em 'pesquisa_token_tecnico': {e}")
            return ""

    def _gerar_mensagem_saudacao(self, nome_usuario: str) -> str:
        hora_atual = datetime.datetime.now().hour
        try:
            nome_formatado = nome_usuario.replace('.', ' ').split()[0].capitalize()
        except IndexError:
            nome_formatado = "Olá"

        if 5 <= hora_atual < 12:
            return f"Bom dia, {nome_formatado}!\n"
        elif 12 <= hora_atual < 18:
            return f"Boa tarde, {nome_formatado}!\n"
        else:
            return f"Boa noite, {nome_formatado}!\n"

    def enviar_mensagem_telegram(self, tec: str, cha: str) -> bool:
        """
        Envia a notificação de atribuição para o TÉCNICO.
        """
        #print(f"\n[INFO TELEGRAM] Tentando enviar notificação para o TÉCNICO: '{tec}' sobre o chamado '{cha}'")
        try:
            chat_id_destinatario = self.pesquisa_token_tecnico(tec)
            if not chat_id_destinatario:
                print(f"[FALHA TELEGRAM] Não foi possível enviar a mensagem porque o token para '{tec}' não foi encontrado.")
                return False
            
            saudacao = self._gerar_mensagem_saudacao(tec)
            mensagem_texto = f"{saudacao}O GLPI lhe atribuiu o seguinte chamado: \n\nNúmero: {cha}"
            mensagem_formatada = quote_plus(mensagem_texto)
            url = f"https://api.telegram.org/bot{self.TOKEN_ROBO}/sendMessage?chat_id={chat_id_destinatario}&text={mensagem_formatada}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                #print(f"[SUCESSO TELEGRAM] Mensagem para o técnico '{tec}' enviada com sucesso.")
                pass
            else:
                 #print(f"[ERRO TELEGRAM] API do Telegram retornou erro para o técnico '{tec}'. Status: {response.status_code}, Resposta: {response.text}")
                 pass
            return response.status_code == 200
        except Exception as e:
            #print(f"Ocorreu um erro em 'enviar_mensagem_telegram': {e}")
            return False

    def enviar_mensagem_telegram_solicitante(self, solicitante: str, cha: str) -> bool:
        """
        Envia a notificação de atualização para o SOLICITANTE, com depuração detalhada.
        """
        #print(f"\n[DEBUG TELEGRAM] ==================== INÍCIO DO ENVIO PARA SOLICITANTE ====================")
        #print(f"[DEBUG TELEGRAM] Tentando notificar o solicitante: '{solicitante}'")
        #print(f"[DEBUG TELEGRAM] Referente ao chamado ID: '{cha}'")

        try:
            if not solicitante or not solicitante.strip():
                #print(f"[FALHA TELEGRAM] O nome do solicitante está VAZIO ou NULO. Impossível continuar.")
                return False

            chat_id_destinatario = self.pesquisa_token_tecnico(solicitante)
            
            #print(f"[DEBUG TELEGRAM] Resultado da busca pelo token para '{solicitante}': '{chat_id_destinatario}'")

            if not chat_id_destinatario:
                #print(f"[FALHA TELEGRAM] A busca no banco de dados não retornou um chat_id (token). Verifique os logs de '[DEPURAÇÃO DB]' acima para entender o porquê.")
                #print(f"[DEBUG TELEGRAM] ===================== FIM DO ENVIO PARA SOLICITANTE (FALHA) =====================")
                return False

            #print(f"[DEBUG TELEGRAM] Token (chat_id) encontrado: '{chat_id_destinatario}'. Construindo a mensagem...")

            saudacao = self._gerar_mensagem_saudacao(solicitante)
            mensagem_texto = f"{saudacao}Houve uma alteração no chamado que você abriu. Peço que verifique a situação no GLPI: \n\nChamado: {cha}"
            mensagem_formatada = quote_plus(mensagem_texto)
            
            url = f"https://api.telegram.org/bot{self.TOKEN_ROBO}/sendMessage?chat_id={chat_id_destinatario}&text={mensagem_formatada}"
            
            #print(f"[DEBUG TELEGRAM] URL da API que será chamada: {url}")
            #print("[DEBUG TELEGRAM] Realizando a chamada para a API do Telegram...")
            response = requests.get(url, timeout=10)
            
            #print(f"[DEBUG TELEGRAM] Resposta recebida da API do Telegram:")
            #print(f"    -> Status Code: {response.status_code}")
            #print(f"    -> Conteúdo (Response Text): {response.text}")

            if response.status_code == 200:
                #print(f"[SUCESSO TELEGRAM] Mensagem para o solicitante '{solicitante}' enviada com sucesso.")
                #print(f"[DEBUG TELEGRAM] =================== FIM DO ENVIO PARA SOLICITANTE (SUCESSO) ===================")
                return True
            else:
                #print(f"[ERRO TELEGRAM] A API do Telegram retornou um erro. Analise o 'Status Code' e o 'Conteúdo' acima.")
                #print(f"[DEBUG TELEGRAM] ===================== FIM DO ENVIO PARA SOLICITANTE (FALHA) =====================")
                return False
                
        except Exception as e:
            #print(f"--- [ERRO GERAL TELEGRAM] Ocorreu uma exceção inesperada em 'enviar_mensagem_telegram_solicitante': {e}")
            #print(f"[DEBUG TELEGRAM] ===================== FIM DO ENVIO PARA SOLICITANTE (ERRO) ======================")
            return False
        
    def enviar_mensagem_Expiracao(self, tec: str, cha: str) -> bool:
        """
        Envia a notificação de atribuição para o TÉCNICO.
        """
        #print(f"\n[INFO TELEGRAM] Tentando enviar notificação para o TÉCNICO: '{tec}' sobre o chamado '{cha}'")
        try:
            chat_id_destinatario = self.pesquisa_token_tecnico(tec)
            if not chat_id_destinatario:
                print(f"[FALHA TELEGRAM] Não foi possível enviar a mensagem porque o token para '{tec}' não foi encontrado.")
                return False
            
            saudacao = self._gerar_mensagem_saudacao(tec)
            mensagem_texto = f"{saudacao}O chamado que lhe foi atribuido,deverá expirar nos próximos minutos (15 minutos) chamado: \n\nNúmero: {cha}"
            mensagem_formatada = quote_plus(mensagem_texto)
            url = f"https://api.telegram.org/bot{self.TOKEN_ROBO}/sendMessage?chat_id={chat_id_destinatario}&text={mensagem_formatada}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                #print(f"[SUCESSO TELEGRAM] Mensagem para o técnico '{tec}' enviada com sucesso.")
                pass
            else:
                 #print(f"[ERRO TELEGRAM] API do Telegram retornou erro para o técnico '{tec}'. Status: {response.status_code}, Resposta: {response.text}")
                 pass
            return response.status_code == 200
        except Exception as e:
            print(f"Ocorreu um erro em 'enviar_mensagem_telegram': {e}")
            return False