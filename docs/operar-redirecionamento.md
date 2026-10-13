# Operar redirecionamento de chamados

Há **três** fluxos. O painel **não** atribui a fila **Novo** automaticamente — isso é o robô.

## 1) Automático — worker (Novos)

Atribui chamados **Novo** no GLPI → equipe → técnico elegível → `Tb_Ticket_new`.

### Sem ficar no prompt (recomendado)

1. Uma vez: `frontend` → `npm run build` (painel estático).
2. Dia a dia: dois cliques em **`Iniciar_SGC.vbs`** (worker + API **sem janela preta**; abre o painel).
3. Painel: **http://127.0.0.1:8001**
4. Para parar: **`Parar_SGC.vbs`**.

`run.bat` também inicia oculto (delega para o `.vbs`).  
Autostart no logon: `install_autostart_windows.bat` / remover: `uninstall_autostart_windows.bat`.

### Manual (dev — com console)

Worker: `venv\Scripts\python.exe main.py`  
API + Vite: `run_api_dev.bat` + `npm run dev`.

### Como saber que está atribuindo

- `log/worker_heartbeat.json`: `glpi_ok`, `novos_na_fila`, `updated_at` fresco
- `/health` com `worker_alive: true`
- Chamado sai de Novo no GLPI e aparece em Chamados (fonte SGC)

---

## 2) Manual — “manda pra fila” (um chamado)

Quando um chamado **já atribuído** caiu na pessoa/equipe errada (ex.: N3 → fila N2).

1. Login **ADMIN**
2. **Chamados** → abra o chamado
3. **Enviar para outra fila**
4. Escolha **Fila (equipe)** (ex. N2) **ou** **Pessoa**
5. Confirme — atualiza GLPI + SGC; mensagem do tipo *“Chamado #42 enviado para a fila N2 (técnico: …)”*

### Como verificar se deu certo

Após enviar, confira o **comprovante** na tela do chamado:

- GLPI atualizado — sim/não  
- SGC atualizado — sim/não  
- Notificação ao destino — sim/não  
- Aviso no seu sino (ADMIN)

Equipe e Técnico na ficha ficam destacados (“atualizado agora”). Se falhar (fila sem técnico / GLPI recusou), aparece card vermelho com o motivo.

Se a fila não tiver técnico ativo **no horário**, a API avisa e não move.

API: `POST /api/v1/tickets/{id}/reassign`

### Como decidir a fila (N1, N2, N3…)

- Página **Equipes**: resumo do que cada fila faz + exemplos das regras (`arqaux`).
- No chamado: card **Por que foi atribuído?** (método, palavras, técnico).
- Motivo da **pessoa** gravado pelo robô em `Tb_ML_Log.Motivo_Atrib` (elegíveis + QtdC ou técnico fixo).
- Se o ID **não estiver no SGC**: botão **Consultar no GLPI** (atribuição externa).
- No modal **Enviar para outra fila**: cada chip mostra o resumo da fila.

---

## 3) Manual — redirect técnico em lote (plantão)

Página **Técnicos** → **Redirecionar** de A para B (todos os tickets locais de A).  
Útil em saída/troca de plantão; **não** substitui o “manda pra fila” por chamado.

---

## Objetivo × ferramenta

| Objetivo | O que usar |
|----------|------------|
| Atribuir Novos automaticamente | Worker (`run.bat` ou autostart) |
| Entender o que N1/N2/N3 fazem | Equipes (guia) ou modal de reatribuir |
| Ver por que caiu em Fulano | Chamado → “Por que Fulano?” / Consultar GLPI se 404 SGC |
| Corrigir um chamado (ex. manda pra N2) | ADMIN → Chamado → Enviar para outra fila |
| Passar toda a carga A→B | ADMIN → Técnicos → Redirecionar |
| Só olhar fila/status | Painel |

## Checklist se “não está redirecionando” Novos

- Worker parado → autostart ou `run.bat`
- Heartbeat antigo / `glpi_ok: false` → GLPI/`conf`
- `/health` com `database: error` → MariaDB
- Técnicos `Sit=0` ou fora do horário → skip
- Dois workers → deixe um só
