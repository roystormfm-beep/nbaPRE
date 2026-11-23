"""Lettura della configurazione e percorsi del progetto."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def cfg() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def path(key: str) -> Path:
    p = ROOT / cfg()["paths"][key]
    p.mkdir(parents=True, exist_ok=True)
    return p


def all_seasons() -> list[int]:
    s = cfg()["seasons"]
    return sorted(set(s["dev"]) | set(s["test"]))


def season_label(y: int) -> str:
    """2025 -> '2025-26'."""
    return f"{y}-{str(y + 1)[-2:]}"


# Codici squadra usati in tutto il progetto (gli stessi della pagina)
TEAMS = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM",
         "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]
TEAM_ALIAS = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX", "NO": "NOP", "NOH": "NOP", "NY": "NYK", "SA": "SAS",
              "GS": "GSW", "UTAH": "UTA", "WSH": "WAS", "NJN": "BKN", "SEA": "OKC", "CHH": "CHA"}


def team(code: str) -> str:
    c = str(code or "").strip().upper()
    return TEAM_ALIAS.get(c, c)
