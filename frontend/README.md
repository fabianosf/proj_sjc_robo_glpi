# SGC Control Center (frontend)

Painel React somente leitura que consome a **API FastAPI** (`backend/`).  
Não acessa GLPI, MariaDB, `conf/`, modelos ML nem código Python.

## Stack

- React + TypeScript + Vite
- React Router
- Tailwind CSS v4
- TanStack Query
- Lucide React
- Recharts

## Configurar URL da API

1. Copie o exemplo:

```bat
copy .env.example .env
```

2. Edite `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

Use a mesma porta do `run_api.bat` / `SGC_API_PORT`.  
Reinicie o Vite após alterar o `.env`.

CORS da API permite apenas `http://localhost:5173` e `http://127.0.0.1:5173`.

## Comandos Windows

Na pasta `frontend`:

```bat
npm install
npm run dev
```

Build de produção:

```bat
npm run build
npm run preview
```

Suba a API antes (exemplo na raiz do projeto):

```bat
set SGC_API_PORT=8001
run_api.bat
```

## Páginas

| Rota | Conteúdo |
|------|----------|
| `/` | Dashboard |
| `/chamados` | Lista paginada + busca |
| `/chamados/:ticketId` | Detalhe + ML log |
| `/equipes` | Equipes |
| `/tecnicos` | Técnicos |
| `/ia` | Inteligência artificial |
| `/agendamentos` | Jobs do agendador |
| `/configuracoes` | URL da API e health |

## Badges de método

A API grava `DIRETO`; o painel exibe o rótulo **REGRA_DIRETA**. Também: `FALLBACK_PARCIAL`, `ML`, `FALLBACK_CATEGORIA`, `FALLBACK_N1`.  
Na lista de chamados o método não vem do endpoint de listagem → **Não disponível** (disponível no detalhe / overview ML).
