# Requisitos formais — SGC (ROBO)

| Campo | Valor |
|-------|--------|
| **Documento** | REQ-SGC-001 |
| **Versão** | 1.0 |
| **Data** | 2026-10-13 |
| **Escopo** | Worker de atribuição, classificação, elegibilidade, isolamento painel, auth |
| **Fora de escopo** | Telegram (removido), Power BI embed, disparo de re-treino pela API |

Origens principais: [POP-SGC-001](POP-SGC-001-aplicativo-completo.md), [README.md](../README.md), [operar-redirecionamento.md](operar-redirecionamento.md).

---

## RF-001 — Atribuição automática de chamado Novo

| Campo | Conteúdo |
|-------|----------|
| **ID** | RF-001 |
| **Descrição** | O Worker deve consultar periodicamente chamados com status **Novo** no GLPI, classificar a equipe, escolher técnico elegível, atribuir no GLPI e registrar em `Tb_Ticket_new` (e log ML quando aplicável). |
| **Origem** | POP-SGC-001 §2.1 / §4; README (worker) |
| **Componentes** | `main.py`, `python/main.py`, `python/trade.py`, `python/MetodosGenericos.py`, `python/GLPI_API.py`, MariaDB SGC |
| **Critério de aceite** | Dado um chamado Novo elegível na janela configurada, após um ciclo do Worker ele deixa de estar Novo no GLPI, aparece em `Tb_Ticket_new` com técnico/equipe, e o heartbeat registra atividade (`worker_alive` / `last_assigned_id` quando atribuído). |

---

## RF-002 — Pipeline de classificação de equipe

| Campo | Conteúdo |
|-------|----------|
| **ID** | RF-002 |
| **Descrição** | A equipe do chamado deve ser resolvida na ordem fixa: **DIRETO** (`arqaux`) → **FALLBACK_PARCIAL** → **ML** (se modelo aceitar) → **FALLBACK_CATEGORIA** → **FALLBACK_N1**. |
| **Origem** | POP-SGC-001 glossário DIRETO/ML; `MetodosGenericos.resolver_equipe_chamado` |
| **Componentes** | `python/MetodosGenericos.py`, `python/arqaux_rules.py`, `arqaux.txt`, `python/ML.py` |
| **Critério de aceite** | Para o mesmo texto de chamado: (1) palavra-chave DIRETO em `arqaux` produz método `DIRETO` e a equipe da regra; (2) sem DIRETO/parcial/ML válido, o método final é `FALLBACK_N1` com equipe `N1` (ou fallback de categoria se houver match). O método gravado em `Tb_ML_Log` reflete o estágio vencedor. |

---

## RF-003 — Técnico fixo (pin) na regra DIRETO

| Campo | Conteúdo |
|-------|----------|
| **ID** | RF-003 |
| **Descrição** | Regras `arqaux` no formato `EQUIPE@login-"PALAVRA"` devem priorizar o técnico pinado quando a regra DIRETO vencer. |
| **Origem** | `arqaux_rules.py`; POP / operar-redirecionamento (motivo pessoa) |
| **Componentes** | `python/arqaux_rules.py`, `python/MetodosGenericos.py`, `python/main.py` |
| **Critério de aceite** | Quando `tecnico_fixo` vem da regra DIRETO e o login existe/elegível, a atribuição tenta esse técnico antes dos demais candidatos da equipe. |

---

## RF-004 — Elegibilidade de técnico

| Campo | Conteúdo |
|-------|----------|
| **ID** | RF-004 |
| **Descrição** | Só técnicos em `Tb_Atrib` com `Sit=1`, da equipe resolvida, dentro do intervalo `[H1,H2]` (incluindo turno que cruza meia-noite), entram na lista; ordenação por menor `QtdC`; preferência opcional de `Empresa` vs localização do chamado. |
| **Origem** | POP-SGC-001 (`Tb_Atrib`); `listar_tecnicos_elegiveis_equipe` |
| **Componentes** | `python/MetodosGenericos.py`, tabela `Tb_Atrib` |
| **Critério de aceite** | Técnico `Sit=0` ou fora do horário não é escolhido. Entre elegíveis no horário, o de menor `QtdC` vem primeiro (salvo pools especiais Comunicação Interna / celular-manutenção). Se não houver elegível, a atribuição falha sem inventar login. |

