"""Variabili di contesto per ogni partita, tutte note prima della palla a due.

Calendario (dalla fase 1): giorni di riposo, back-to-back, 3 partite in 4 notti, partite negli ultimi 7 giorni,
chilometri dalla partita precedente, fusi orari attraversati, campo neutro.
Altura: partita in casa di Denver o Utah.
Fine stagione: squadre con poche vittorie nelle ultime settimane (spesso senza obiettivi) e squadre già sicure
del loro piazzamento negli ultimi giorni; record calcolato solo con le partite precedenti.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import path


def team_records(g: pd.DataFrame) -> pd.DataFrame:
    """Vittorie e sconfitte di ogni squadra prima di ogni partita (stessa stagione)."""
    rows = []
    for side, opp in (("home", "away"), ("away", "home")):
        w = (g["hpts"] > g["apts"]) if side == "home" else (g["apts"] > g["hpts"])
        rows.append(pd.DataFrame({"game_id": g["game_id"], "season": g["season"], "date": g["date"], "team": g[side],
                                  "win": w.astype(int)}))
    t = pd.concat(rows).sort_values(["team", "season", "date", "game_id"])
    grp = t.groupby(["team", "season"])
    t["w_before"] = grp["win"].cumsum() - t["win"]
    t["g_before"] = grp.cumcount()
    t["wpct"] = np.where(t["g_before"] > 0, t["w_before"] / t["g_before"].clip(lower=1), 0.5)
    return t[["game_id", "team", "wpct", "g_before"]]


def build(seasons: list[int]) -> pd.DataFrame:
    sc = pd.read_parquet(path("processed") / "schedule.parquet")
    sc = sc[sc["season"].isin(seasons)].copy()
    sc["d"] = pd.to_datetime(sc["date"])
    sc = sc.sort_values(["team", "d"])
    sc["games_last7"] = sc.groupby(["season", "team"])["d"].transform(
        lambda x: x.apply(lambda d: ((x < d) & (x >= d - pd.Timedelta(days=7))).sum()))
    games = pd.concat([pd.read_parquet(path("processed") / f"games_{s}.parquet").assign(season=s) for s in seasons])
    games = games.dropna(subset=["date", "hpts"])
    rec = team_records(games)
    sc = sc.merge(rec, on=["game_id", "team"], how="left")
    # giorni alla fine della stagione regolare (calendario noto in anticipo)
    end = sc.groupby("season")["d"].max().rename("season_end")
    start = sc.groupby("season")["d"].min().rename("season_start")
    sc = sc.merge(end, on="season").merge(start, on="season")
    sc["days_left"] = (sc["season_end"] - sc["d"]).dt.days
    sc["late_lowwin"] = ((sc["days_left"] <= 35) & (sc["wpct"] < 0.35) & (sc["g_before"] >= 40)).astype(int)
    sc["late_top"] = ((sc["days_left"] <= 7) & (sc["wpct"] > 0.65)).astype(int)
    sc["rest0"] = (sc["rest_days"] == 0).astype(int)
    sc["rest1"] = (sc["rest_days"] == 1).astype(int)
    sc["rest3"] = (sc["rest_days"] >= 3).astype(int)
    sc["trav"] = sc["travel_km"] / 1000
    sc["tz"] = sc["tz_shift_h"].abs()
    sc["tz_east"] = (sc["tz_shift_h"] > 0).astype(int) * sc["tz_shift_h"]     # verso est: partite "prima" per il corpo
    sc["dens"] = sc["games_last7"]
    sc["b2b_road"] = (sc["rest0"] == 1) & (~sc["is_home"])
    keep = ["game_id", "rest0", "rest1", "rest3", "three_in_four", "trav", "tz", "tz_east", "dens", "late_lowwin",
            "late_top", "wpct", "b2b_road"]
    h = sc[sc["is_home"]][keep + ["team", "neutral", "season", "date", "days_left", "season_start"]].rename(
        columns={k: f"h_{k}" for k in keep[1:]} | {"team": "home"})
    a = sc[~sc["is_home"]][keep + ["team"]].rename(columns={k: f"a_{k}" for k in keep[1:]} | {"team": "away"})
    x = h.merge(a, on="game_id")
    x["altitude"] = (x["home"].isin(["DEN", "UTA"]) & ~x["neutral"].astype(bool)).astype(int)
    x["season_frac"] = 1 - x["days_left"] / (x["days_left"] + (pd.to_datetime(x["date"]) - x["season_start"]).dt.days).clip(lower=1)
    for c in ("three_in_four", "b2b_road"):
        x[f"h_{c}"] = x[f"h_{c}"].astype(int)
        x[f"a_{c}"] = x[f"a_{c}"].astype(int)
    return x.drop(columns=["season_start"])


# variabili per lo scarto (casa - trasferta) e per il totale (somma)
DIFF = ["rest0", "rest1", "rest3", "three_in_four", "trav", "tz", "tz_east", "dens", "late_lowwin", "late_top", "b2b_road"]


def design(x: pd.DataFrame, target: str, teams: list[str] | None = None) -> tuple[np.ndarray, list[str]]:
    cols, names = [], []
    not_neutral = (~x["neutral"].astype(bool)).astype(float).to_numpy()
    if target == "margin":
        cols.append(not_neutral)
        names.append("vantaggio_campo")
        for c in DIFF:
            cols.append((x[f"h_{c}"] - x[f"a_{c}"]).to_numpy(float))
            names.append(f"diff_{c}")
        cols.append(x["altitude"].to_numpy(float))
        names.append("altura")
        if teams:
            for t in teams:
                cols.append(((x["home"] == t).astype(float) * not_neutral).to_numpy())
                names.append(f"casa_{t}")
    else:
        cols.append(np.ones(len(x)))
        names.append("costante")
        for c in DIFF:
            cols.append((x[f"h_{c}"] + x[f"a_{c}"]).to_numpy(float))
            names.append(f"somma_{c}")
        cols.append(x["altitude"].to_numpy(float))
        names.append("altura")
        cols.append(x["season_frac"].to_numpy(float))
        names.append("avanzamento_stagione")
    return np.column_stack(cols), names
