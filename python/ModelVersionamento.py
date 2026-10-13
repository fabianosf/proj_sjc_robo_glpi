# ModelVersionamento.py — versionamento e rollback do modelo ML

import json
import shutil
from datetime import datetime
from pathlib import Path

from logger import ClLog
from paths import MODEL_DIR

MODELO_ATIVO = MODEL_DIR / "ModeloML.pkl"
METRICS_FILE = MODEL_DIR / "metrics.json"
MAX_VERSOES = 20


class ClModelVersionamento:
    logger = ClLog()

    def _carregar_metrics(self) -> dict:
        if not METRICS_FILE.exists():
            return {"versoes": [], "ativo": ""}
        with open(METRICS_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _salvar_metrics(self, data: dict) -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def registrar_implantacao(self, metadata: dict) -> str:
        """Arquiva cópia versionada do modelo ativo e atualiza metrics.json."""
        f1 = metadata.get("f1_macro")
        ts = datetime.now()
        f1_str = f"{f1:.3f}" if f1 is not None else "0.000"
        nome = f"ModeloML_v{ts:%Y%m%d_%H%M%S}_f1-{f1_str}.pkl"
        destino = MODEL_DIR / nome

        if MODELO_ATIVO.exists():
            shutil.copy2(MODELO_ATIVO, destino)

        entry = {
            "arquivo": nome,
            "data": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "f1_macro": f1,
            "version": metadata.get("version"),
            "train_samples": metadata.get("train_samples"),
            "classes": len(metadata.get("class_counts") or {}),
        }

        metrics = self._carregar_metrics()
        versoes = metrics.get("versoes", [])
        versoes.insert(0, entry)
        metrics["versoes"] = versoes[:MAX_VERSOES]
        metrics["ativo"] = nome
        self._salvar_metrics(metrics)

        self.logger.registrarActionLog("ML", "ATIVIDADE", f"MODELO VERSIONADO: {nome}")
        return nome

    def listar_versoes(self) -> list:
        return self._carregar_metrics().get("versoes", [])

    def restaurar(self, arquivo: str) -> bool:
        origem = MODEL_DIR / arquivo
        if not origem.is_file():
            self.logger.registrarActionLog("ML", "AVISO", f"VERSÃO NÃO ENCONTRADA: {arquivo}")
            return False
        shutil.copy2(origem, MODELO_ATIVO)
        metrics = self._carregar_metrics()
        metrics["ativo"] = arquivo
        self._salvar_metrics(metrics)
        self.logger.registrarActionLog("ML", "ATIVIDADE", f"MODELO RESTAURADO: {arquivo}")
        return True
