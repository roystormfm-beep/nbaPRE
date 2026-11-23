"""Elo con margine di vittoria (schema reso noto da FiveThirtyEight per l'NBA).

- Ogni squadra parte da 1500; tra una stagione e l'altra il rating torna in parte verso la media (carry).
- Aggiornamento dopo ogni partita: K × moltiplicatore del margine × (risultato − atteso).
  Il moltiplicatore cresce con lo scarto ma meno se vince la favorita (evita di gonfiare le squadre forti).
- Vantaggio del campo in punti Elo (zero sui campi neutri). Scarto atteso in punti = differenza Elo / 28.
I pronostici di un giorno si calcolano tutti prima di aggiornare i rating con i risultati di quel giorno.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import TEAMS, path

DEFAULTS = dict(k=20.0, hca=100.0, carry=0.75, mean=1505.0, per_point=28.0)


def games(seasons: list[int]) -> pd.DataFrame:
    parts = []
    for s in seasons:
        g = pd.read_parquet(path("processed") / f"games_{s}.parquet").dropna(subset=["date", "hpts"])
        g["season"] = s
        parts.append(g)
    g = pd.concat(parts, ignore_index=True)
    g["neutral"] = g.get("neutral", pd.Series(False, index=g.index)).fillna(False).astype(bool)
    return g.sort_values(["date", "game_id"]).reset_index(drop=True)


def run(g: pd.DataFrame, P: dict | None = None) -> pd.DataFrame:
    P = {**DEFAULTS, **(P or {})}
    R = {t: 1500.0 for t in TEAMS}
    season = None
    out = []
    for d, day in g.groupby("date", sort=True):
        s = int(day["season"].iloc[0])
        if season is not None and s != season:
            R = {t: P["carry"] * r + (1 - P["carry"]) * P["mean"] for t, r in R.items()}
        season = s
        rows = []
        for r in day.itertuples():
            hca = 0.0 if r.neutral else P["hca"]
            diff = R[r.home] + hca - R[r.away]
            rows.append((r, diff))
            out.append({"game_id": r.game_id, "season": s, "elo_home": R[r.home], "elo_away": R[r.away],
                        "elo_diff": diff, "margin_elo": diff / P["per_point"],
                        "p_elo": 1 / (1 + 10 ** (-diff / 400))})
        for r, diff in rows:
            exp_h = 1 / (1 + 10 ** (-diff / 400))
            mov = r.hpts - r.apts
            res = 1.0 if mov > 0 else 0.0
            win_diff = diff if mov > 0 else -diff
            mult = (abs(mov) + 3) ** 0.8 / (7.5 + 0.006 * win_diff)
            delta = P["k"] * mult * (res - exp_h)
            R[r.home] += delta
            R[r.away] -= delta
    return pd.DataFrame(out)
