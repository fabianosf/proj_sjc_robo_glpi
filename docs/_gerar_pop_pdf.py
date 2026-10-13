# -*- coding: utf-8 -*-
"""Gera PDF profissional do POP-SGC-010."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", r"C:\Windows\Fonts\ariali.ttf"))

OUT = Path(__file__).resolve().parent / "POP-SGC-010-aplicativo.pdf"

NAVY = HexColor("#0f3d3e")
TEAL = HexColor("#0d7377")
SLATE = HexColor("#334155")
MUTED = HexColor("#64748b")
LINE = HexColor("#e2e8f0")
BG_SOFT = HexColor("#f1f5f9")
BG_HEAD = HexColor("#0f3d3e")
WHITE = white

page_w, page_h = A4
MARGIN = 18 * mm


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, page_h - 12 * mm, page_w, 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Arial-Bold", 8)
    canvas.drawString(MARGIN, page_h - 7.5 * mm, "SGC  |  Procedimento Operacional Padrão")
    canvas.setFont("Arial", 8)
    canvas.drawRightString(page_w - MARGIN, page_h - 7.5 * mm, "POP-SGC-010  ·  v2.0")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 12 * mm, page_w - MARGIN, 12 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Arial", 8)
    canvas.drawString(MARGIN, 7 * mm, "Uso interno  ·  Confidencial")
    canvas.drawRightString(page_w - MARGIN, 7 * mm, f"Página {doc.page}")
    canvas.restoreState()


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        fontName="Arial-Bold",
        fontSize=20,
        textColor=NAVY,
        spaceAfter=6,
        leading=24,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSub",
        fontName="Arial",
        fontSize=10,
        textColor=MUTED,
        spaceAfter=3,
        leading=13,
    )
)
styles.add(
    ParagraphStyle(
        name="H1Doc",
        fontName="Arial-Bold",
        fontSize=11,
        textColor=NAVY,
        spaceBefore=12,
        spaceAfter=5,
        leading=14,
    )
)
styles.add(
    ParagraphStyle(
        name="H2Doc",
        fontName="Arial-Bold",
        fontSize=9.5,
        textColor=TEAL,
        spaceBefore=7,
        spaceAfter=3,
        leading=12,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyDoc",
        fontName="Arial",
        fontSize=8.5,
        textColor=SLATE,
        alignment=TA_JUSTIFY,
        spaceAfter=3,
        leading=11,
    )
)
styles.add(
    ParagraphStyle(
        name="ItemDoc",
        fontName="Arial",
        fontSize=8.5,
        textColor=SLATE,
        leftIndent=8,
        spaceAfter=1.5,
        leading=11,
    )
)
styles.add(
    ParagraphStyle(
        name="Cell", fontName="Arial", fontSize=7.5, textColor=SLATE, leading=9.5
    )
)
styles.add(
    ParagraphStyle(
        name="CellHead",
        fontName="Arial-Bold",
        fontSize=7.5,
        textColor=WHITE,
        leading=9.5,
    )
)
styles.add(
    ParagraphStyle(
        name="FooterNote",
        fontName="Arial-Italic",
        fontSize=7.5,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceBefore=8,
    )
)


def P(text, style="BodyDoc"):
    return Paragraph(text, styles[style])


def hrule():
    return HRFlowable(width="100%", thickness=0.7, color=TEAL, spaceBefore=1, spaceAfter=6)


def make_table(data, col_widths=None):
    rows = []
    for i, row in enumerate(data):
        st = "CellHead" if i == 0 else "Cell"
        rows.append([Paragraph(str(c), styles[st]) for c in row])
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BG_HEAD),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_SOFT]),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def build() -> Path:
    story = []
    usable = page_w - 2 * MARGIN

    story.append(Spacer(1, 4 * mm))
    story.append(P("PROJ SGC (ROBO)", "CoverSub"))
    story.append(P("Procedimento Operacional Padrão", "CoverTitle"))
    story.append(
        P("Aplicativo completo — Worker · API · Painel de consulta", "CoverSub")
    )
    story.append(hrule())

    story.append(
        make_table(
            [
                ["Campo", "Valor"],
                ["Documento", "POP-SGC-010"],
                ["Versão", "2.0"],
                ["Data", "19/09/2026"],
                ["Owner", "Matrícula 59817 (ADMIN)"],
                ["Classificação", "Uso interno — Confidencial"],
            ],
            [usable * 0.28, usable * 0.72],
        )
    )
    story.append(Spacer(1, 4 * mm))

    story.append(P("1. Objetivo e escopo", "H1Doc"))
    story.append(hrule())
    story.append(
        P(
            "Padronizar a operação do <b>SGC</b>: atribuição automática de chamados no <b>GLPI</b> "
            "e consulta via <b>Control Center</b> (somente leitura). O painel não atribui, "
            "não altera GLPI/ML e não depende de Telegram.",
            "BodyDoc",
        )
    )
    story.append(
        make_table(
            [
                ["Componente", "Função"],
                [
                    "Worker",
                    "Monitora GLPI, classifica equipe, atribui técnico, grava MariaDB",
                ],
                [
                    "API",
                    "FastAPI somente leitura + autenticação Active Directory",
                ],
                [
                    "Frontend",
                    "Painel React — dashboard, chamados, equipes, IA, jobs",
                ],
            ],
            [usable * 0.22, usable * 0.78],
        )
    )

    story.append(P("2. Stack tecnológica", "H1Doc"))
    story.append(hrule())
    story.append(
        make_table(
            [
                ["Camada", "Tecnologia"],
                ["Worker", "Python 3.10+, pandas, scikit-learn, pymysql, requests"],
                ["Config", "conf/*.dat + chave.key (Fernet)"],
                ["API", "FastAPI, Uvicorn, PyJWT, pywin32 (LogonUser AD)"],
                [
                    "Frontend",
                    "React 19, TypeScript, Vite 8, Tailwind 4, TanStack Query",
                ],
                ["Dados", "MariaDB (base SGC)"],
                [
                    "Integrações",
                    "GLPI REST · Telegram opcional (desligado sem token)",
                ],
            ],
            [usable * 0.22, usable * 0.78],
        )
    )

    story.append(P("3. Arquitetura", "H1Doc"))
    story.append(hrule())
    story.append(
        P(
            "<font face='Courier' size='8'>"
            "GLPI  →  Worker (run.bat)  →  MariaDB  →  API (run_api*.bat)  ←  AD<br/>"
            "                                                  ↓<br/>"
            "                                            Frontend (:5173 / dist)"
            "</font>",
            "BodyDoc",
        )
    )

    story.append(P("4. Regras de negócio", "H1Doc"))
    story.append(hrule())
    story.append(P("4.1 Atribuição (Worker)", "H2Doc"))
    for t in [
        "1. Consulta chamados GLPI com status <b>Novo</b> (ciclo ~30 s).",
        "2. Se já existe em <b>Tb_Ticket_new</b> → ignora. Erro de DB → <b>fail-closed</b> (não reatribui).",
        "3. Define equipe: DIRETO → FALLBACK_PARCIAL → ML → FALLBACK_CATEGORIA → FALLBACK_N1.",
        "4. Seleciona técnico elegível em <b>Tb_Atrib</b> (Sit=1, horário, menor carga).",
        "5. Atribui no GLPI → só então INSERT local + carga. Falha no INSERT → log crítico, sem carga.",
        "6. Telegram: somente se <b>TELEGRAM_TOKEN</b> definido; caso contrário, não notifica.",
    ]:
        story.append(P(t, "ItemDoc"))

    story.append(P("4.2 Aprendizado", "H2Doc"))
    story.append(
        P(
            "Agendador (padrão ligado): re-treino ~02:00, PDF assertividade ~03:00, relatório feedback (domingo). "
            "Modelo ativo: <b>Modelo/ModeloML.pkl</b>.",
            "BodyDoc",
        )
    )

    story.append(P("4.3 Acesso ao painel", "H2Doc"))
    story.append(
        make_table(
            [
                ["Pode entrar", "Não pode"],
                ["Matrícula 59817", "Qualquer outra matrícula"],
                [
                    "N3 ativo (Sit=1) com Matricula real em Tb_Atrib",
                    "00000 / vazio · outras equipes · login por nome.sobrenome",
                ],
            ],
            [usable * 0.48, usable * 0.52],
        )
    )
    story.append(Spacer(1, 1.5 * mm))
    story.append(
        P(
            "Login = <b>matrícula</b> + <b>senha Windows (AD)</b>. Allowlist antes do AD. Perfil: ADMIN. "
            "Rate limit: 10 tentativas/IP/min. Logout revoga JWT (jti); TTL padrão 120 min.",
            "BodyDoc",
        )
    )
    story.append(P("4.4 Isolamento", "H2Doc"))
    story.append(
        P(
            "API e painel <b>não</b> escrevem em GLPI, Telegram, arqaux.txt nem modelo ML.",
            "BodyDoc",
        )
    )

    story.append(P("5. Operação", "H1Doc"))
    story.append(hrule())
    story.append(P("5.1 Subir o sistema", "H2Doc"))
    story.append(
        make_table(
            [
                ["#", "Componente", "Comando"],
                ["1", "Worker", "run.bat"],
                ["2", "API (dev)", "run_api_dev.bat"],
                ["3", "API (prod)", "set SGC_API_PORT=8001  →  run_api.bat"],
                [
                    "4",
                    "Frontend",
                    "cd frontend → npm run dev   ou   build_frontend.bat",
                ],
            ],
            [usable * 0.08, usable * 0.22, usable * 0.70],
        )
    )
    story.append(
        P(
            "Ordem: MariaDB → Worker → API → Frontend. Login: <b>http://127.0.0.1:5173</b>.",
            "BodyDoc",
        )
    )

    story.append(P("5.2 Variáveis críticas", "H2Doc"))
    story.append(
        make_table(
            [
                ["Variável", "Uso"],
                ["TELEGRAM_TOKEN", "Opcional (vazio = sem Telegram)"],
                ["SGC_JWT_SECRET", "Obrigatório na API (≥ 32 caracteres)"],
                ["SGC_AD_DOMAIN", "Domínio AD (ex.: GRBF)"],
                ["SGC_AUTH_ADMIN_MATRICULAS", "Default: 59817"],
                ["SGC_AUTH_ADMIN_EQUIPES", "Default: N3"],
                ["SGC_API_PORT / SGC_CORS_ORIGINS", "Bind da API / CORS"],
                ["VITE_API_BASE_URL", "URL da API no frontend"],
            ],
            [usable * 0.40, usable * 0.60],
        )
    )
    story.append(
        P(
            "Credenciais GLPI/DB: somente em <b>conf/</b>. Matrículas N3: "
            "<font face='Courier' size='7'>sgc_python.bat python\\ListarMatriculasN3Pendentes.py</font>",
            "BodyDoc",
        )
    )

    story.append(P("6. API — endpoints", "H1Doc"))
    story.append(hrule())
    story.append(
        make_table(
            [
                ["Método", "Rota", "Auth"],
                ["GET", "/health", "Público"],
                ["POST", "/api/v1/auth/login", "Público (AD + allowlist)"],
                ["POST", "/api/v1/auth/logout", "JWT (revoga)"],
                ["GET", "/api/v1/auth/me", "JWT"],
                ["GET", "/api/v1/dashboard/summary", "JWT"],
                ["GET", "/api/v1/tickets · /tickets/{id}", "JWT"],
                ["GET", "/api/v1/teams · /technicians", "JWT"],
                ["GET", "/api/v1/ml/overview", "JWT (GESTOR+)"],
                ["GET", "/api/v1/jobs", "JWT (OPERADOR+)"],
            ],
            [usable * 0.14, usable * 0.54, usable * 0.32],
        )
    )

    story.append(P("7. Incidentes rápidos", "H1Doc"))
    story.append(hrule())
    story.append(
        make_table(
            [
                ["Sintoma", "Ação"],
                [
                    "Sem permissão no login",
                    "Conferir matrícula / N3 + Matricula em Tb_Atrib",
                ],
                ["Senha inválida", "Senha Windows / SGC_AD_DOMAIN"],
                ["Health database fail", "MariaDB + conf/sgc.dat"],
                ["Chamados não atribuem", "Worker ligado? Logs em log/? GLPI?"],
                ["Painel sem dados", "API no ar? VITE_API_BASE_URL? JWT?"],
                ["Porta ocupada", "set SGC_API_PORT=8001"],
            ],
            [usable * 0.35, usable * 0.65],
        )
    )
    story.append(
        P(
            "<b>Prioridade:</b> worker + GLPI + banco. O painel é apenas consulta.",
            "BodyDoc",
        )
    )

    story.append(P("8. Checklist de saúde", "H1Doc"))
    story.append(hrule())
    for item in [
        "Worker em execução sem erro fatal",
        "GET /health → status e database ok",
        "Login 59817 + senha AD ok",
        "Fora da allowlist → 401",
        "Dashboard e chamados carregam",
        "N3 com matrícula preenchida consegue entrar (se aplicável)",
    ]:
        story.append(P(f"☐  {item}", "ItemDoc"))

    story.append(P("9. Aprovação", "H1Doc"))
    story.append(hrule())
    story.append(
        make_table(
            [
                ["Papel", "Identificação", "Data", "Rubrica"],
                ["Owner ADMIN", "59817", "____ / ____ / ________", ""],
                ["N3 (ciência)", "", "____ / ____ / ________", ""],
            ],
            [usable * 0.22, usable * 0.28, usable * 0.30, usable * 0.20],
        )
    )

    story.append(Spacer(1, 6 * mm))
    story.append(
        P(
            "Documento gerado a partir do POP-SGC-010 v2.0 — uso interno.",
            "FooterNote",
        )
    )

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="POP-SGC-010 — Aplicativo SGC",
        author="SGC Control Center",
        subject="Procedimento Operacional Padrão",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return OUT


if __name__ == "__main__":
    path = build()
    print("PDF_OK", path)
    print("SIZE_KB", round(path.stat().st_size / 1024, 1))
