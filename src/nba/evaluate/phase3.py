"""Valutazione della fase 3 sulle stagioni di sviluppo con injury report (2018-19 → 2024-25).

Confronto ad armi pari, sulle stesse partite:
  - baseline (ritarato) con le assenze dall'injury report pre-partita;
  - modello giocatori: RAPM + minuti proiettati con l'injury report;
  - miscela 50/50 dei due (anticipo dell'ensemble della fase 5);
  - mercato (linea di chiusura).
Le probabilità di giocare per stato dell'injury report si stimano solo sulle stagioni precedenti.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nba.config import path
from nba.features.availability import label_participation, pregame_reports
from nba.features.minutes import STATUS_P, project_season
from nba.evaluate.player_model import predict_season

SEASONS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]


def status_probs(prior_seasons: list[int]) -> dict:
    parts = []
    for s in prior_seasons:
        r = pregame_reports(s)
        if len(r):
            parts.append(label_participation(r, s))
    if not parts:
        return dict(STATUS_P)
    x = pd.concat(parts)
    x["st"] = x["status"].str.lower()
    rates = x.groupby("st")["played"].agg(["mean", "size"])
    out = dict(STATUS_P)
    for st, row in rates.iterrows():
        if st in out and row["size"] >= 30:
            out[st] = float(row["mean"])
    return out


def run_season(season: int) -> pd.DataFrame:
    rep = pregame_reports(season)
    sp = status_probs([s for s in SEASONS if s < season])
    mins = project_season(season, injuries=rep if len(rep) else None, status_p=sp)
    mins.to_parquet(path("processed") / f"minutes_proj_report_{season}.parquet", index=False)
    pm = predict_season(season, minutes=mins[["game_id", "team", "player", "min"]])
    pm["status_probs"] = json.dumps(sp)
    pm["report_games"] = rep["game_id"].nunique()
    return pm


def run(seasons: list[int] | None = None, workers: int = 2) -> pd.DataFrame:
    from concurrent.futures import ProcessPoolExecutor
    seasons = seasons or SEASONS
    with ProcessPoolExecutor(max_workers=workers) as ex:
        parts = list(ex.map(run_season, seasons))
    out = pd.concat(parts, ignore_index=True)
    out.to_parquet(path("processed") / "player_model_report_predictions.parquet", index=False)
    return out
