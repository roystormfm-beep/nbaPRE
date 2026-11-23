"""Fase 5: pronostico finale (ensemble + distribuzione dello scarto), con le scelte fissate in config.yaml.

`final(max_season)` costruisce i pronostici di tutte le stagioni fino a max_season. Tutto è walk-forward:
i pronostici di una stagione non cambiano aggiungendo stagioni successive.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import cfg, path
from nba.models import distribution as D
from nba.models import ensemble as EN


def final(max_season: int) -> pd.DataFrame:
    E, Dc = cfg()["models"]["ensemble"], cfg()["models"]["distribution"]
    c = pd.read_parquet(path("processed") / "components.parquet")
    c = c[c["season"] <= max_season].reset_index(drop=True)
    seasons = list(range(E["first_season"], max_season + 1))
    pm = EN.fit_predict(c, E["margin_components"], "margin", seasons,
                        {"hl_seasons": E["hl_seasons"], "report_only": E["report_only"]})
    weights = dict(EN.fit_predict.last_weights)
    if len(E["total_components"]) > 1:
        pt = EN.fit_predict(c, E["total_components"], "total", seasons,
                            {"hl_seasons": E["hl_seasons"], "report_only": E["report_only"]})
        c = c.merge(pt[["game_id", "pred"]].rename(columns={"pred": "t_final"}), on="game_id", how="left")
    else:
        c["t_final"] = c[E["total_components"][0]]
    c = c.merge(pm[["game_id", "pred"]].rename(columns={"pred": "m_ens"}), on="game_id", how="left")
    # prima del 2018-19 non c'è l'ensemble: il modello giocatori serve solo come storico degli errori per la distribuzione
    c["m_final"] = c["m_ens"].where(c["season"] >= E["first_season"], c["m_players"])
    p, s, fits = D.walk_forward(c, "m_final", "t_final", list(range(2016, max_season + 1)), Dc["kind"],
                                Dc["hl_seasons"], Dc["window"])
    c["p_home"], c["sd"] = p, s
    c["hp"] = (c["t_final"] + c["m_final"]) / 2
    c["ap"] = (c["t_final"] - c["m_final"]) / 2
    final.weights, final.fits = weights, fits
    return c[c["season"] >= E["first_season"]].reset_index(drop=True)
