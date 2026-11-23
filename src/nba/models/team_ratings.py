"""Ritmo ed efficienza di squadra, stimati giorno per giorno con le sole partite precedenti.

Per ogni partita giocata:
  possessi della partita      = ritmo_lega + ritmo(casa) + ritmo(trasferta)
  punti per 100 possessi casa = media_lega + h/2 + attacco(casa) - difesa(trasferta)
  punti per 100 possessi ospiti = media_lega - h/2 + attacco(trasferta) - difesa(casa)
Regressioni ridge pesate per quanto è recente la partita (emivita in giorni). La media della lega usa
un'emivita più corta, così segue l'aumento dei punti nel corso degli anni e delle stagioni.
Possessi di squadra = tiri tentati - rimbalzi offensivi + palle perse + 0,44 × tiri liberi tentati (dal box score).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import TEAMS, path

DEFAULTS = dict(hl_team=60.0, hl_league=30.0, lam_eff=15.0, lam_pace=15.0, lam_h=50.0, window_days=500)
TIX = {t: i for i, t in enumerate(TEAMS)}


def game_table(seasons: list[int]) -> pd.DataFrame:
    parts = []
    for s in seasons:
        g = pd.read_parquet(path("processed") / f"games_{s}.parquet").dropna(subset=["date", "hpts"])
        pg = pd.read_parquet(path("processed") / f"player_games_{s}.parquet",
                             columns=["game_id", "team", "fga", "oreb", "tov", "fta"])
        t = pg.groupby(["game_id", "team"])[["fga", "oreb", "tov", "fta"]].sum()
        t["poss"] = t["fga"] - t["oreb"] + t["tov"] + 0.44 * t["fta"]
        gp = t["poss"].groupby(level=0).mean().rename("poss")
        g = g.merge(gp, left_on="game_id", right_index=True, how="left")
        g["season"] = s
        parts.append(g)
    g = pd.concat(parts, ignore_index=True)
    g["date"] = pd.to_datetime(g["date"])
    g["neutral"] = g.get("neutral", pd.Series(False, index=g.index)).fillna(False).astype(bool)
    per = g["periods"].fillna(4).clip(lower=4)
    g["poss48"] = g["poss"] * 48 / (48 + 5 * (per - 4))           # possessi riportati a 48 minuti
    return g.sort_values(["date", "game_id"]).reset_index(drop=True)


def _ridge(X, y, w, lam):
    A = (X.T * w) @ X + np.diag(lam)
    return np.linalg.solve(A, (X.T * w) @ y)


def fit(g: pd.DataFrame, cutoff: pd.Timestamp, P: dict) -> dict:
    d = g[(g["date"] < cutoff) & (g["date"] >= cutoff - pd.Timedelta(days=P["window_days"]))].dropna(subset=["poss48"])
    if d.empty:
        return {}
    age = (cutoff - d["date"]).dt.days.to_numpy(float)
    w_t = 0.5 ** (age / P["hl_team"])
    w_l = 0.5 ** (age / P["hl_league"])
    lg_pace = float(np.average(d["poss48"], weights=w_l))
    pts = np.r_[d["hpts"], d["apts"]] * 100 / np.r_[d["poss"], d["poss"]]
    lg_eff = float(np.average(pts, weights=np.r_[w_l, w_l]))
    n = len(d)
    hi = d["home"].map(TIX).to_numpy()
    ai = d["away"].map(TIX).to_numpy()
    neutral = d["neutral"].to_numpy()
    # ritmo: poss48 - lega = p(casa) + p(trasferta)
    Xp = np.zeros((n, 30))
    Xp[np.arange(n), hi] = 1
    Xp[np.arange(n), ai] += 1
    pace = _ridge(Xp, d["poss48"].to_numpy() - lg_pace, w_t, np.full(30, P["lam_pace"]))
    # efficienza: due osservazioni per partita; colonne attacco[30], difesa[30], h
    X = np.zeros((2 * n, 61))
    r = np.arange(n)
    X[r, hi] = 1
    X[r, 30 + ai] = -1
    X[r, 60] = np.where(neutral, 0, 0.5)
    X[n + r, ai] = 1
    X[n + r, 30 + hi] = -1
    X[n + r, 60] = np.where(neutral, 0, -0.5)
    lam = np.r_[np.full(60, P["lam_eff"]), P["lam_h"]]
    beta = _ridge(X, pts - lg_eff, np.r_[w_t, w_t], lam)
    return {"lg_pace": lg_pace, "lg_eff": lg_eff, "pace": pace, "O": beta[:30], "D": beta[30:60], "h": beta[60]}


def predict_games(g: pd.DataFrame, seasons: list[int], P: dict | None = None) -> pd.DataFrame:
    P = {**DEFAULTS, **(P or {})}
    rows = []
    for s in seasons:
        gs = g[g["season"] == s]
        for d, day in gs.groupby("date"):
            f = fit(g, d, P)
            if not f:
                continue
            for r in day.itertuples():
                h, a = TIX[r.home], TIX[r.away]
                hh = 0.0 if r.neutral else f["h"] / 2
                pace = f["lg_pace"] + f["pace"][h] + f["pace"][a]
                he = f["lg_eff"] + hh + f["O"][h] - f["D"][a]
                ae = f["lg_eff"] - hh + f["O"][a] - f["D"][h]
                rows.append({"game_id": r.game_id, "season": s, "pace_pred": pace, "eff_home": he, "eff_away": ae,
                             "lg_eff": f["lg_eff"], "lg_pace": f["lg_pace"],
                             "total_team": pace * (he + ae) / 100, "margin_team": pace * (he - ae) / 100})
    return pd.DataFrame(rows)