---

## RF-005 — Isolamento Worker vs Painel

| Campo | Conteúdo |
|-------|----------|
| **ID** | RF-005 |
| **Descrição** | O painel (API + frontend) **não** atribui chamados em status Novo. Atribuição automática de Novos é exclusiva do Worker. O painel pode consultar e, com perfil ADMIN, corrigir (reatribuição / redirect técnico) em chamados já existentes. |
| **Origem** | POP-SGC-001 §2.2 / §4 “regra de ouro”; operar-redirecionamento.md |
| **Componentes** | `backend/app/**`, `frontend/src/**`, Worker `python/main.py` |
| **Critério de aceite** | Nenhuma rota da API realiza o fluxo de varredura/atribuição de Novos do Worker. Rotas de escrita ADMIN (`reassign`, `technicians/redirect`) não substituem o loop de Novos. Documentação oficial afirma o isolamento. |

---

## RF-006 — Autenticação AD + JWT

| Campo | Conteúdo |
|-------|----------|
| **ID** | RF-006 |
| **Descrição** | Acesso ao painel via login Windows (LogonUser AD) + emissão de JWT; allowlist: matrícula ADMIN configurada e técnicos N3 com matrícula válida; rotas `/api/v1/*` (exceto login) exigem JWT válido. |
| **Origem** | POP-SGC-001 §2.1 Acesso; `backend/README-AUTH.md` |
| **Componentes** | `backend/app/auth/**`, `backend/app/routers/auth.py`, frontend login |
| **Critério de aceite** | Login sem credencial/allowlist retorna erro. Com usuário allowlist + senha AD válida, retorna JWT. Request autenticado a `/api/v1/auth/me` devolve o usuário. Request sem token a rota protegida retorna 401. |

---

## RF-007 — Persistência e rastreabilidade da decisão

| Campo | Conteúdo |
|-------|----------|
| **ID** | RF-007 |
| **Descrição** | Após classificação/atribuição, o sistema registra método/equipe (e quando disponível `Motivo_Atrib`) para explicar “por que Fulano/equipe” no painel. |
| **Origem** | operar-redirecionamento.md; `Tb_ML_Log` |
| **Componentes** | `python/MLLog.py`, `python/main.py`, `backend/app/services/queries.py`, UI detalhe do chamado |
| **Critério de aceite** | Chamado atribuído pelo Worker e presente no SGC expõe no detalhe método de classificação e texto de motivo da pessoa (gravado ou reconstruído), sem expor segredos de `conf/`. |

---

## RF-008 — Correção ADMIN sem quebrar o Worker

| Campo | Conteúdo |
|-------|----------|
| **ID** | RF-008 |
| **Descrição** | ADMIN pode reatribuir um chamado (fila ou pessoa) e redirecionar carga técnico→técnico; essas ações atualizam GLPI+SGC e não disparam re-treino nem o loop de Novos. |
| **Origem** | operar-redirecionamento.md §2–3; POP-SGC-001 |
| **Componentes** | `backend/.../queries.py` (reassign/redirect), `TicketDetailPage`, `TechniciansPage` |
| **Critério de aceite** | Reassign bem-sucedido retorna comprovante (GLPI/SGC). Redirect move tickets locais do técnico origem. Worker continua independente (processo separado). |

---

## Rastreabilidade resumida

| RF | Worker | Painel | Auth |
|----|--------|--------|------|
| RF-001 | X | | |
| RF-002 | X | leitura | |
| RF-003 | X | | |
| RF-004 | X | | |
| RF-005 | X | X | |
| RF-006 | | X | X |
| RF-007 | X | X | |
| RF-008 | | X (ADMIN) | X |
