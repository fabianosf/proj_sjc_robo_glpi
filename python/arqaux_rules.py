"""
Leitura/gravação de arqaux.txt — regras palavra-chave → equipe [@tecnico].

Formatos:
  N8-"AR CONDICIONADO","LÂMPADA"
  N8@fulano.silva-"AR CONDICIONADO"
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class Rule:
    equipe: str
    keywords: List[str] = field(default_factory=list)
    tecnico: Optional[str] = None  # login Windows opcional (pin)

    def to_line(self) -> str:
        eq = (self.equipe or "").strip().upper()
        tec = (self.tecnico or "").strip()
        prefix = f"{eq}@{tec}" if tec else eq
        kws = ",".join(f'"{k.strip().upper()}"' for k in self.keywords if k.strip())
        return f"{prefix}-{kws}"


_PREFIX_RE = re.compile(
    # Equipe 1–5 chars; @login opcional (sem consumir o "-" separador); "-" opcional.
    r'^([A-Za-z0-9]{1,5})(?:@([^\s@"\-]+))?\s*-?\s*',
    re.UNICODE,
)


def parse_line(line: str) -> Optional[Rule]:
    item = (line or "").strip()
    if not item or item.startswith("#"):
        return None
    m = _PREFIX_RE.match(item)
    if not m:
        return None
    equipe = m.group(1).strip().upper()
    tecnico = (m.group(2) or "").strip() or None
    keywords = [k.strip().upper() for k in re.findall(r'"([^"]*)"', item) if k.strip()]
    if not equipe or not keywords:
        return None
    return Rule(equipe=equipe, keywords=keywords, tecnico=tecnico)


def load_rules(path: Path) -> List[Rule]:
    if not path.is_file():
        return []
    rules: List[Rule] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        rule = parse_line(line)
        if rule:
            rules.append(rule)
    return rules


def save_rules(path: Path, rules: List[Rule], *, backup: bool = True) -> None:
    path = Path(path)
    if backup and path.is_file():
        bak = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak)
    lines = [r.to_line() for r in rules if r.keywords and r.equipe]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_rules_as_tuples(path: Path) -> List[Tuple[str, List[str], Optional[str]]]:
    """Compatível com o worker: (equipe, keywords, tecnico|None)."""
    return [(r.equipe, r.keywords, r.tecnico) for r in load_rules(path)]
