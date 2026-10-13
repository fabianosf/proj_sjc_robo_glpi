# Proj SGC (ROBO)

Robô de **atribuição automática de chamados** integrado ao **GLPI**. Monitora tickets novos, classifica a equipe responsável (regras + Machine Learning), escolhe um técnico elegível, atribui no GLPI, registra na base local e notifica via **Telegram**.

---

## O que o projeto faz

Em resumo, o SGC automatiza o fluxo operacional de triagem:

1. **Consulta o GLPI** em loop (padrão: a cada 30 segundos) em busca de chamados com status **Novo**.
2. **Define a equipe** com um pipeline híbrido (regras em `arqaux.txt` → ML → fallbacks).
3. **Seleciona um técnico** da equipe (carga, elegibilidade, existência no GLPI).
4. **Atribui o chamado** no GLPI via API REST.
5. **Grava o ticket** na base local (`Tb_Ticket_new`) e incrementa a carga do técnico.
6. **Notifica** técnico e solicitante pelo Telegram.
7. **Aprende continuamente**: importa chamados fechados, detecta correções de equipe, re-treina o modelo e gera relatórios de assertividade.

Também sincroniza periodicamente o técnico atribuído no GLPI com o registro local (chamados já atribuídos).

---

## Fluxo principal (monitoramento)

```
GLPI (status Novo)
        │
        ▼
   main.py (loop)
        │
        ├─ Já existe em Tb_Ticket_new? → ignora
        │
        ├─ resolver_equipe_chamado()
        │     1. DIRETO          (palavras-chave exatas em arqaux.txt)
        │     2. FALLBACK_PARCIAL (match parcial)
        │     3. ML               (ComplementNB + TF-IDF, com limiares)
        │     4. FALLBACK_CATEGORIA
        │     5. FALLBACK_N1      (equipe padrão)
        │
        ├─ Lista técnicos elegíveis da equipe
        ├─ Atribui no GLPI (primeiro candidato válido)
        ├─ Persiste + incrementa carga
        └─ Telegram (técnico + solicitante)
```

Em paralelo (thread em background), o **AgendadorSGC** executa tarefas diárias/semanais de aprendizado e relatórios.

---

## Arquitetura

| Camada | Responsabilidade |
|--------|------------------|
| `main.py` (raiz) | Bootstrap: garante `venv` e executa `python/main.py` |
| `python/main.py` | Loop de monitoramento e orquestração |
| `trade.py` / `GLPI_API.py` | Integração com a API REST do GLPI |
| `MetodosGenericos.py` | Regras de equipe, técnicos, carga e persistência |
| `ML.py` | Treino, inferência, limiares e implantação do modelo |
| `DAL.py` | Acesso a dados (MariaDB; Oracle opcional) |
| `CONFIGURACAO.py` | Lê `conf/*.dat` criptografados (Fernet + `chave.key`) |
| `telegram.py` | Notificações Telegram |
| `AgendadorSGC.py` / `TarefasML.py` | Re-treino, correções e PDFs agendados |
| `logger.py` | Logs diários em `log/` |

### Modelo de ML

- Algoritmo: **Complement Naive Bayes** + **TF-IDF** (scikit-learn).
- Entrada: localização + categoria + título + descrição (texto normalizado).
- Artefatos em `Modelo/` (`ModeloML.pkl`, backup e candidato).
- Re-treino diário com feedback de chamados **fechados** do GLPI; só implantado se passar critérios de qualidade (F1, etc.).
- Versionamento e rollback via `ModelVersionamento.py` / `RestaurarModeloML.py`.

### Regras diretas (`arqaux.txt`)

Arquivo de palavras-chave por equipe (N1, N2, N3, …). Tem **prioridade** sobre o ML: se um termo da lista for encontrado, a equipe é definida sem consultar o modelo.

---

## Estrutura do repositório

```
Proj_SGC(ROBO)/
├── main.py                 # Entrada (usa venv automaticamente)
├── run.bat / run.sh        # Inicia o monitoramento
├── setup_env.bat / .sh     # Cria venv e instala dependências
├── sgc_python.bat / .sh    # Executa scripts Python com o venv
├── requirements.txt
├── arqaux.txt              # Regras de classificação por palavras-chave
├── proj_sgc.service        # Unit systemd (Linux)
├── conf/                   # Configurações criptografadas (.dat + chave.key)
├── python/                 # Código da aplicação
├── sql/                    # Scripts de tabelas (Fase 2/3)
├── Modelo/                 # Modelo ML ativo e versões
├── log/                    # Logs por dia
├── relatorios/             # PDFs e relatórios gerados
└── drivers/                # Drivers Oracle (se necessário)
```

---

## Pré-requisitos

- **Python 3.10+**
- Acesso à **API do GLPI** (URL, tokens/credenciais)
- Banco **MariaDB** (ou Oracle, se configurado) com a base do SGC
- Arquivos em `conf/`:
  - `chave.key` — chave Fernet
  - `sgc.dat` — conexão com o banco
  - `glpi.dat` — conexão com o GLPI
- Token do bot Telegram (**opcional** — se ausente, o robô atribui sem notificar)

---

## Instalação

### Windows

```bat
setup_env.bat
```

### Linux

```bash
chmod +x setup_env.sh run.sh sgc_python.sh
./setup_env.sh
```

Isso cria o `venv/` e instala as dependências de `requirements.txt`.

