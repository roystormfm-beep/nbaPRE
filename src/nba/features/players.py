"""Anagrafica giocatori (id ↔ nome) e prior per giocatore dalla stagione precedente."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from nba.config import path
from nba.models.baseline import norm_name
from nba.models.rapm import prev_box_prior


@lru_cache(maxsize=None)
def names(season: int) -> pd.DataFrame:
    pg = pd.read_parquet(path("processed") / f"player_games_{season}.parquet", columns=["player", "name"]).dropna()
    pg = pg.drop_duplicates("player")
    pg["name_key"] = pg["name"].map(norm_name)
    return pg


def priors(season: int, P: dict) -> dict[int, tuple[float, float]]:
    """Prior (O, D) per 100 possessi: BPM offensivo/difensivo della stagione precedente, riportato verso il
    valore dei giocatori senza storia in proporzione ai minuti giocati, e moltiplicato per prior_scale."""
    b = prev_box_prior(season)
    nm = names(season)
    if season - 1 >= 2014:
        nm = pd.concat([nm, names(season - 1)]).drop_duplicates("player")
    m = nm.merge(b, on="name_key", how="inner")
    k = P["prior_shrink_min"]
    o = (m["obpm"] * m["mp"] + P["rookie_o"] / P["prior_scale"] * k) / (m["mp"] + k) * P["prior_scale"]
    d = (m["dbpm"] * m["mp"] + P["rookie_d"] / P["prior_scale"] * k) / (m["mp"] + k) * P["prior_scale"]
    return {int(p): (float(a), float(c)) for p, a, c in zip(m["player"], o, d)}
