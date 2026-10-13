"""Matching Oracle login → CHAPAFUNC (sem banco)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.oracle_matricula import match_logins_to_chapas  # noqa: E402


def _row(chapa, nome, email, situacao="A"):
    return {
        "CHAPAFUNC": chapa,
        "NOMEFUNC": nome,
        "EMAILFUNC": email,
        "SITUACAOFUNC": situacao,
    }


def test_email_exact_and_nodot():
    funcs = [_row("059817", "FABIANO FREITAS", "fabiano.freitas@escola.br")]
    out, amb = match_logins_to_chapas(funcs, ["fabiano.freitas", "fabianofreitas"])
    assert amb == []
    assert out["fabiano.freitas"] == "59817"
    assert out["fabianofreitas"] == "59817"


def test_extra_ad_mail():
    funcs = [_row("27237", "JUAN DAMASCENO", "juan.damasceno@escola.br")]
    out, _ = match_logins_to_chapas(
        funcs,
        ["jdamasceno"],
        extra_emails={"jdamasceno": "juan.damasceno@escola.br"},
    )
    assert out["jdamasceno"] == "27237"


def test_name_unique_and_ambiguous():
    funcs = [
        _row("1", "JOSE CARLOS SILVA", "a@x"),
        _row("2", "JOSE ANTONIO SILVA", "b@x"),
        _row("3", "ANDRE LUIS SOUZA", "c@x"),
    ]
    out, amb = match_logins_to_chapas(funcs, ["jose.silva", "andre.souza"])
    assert "jose.silva" not in out
    assert "jose.silva" in amb
    assert out["andre.souza"] == "3"


def test_prefer_active_email():
    funcs = [
        _row("10", "ANA", "ana.souza@x", "D"),
        _row("11", "ANA SOUZA", "ana.souza@x", "A"),
    ]
    out, _ = match_logins_to_chapas(funcs, ["ana.souza"])
    assert out["ana.souza"] == "11"


def test_inactive_if_only_hit():
    funcs = [_row("99", "PAULO LIMA", "paulo.lima@x", "D")]
    out, _ = match_logins_to_chapas(funcs, ["paulo.lima"])
    assert out["paulo.lima"] == "99"


def test_accent_and_particle():
    funcs = [_row("44", "JOSÉ DA SILVA", "z@x")]
    out, amb = match_logins_to_chapas(funcs, ["jose.silva"])
    assert amb == []
    assert out["jose.silva"] == "44"


def test_ad_person_name_unique():
    funcs = [_row("55", "JOSÉ SILVA", "z@x")]
    out, amb = match_logins_to_chapas(
        funcs,
        ["jsilva"],
        extra_names={"jsilva": "José Silva"},
    )
    assert amb == []
    assert out["jsilva"] == "55"


def test_ad_person_name_homonym_skipped():
    funcs = [
        _row("1", "JOSÉ SILVA", "a@x"),
        _row("2", "JOSE SILVA", "b@x"),
    ]
    out, amb = match_logins_to_chapas(
        funcs,
        ["jsilva"],
        extra_names={"jsilva": "José Silva"},
    )
    assert "jsilva" not in out
    assert "jsilva" in amb


if __name__ == "__main__":
    test_email_exact_and_nodot()
    test_extra_ad_mail()
    test_name_unique_and_ambiguous()
    test_prefer_active_email()
    test_inactive_if_only_hit()
    test_accent_and_particle()
    test_ad_person_name_unique()
    test_ad_person_name_homonym_skipped()
    print("ok")
