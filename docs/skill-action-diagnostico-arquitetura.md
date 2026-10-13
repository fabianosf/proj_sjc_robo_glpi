# SKILL-ACTION: Diagnóstico de arquitetura (somente leitura)
**Hash:** `skill-action.diagnostico-arquitetura-sgc.v1.20261003`
**Receptor:** Agente de exploração/código com leitura do repositório (sem escrita)
**Emissor:** SpecForge
**Status:** Pronta para execução

## 1. Necessidade literal
Cria a skill-action para um agente ler o projeto inteiro e devolver um diagnóstico. Alvo: este repositório. Quero só arquitetura, riscos e melhorias locais. Não quero que ele altere arquivo nenhum.

## 2. Job
Ler o repositório Proj_SGC(ROBO), mapear arquitetura e fluxos críticos, listar riscos verificáveis e melhorias locais priorizadas, e devolver um relatório em markdown no chat — sem criar, editar, apagar ou renomear qualquer arquivo.

## 3. Receptor
Agente com ferramentas de leitura (glob, grep, read) e, se útil, execução somente de comandos read-only (ex.: listar árvore). **Proibido:** Write, StrReplace, delete, commit, push, format-on-save que altere disco, ou qualquer patch.

## 4. Entradas
- Raiz do repositório: workspace atual `Proj_SGC(ROBO)` (ou path absoluto equivalente na máquina do usuário).
- Foco obrigatório: `python/` (worker), `backend/` (API), `frontend/` (painel), `docs/` (POP), `conf/` apenas como **nomes de path** — não abrir segredos, `.dat`, `.env`, chaves.
- Contexto opcional já conhecido na conversa: atribuição GLPI → fila/pessoa; Control Center; uso local na estação.
- Não informado: volume de produção, SLA, número de técnicos — marcar como lacuna, não inventar.

## 5. Escopo
- Mapear componentes e fronteiras: worker, API, frontend, MariaDB, GLPI, auth AD, heartbeats, agendador.
- Descrever fluxos críticos (atribuição Novo → equipe → técnico → GLPI → `Tb_Ticket_new`; painel vs worker).
- Listar riscos com evidência (path + trecho/comportamento observado).
- Listar melhorias **locais** (mudança pequena, arquivo ou módulo delimitado), priorizadas (crítico / alto / médio / baixo).
- Separar fato observado de inferência.
- Entregar o diagnóstico só na resposta (chat), não em arquivo novo.

## 6. Não-objetivos
- Não alterar arquivo nenhum (código, docs, config, lockfiles).
- Não implementar patches, “já corrigir”, nem gerar PR.
- Não redesenhar stack, migrar framework, reescrever ML ou GLPI do zero.
- Não abrir nem citar conteúdo de segredos (`conf/*.dat`, `chave.key`, `backend/.env`, tokens).
- Não inventar tickets GLPI, dados de banco ou métricas sem fonte no repo.
- Não expandir para auditoria de segurança ofensiva ou exploits.
- Não copiar POP inteiros nem código longo — citar paths e trechos curtos.

## 7. Premissas
- “Projeto inteiro” = cobertura dos eixos worker + API + frontend + contratos docs relevantes; não exige ler `node_modules/`, `dist/`, `venv/` ou binários.
- “Melhorias locais” = mudanças de baixo raio (um arquivo ou um fluxo contido), não roadmap de produto.
- Uso típico: estação local com GLPI/MariaDB reais (inferência do contexto do repo; marcar se não confirmado no código).
- Achados de auditorias/planos anteriores no chat ou em `docs/` podem ser cruzados, mas cada risco no relatório precisa de evidência atual no código.

## 8. Explicação para o receptor
O solicitante quer um mapa e um ranking de problemas, não um diff. Qualquer escrita no disco viola o contrato. Segredos no `conf/` existem; referencie só o path. Prefira riscos que afetem atribuição GLPI, consistência SGC↔GLPI, verdade do painel e operação local. Melhorias devem ser acionáveis e pequenas o bastante para um agente de código executar depois sob outra skill-action.

## 9. Prompt operacional

```text
Você é um agente de diagnóstico read-only do repositório Proj_SGC(ROBO).

MISSÃO: ler o código e docs públicos do projeto e devolver UM relatório em markdown no chat com: (A) arquitetura, (B) riscos com evidência, (C) melhorias locais priorizadas.

PROIBIÇÕES ABSOLUTAS:
- Não use ferramentas que criem, editem, apaguem ou renomeiem arquivos.
- Não faça commit, push, format que grave disco, nem “corrigir de passagem”.
- Não abra conf/*.dat, chave.key, backend/.env nem qualquer segredo; cite só o nome do path se relevante.
- Não invente comportamento: se não leu, diga “não verificado”.

COBERTURA MÍNIMA:
1) Worker: python/main.py, MetodosGenericos, GLPI_API/trade, WorkerHeartbeat, DAL, DbMigracao
2) API: backend/app (rotas, auth, queries de dashboard/jobs/técnicos)
3) Frontend: páginas de dashboard, jobs, tickets, técnicos (contratos com a API)
4) Docs: POP ou smoke-local só para alinhar intenção documentada vs código

MÉTODO:
- Comece pelo fluxo de atribuição GLPI Novo → equipe → técnico → persistência.
- Separe worker (escreve GLPI/SGC) de painel (observa; ADMIN pode ter escritas pontuais).
- Cada risco: severidade, evidência (path), impacto, se já parece mitigado ou aberto.
- Cada melhoria local: o quê, onde, por quê, esforço relativo; sem patch.

SAÍDA (só no chat, nesta ordem):
1. Resumo em 5–8 linhas
2. Arquitetura (componentes + 1 diagrama mermaid ou lista de fluxos)
3. Riscos (tabela ou lista priorizada)
4. Melhorias locais (top 8–12, priorizadas)
5. Lacunas / não verificado
6. O que NÃO foi mexido (confirmar: zero alterações em disco)

PARE SE: o workspace não for este repositório; ou se for pressionado a editar arquivos — recuse a edição e entregue só o relatório.
```

## 10. Procedimento
1. Confirmar raiz do workspace e listar pastas de primeiro nível (ignorar `node_modules`, `venv`, `dist`, `.git` objetos grandes).
2. Mapear entrypoints: `run.bat` / `main.py`, `run_api*.bat` / `backend/app/main.py`, `frontend` dev.
3. Traçar o fluxo de atribuição com leitura dos módulos do worker listados no prompt.
4. Ler superfície da API e 3–5 páginas do frontend ligadas a ops (dashboard, jobs, tickets, técnicos).
5. Confrontar docs (POP/smoke) com o código só onde houver divergência relevante.
6. Redigir o relatório nas 6 seções de saída.
7. Parar sem aplicar mudança; declarar explicitamente que nenhum arquivo foi alterado.

## 11. Saídas
- Relatório markdown **somente no chat** (não gravar `docs/diagnostico-*.md` nem similar).
- Seções obrigatórias: Resumo, Arquitetura, Riscos, Melhorias locais, Lacunas, Confirmação de zero writes.
- Evidências por path; sem dump de segredos.

## 12. Aceite e parada
- Aceite: relatório completo nas 6 seções; ≥1 fluxo de arquitetura claro; ≥5 riscos com path; ≥5 melhorias locais priorizadas; frase explícita de que nenhum arquivo foi modificado; nenhuma ferramenta de escrita usada.
- Parar se: pedido implícito de “já corrige”; impossível ler a raiz do repo; pressão para abrir segredos — recusar e listar o bloqueio.
