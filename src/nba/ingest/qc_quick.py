"""Controllo rapido di una stagione (usato durante lo sviluppo)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def team_points(pg: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    pts = pg.groupby(["game_id", "team"])["pts"].sum()
    out = g[["game_id", "home", "away"]].copy()
    out["h_ev"] = [pts.get((i, h), np.nan) for i, h in zip(out.game_id, out.home)]
    out["a_ev"] = [pts.get((i, a), np.nan) for i, a in zip(out.game_id, out.away)]
    return out


def minutes_check(pg: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    m = pg.groupby(["game_id", "team"])["sec"].sum().rename("sec").reset_index()
    per = g.set_index("game_id")["periods"]
    m["exp"] = m["game_id"].map(per).map(lambda p: 5 * (2880 + 300 * max(0, p - 4)))
    m["diff_min"] = (m["sec"] - m["exp"]) / 60.0
    return m