---

## Como executar

### Monitoramento (processo principal)

```bat
run.bat
```

ou:

```bash
./run.sh
```

ou ainda:

```bash
python main.py
```

O processo fica em loop até `Ctrl+C`.

### Serviço systemd (Linux)

Exemplo em `proj_sgc.service` — ajuste caminhos/usuário e habilite:

```bash
sudo systemctl enable proj_sgc
sudo systemctl start proj_sgc
```

### Scripts utilitários (com o venv)

```bat
sgc_python.bat python\VerificarFase2Local.py
sgc_python.bat python\SincronizarFeedbackGLPI.py
sgc_python.bat python\ExecutarRetreinoDiario.py
sgc_python.bat python\GerarRelatorioAssertividade.py
sgc_python.bat python\AgendadorSGC.py retreino
```

No Linux, use `./sgc_python.sh` no lugar de `sgc_python.bat`.

---

## Agendador (aprendizado e relatórios)

Quando `SGC_AGENDADOR_AUTO=1` (padrão), o `main.py` sobe o `AgendadorSGC` em background:

| Tarefa | Horário padrão | Descrição |
|--------|----------------|-----------|
| Re-treino ML | 02:00 | Sync feedback GLPI, detecta correções, treina e implanta se válido |
| PDF assertividade | 03:00 | Relatório diário de acerto SGC vs fechamento GLPI |
| Relatório feedback | Domingo 04:00 | Cobertura/gaps do feedback de treino |

Horários configuráveis por variáveis de ambiente (`ML_RETRAIN_HOUR`, `ML_REPORT_HOUR`, etc.).

Também é possível rodar o agendador sozinho:

```bash
sgc_python.bat python\AgendadorSGC.py
```

---

## Variáveis de ambiente úteis

| Variável | Padrão | Função |
|----------|--------|--------|
| `SGC_AGENDADOR_AUTO` | `1` | Liga/desliga agendador no `main` |
| `SGC_INTERVALO_VARREDURA` | `30` | Segundos entre ciclos de monitoramento |
| `SGC_MONITOR_HEARTBEAT` | `60` | Intervalo de heartbeat nos logs |
| `TELEGRAM_TOKEN` | — | Opcional. Se vazio, o worker **não** notifica (Telegram desligado) |
| `ML_RETRAIN_HOUR` | `2` | Hora do re-treino |
| `ML_REPORT_HOUR` | `3` | Hora do PDF de assertividade |
| `ML_FEEDBACK_MESES` | `6` | Janela de feedback para treino |
| `ML_FORCAR_IMPLANTACAO` | — | Força implantação do modelo no re-treino |

---

## Banco de dados (principais tabelas)

| Tabela | Uso |
|--------|-----|
| `Tb_Ticket_new` | Chamados processados pelo robô |
| `Tb_Atrib` | Técnicos × equipes (elegibilidade) |
| `Tb_Ticket_Feedback_Temp` | Feedback de chamados fechados (treino ML) |
| `Tb_ML_Log` | Log de cada decisão de classificação |
| `Tb_Correcao_Feedback` | Divergências SGC vs equipe no fechamento GLPI |
| `tb_performance` | Métricas diárias de assertividade |

Scripts em `sql/`. A aplicação também aplica migrações na subida (`DbMigracao.py`).

Deploy só das tabelas Fase 3:

```text
sql/deploy_fase3_apenas_tabelas.sql
```

---

## Módulos e scripts relevantes

| Arquivo | Função |
|---------|--------|
| `FeedbackChamados.py` / `SincronizarFeedbackGLPI.py` | Importa fechados do GLPI para treino |
| `CorrecaoFeedback.py` / `DetectarCorrecoesGLPI.py` | Detecta equipe errada vs fechamento |
| `AssertividadeMetricas.py` / `RelatorioAssertividade.py` | Métricas e PDF de assertividade |
| `RelatorioFeedback.py` | Relatório de cobertura do feedback |
| `LiberarChamadosGLPI.py` | Remove da base local para reprocessar Novos |
| `PrepararFase2Local.py` / `VerificarFase2Local.py` | Prep/diagnóstico do ambiente |
| `TreinarModeloNovo.py` / `AvaliarModeloML.py` | Treino e avaliação offline |
| `teste_conexao.py` / `listar_chamados.py` | Utilitários de diagnóstico |

---

## Dependências principais

Definidas em `requirements.txt`:

- **pandas**, **scikit-learn**, **numpy** — ML e dados
- **pymysql** — MariaDB (`oracledb` opcional)
- **requests** — API GLPI
- **pyTelegramBotAPI** — Telegram
- **reportlab** — PDFs
- **cryptography** — configs criptografadas
- **beautifulsoup4** — limpeza de HTML das descrições

---

## Observações operacionais

- Credenciais ficam em `conf/*.dat` (criptografados). Não versionar `chave.key` nem `.dat` em repositórios públicos.
- O modelo ativo fica em `Modelo/ModeloML.pkl`; o monitoramento recarrega automaticamente quando o arquivo muda (após re-treino).
- Se não houver técnico elegível na equipe, o sistema tenta um técnico padrão configurado no código de atribuição.
- Logs diários: pasta `log/`. Relatórios: pasta `relatorios/`.

---

## Licença / uso

Projeto interno de automação de Service Desk (SGC). Uso restrito ao ambiente e às credenciais da organização.
