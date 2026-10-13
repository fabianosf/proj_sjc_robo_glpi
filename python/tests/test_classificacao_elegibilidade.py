"""Testes de regressão do pipeline de classificação e elegibilidade (sem GLPI/DB reais)."""

from __future__ import annotations

import sys
import unittest
from datetime import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from MetodosGenericos import ClMetodosGenericos  # noqa: E402
from arqaux_rules import parse_line  # noqa: E402


def _met() -> ClMetodosGenericos:
    """Instância sem abrir DAL/GLPI reais."""
    obj = object.__new__(ClMetodosGenericos)
    obj.trade = MagicMock()
    obj.dal_sgc = MagicMock()
    obj._tem_dat_reg = False
    return obj


class TestClassificacaoElegibilidade(unittest.TestCase):
    def test_parse_arqaux_direto_com_pin(self):
        rule = parse_line('N2@samuel.jesus-"CELULAR","TELA"')
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule.equipe, "N2")
        self.assertEqual(rule.tecnico, "samuel.jesus")
        self.assertIn("CELULAR", rule.keywords)

    def test_hora_no_expediente_normal_e_madrugada(self):
        self.assertTrue(
            ClMetodosGenericos._hora_no_expediente(time(10, 0), time(8, 0), time(17, 0))
        )
        self.assertFalse(
            ClMetodosGenericos._hora_no_expediente(time(7, 0), time(8, 0), time(17, 0))
        )
        self.assertTrue(
            ClMetodosGenericos._hora_no_expediente(time(23, 0), time(22, 0), time(6, 0))
        )
        self.assertTrue(
            ClMetodosGenericos._hora_no_expediente(time(3, 0), time(22, 0), time(6, 0))
        )
        self.assertFalse(
            ClMetodosGenericos._hora_no_expediente(time(12, 0), time(22, 0), time(6, 0))
        )

    def test_resolver_equipe_direto_vence(self):
        met = _met()
        with patch.object(
            met, "definirAtribuicaoDiretaDetalhada", return_value=("N3", "fulano.silva")
        ):
            with patch.object(met, "definirAtribuicaoParcial", return_value="N2"):
                res = met.resolver_equipe_chamado(
                    ml=MagicMock(),
                    modelo=(object(), object()),
                    titulo="RESET DE SENHA",
                    categoria="ACESSO",
                    descricao="",
                    localizacao="",
                )
        self.assertEqual(res["metodo"], "DIRETO")
        self.assertEqual(res["equipe"], "N3")
        self.assertEqual(res["tecnico_fixo"], "fulano.silva")

    def test_resolver_equipe_fallback_n1_quando_nada_bate(self):
        met = _met()
        ml = MagicMock()
        ml.classificar_chamado_detalhado.return_value = {
            "equipe": "",
            "equipe_ml_bruta": "",
            "equipe_2a": "",
            "confianca": 0.0,
            "margem": 0.0,
            "motivo_rejeicao": "abaixo do limiar",
        }
        with patch.object(met, "definirAtribuicaoDiretaDetalhada", return_value=("", "")):
            with patch.object(met, "definirAtribuicaoParcial", return_value=""):
                with patch.object(met, "definirAtribuicaoFallbackCategoria", return_value=""):
                    res = met.resolver_equipe_chamado(
                        ml=ml,
                        modelo=(object(), object()),
                        titulo="assunto genérico",
                        categoria="OUTROS",
                        descricao="",
                        localizacao="",
                    )
        self.assertEqual(res["metodo"], "FALLBACK_N1")
        self.assertEqual(res["equipe"], "N1")

    def test_listar_tecnicos_elegiveis_ordena_por_qtdc(self):
        met = _met()
        df = pd.DataFrame(
            [
                {
                    "Usuario": "tec.alto",
                    "H1": "00:00:00",
                    "H2": "23:59:59",
                    "QtdC": 5,
                    "Empresa": "",
                },
                {
                    "Usuario": "tec.baixo",
                    "H1": "00:00:00",
                    "H2": "23:59:59",
                    "QtdC": 1,
                    "Empresa": "",
                },
                {
                    "Usuario": "tec.fora",
                    "H1": "00:00:00",
                    "H2": "00:01:00",
                    "QtdC": 0,
                    "Empresa": "",
                },
            ]
        )
        met.dal_sgc.read.return_value = df

        def _hora(_atual, _h1, h2):
            return h2 != time(0, 1, 0)

        with patch.object(
            ClMetodosGenericos,
            "_eh_chamado_comunicacao_interna",
            classmethod(lambda cls, *a, **k: False),
        ):
            with patch.object(
                ClMetodosGenericos, "_hora_no_expediente", staticmethod(_hora)
            ):
                lista = met.listar_tecnicos_elegiveis_equipe(
                    "N1", "titulo", "LOCAL", categoria=""
                )

        self.assertEqual(lista[0], "tec.baixo")
        self.assertIn("tec.alto", lista)
        self.assertNotIn("tec.fora", lista)


if __name__ == "__main__":
    unittest.main()
