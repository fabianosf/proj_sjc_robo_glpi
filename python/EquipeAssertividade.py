# EquipeAssertividade.py — regras de acerto por equipe (SGC vs fechamento GLPI)


def normalizar_equipe(equipe: str) -> str:
    return (equipe or "").strip().upper()


def acertou_classificacao_equipe(equipe_sgc: str, equipe_fechamento: str) -> bool:
    """
    Acerto quando a equipe classificada pelo SGC é a mesma equipe do técnico
    que fechou o chamado. Troca de técnico dentro da mesma equipe não é erro.
    """
    eq_sgc = normalizar_equipe(equipe_sgc)
    eq_fim = normalizar_equipe(equipe_fechamento)
    return bool(eq_sgc) and bool(eq_fim) and eq_sgc == eq_fim


def errou_classificacao_equipe(equipe_sgc: str, equipe_fechamento: str) -> bool:
    """Erro somente quando as equipes são diferentes."""
    eq_sgc = normalizar_equipe(equipe_sgc)
    eq_fim = normalizar_equipe(equipe_fechamento)
    if not eq_sgc or not eq_fim:
        return False
    return eq_sgc != eq_fim
