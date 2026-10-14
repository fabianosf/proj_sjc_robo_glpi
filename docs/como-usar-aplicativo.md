# Como mexer no aplicativo SGC

Guia do dia a dia (Windows). Para instalação em outro PC, use [`INSTALAR-WINDOWS.txt`](INSTALAR-WINDOWS.txt) / [`DEPLOY-WINDOWS.md`](DEPLOY-WINDOWS.md).

---

## 1) Ligar e desligar

| Ação | Como |
|------|------|
| **Ligar** (robô + painel, sem janela preta) | Dois cliques em `Iniciar_SGC.vbs` |
| **Parar** | Dois cliques em `Parar_SGC.vbs` |
| **Abrir o painel (neste PC)** | **http://127.0.0.1:8001** |
| **Abrir de outro PC (mesma rede)** | **http://IP_DO_PC:8001** (ex.: `http://10.1.26.209:8001`) |

Na primeira vez (ou depois de mudar o frontend):

```bat
cd frontend
npm run build
```

Autostart no login do Windows (opcional): `install_autostart_windows.bat`  
Remover: `uninstall_autostart_windows.bat`

---

## 2) Entrar no painel

1. Neste PC: http://127.0.0.1:8001 — outro PC na LAN: http://IP_DO_PC:8001  
2. Login com **matrícula** + **senha do Windows (AD)**  
3. Só entram usuários na allowlist (ADMIN configurado + técnicos N3 com matrícula)

A API escuta em `0.0.0.0:8001` (rede local). Se outro PC não conectar, rode **como Administrador** `abrir_firewall_mobile.bat` (libera a porta 8001).

- Perfil **ADMIN**: pode corrigir atribuição, técnicos, regras, matrículas.  
- Perfil **CONSULTA** (N3): principalmente leitura.

---

## 3) O que cada um faz (não misturar)

| Quem | Faz |
|------|-----|
| **Robô (Worker)** | Pega chamados **Novo** no GLPI → escolhe equipe → técnico → grava no SGC |
| **Painel** | Consulta, monitora e (ADMIN) **corrige** chamado já atribuído / plantão |

O painel **não** atribui chamados Novo automaticamente. Isso é só o robô.

---

## 4) Telas principais do painel

| Tela | Para quê |
|------|----------|
| **Dashboard** | Resumo / saúde do sistema |
| **Chamados** | Lista dos tickets no SGC; abra um para ver detalhe |
| **Equipes** | O que cada fila (N1, N2, N3…) costuma fazer |
| **Técnicos** | Situação, carga; ADMIN: editar / redirecionar plantão |
| **Regras** | Palavras-chave do `arqaux` (ADMIN) |
| **ML / Jobs / Relatórios** | Modelo, jobs, PDFs de assertividade (consulta) |
| **Configurações** | Ajustes do painel (conforme perfil) |

---

## 5) Corrigir um chamado (ADMIN)

Quando o chamado **já foi** para a pessoa/fila errada:

1. **Chamados** → abra o chamado  
2. **Enviar para outra fila**  
3. Escolha **Fila (equipe)** *ou* **Pessoa**  
4. Confirme  

Na tela aparece o **comprovante** (GLPI / SGC atualizados).  
Card **Por que foi atribuído? / Por que Fulano?** explica a decisão do robô (se o chamado estiver no SGC).

Se o ID **não estiver no SGC**: use **Consultar no GLPI** (atribuição feita fora do robô).

Passo a passo completo: [`operar-redirecionamento.md`](operar-redirecionamento.md).

---

## 6) Plantão: passar carga de um técnico para outro (ADMIN)

1. **Técnicos** → **Redirecionar**  
2. De técnico A → técnico B  
3. Confirme  

Útil em saída/troca de plantão. Não substitui o “manda pra fila” de um chamado só.

---

## 7) Conferir se o robô está vivo

- No navegador: http://127.0.0.1:8001/health → deve ter algo como `worker_alive: true`  
- Arquivo `log/worker_heartbeat.json`: `glpi_ok`, `updated_at` recente  
- Chamados Novos somem do GLPI e aparecem em **Chamados** no painel  

Se o painel abre mas o robô não atribui: rode de novo `Iniciar_SGC.vbs` (ou só o worker) e confira `conf/` / rede GLPI.

---

## 8) Problemas comuns

| Sintoma | O que fazer |
|---------|-------------|
| Página não abre | Ligar com `Iniciar_SGC.vbs`; conferir porta **8001** |
| Login negado | Matrícula na allowlist + senha AD; ver `backend/.env` |
| Não atribui Novos | Worker parado → `Iniciar_SGC.vbs`; ver heartbeat / GLPI |
| Chamado sem “por quê” no SGC | Pode existir só no GLPI (não passou pelo robô) |
| Janela preta / prompt | Use `Iniciar_SGC.vbs` / `Parar_SGC.vbs` (não `run_api.bat` no dia a dia) |

---

## 9) Arquivos úteis na pasta do projeto

| Arquivo | Uso |
|---------|-----|
| `Iniciar_SGC.vbs` | Sobe tudo oculto + abre o painel |
| `Parar_SGC.vbs` | Encerra robô e API |
| `docs/operar-redirecionamento.md` | Detalhe de redirecionar |
| `docs/requisitos.md` | O que o sistema deve fazer (RF) |
| `docs/retencao.md` | Limpeza de log/modelo/relatórios |
| `python/aplicar_retencao.py` | Script de retenção (dry-run / `--apply`) |

---

## 10) Resumo rápido

1. `Iniciar_SGC.vbs`  
2. http://127.0.0.1:8001 (ou http://IP:8001 na LAN) → login AD  
3. Robô cuida dos **Novos**; você (ADMIN) corrige pelo painel quando precisar  
4. `Parar_SGC.vbs` ao encerrar o dia (se não usar autostart)  
5. Outro PC sem acesso: botão direito em `abrir_firewall_mobile.bat` → Executar como administrador
