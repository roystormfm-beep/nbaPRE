"""Valutazione walk-forward del modello "giocatori": RAPM stimato ogni `step` giorni con i soli dati precedenti,
forza di squadra = somma dei rating dei giocatori pesata per i minuti.

Minuti: "veri" (quelli giocati davvero: serve a misurare la qualità dei rating, è ottimistico sulla disponibilità)
oppure una tabella di minuti proiettati (game_id, team, player, min) passata dall'esterno.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from nba.config import path
from nba.features.players import priors
from nba.models import rapm as R


def season_games(season: int) -> pd.DataFrame:
    g = pd.read_parquet(path("processed") / f"games_{season}.parquet")
    g = g.dropna(subset=["date", "hpts"]).copy()
    g["date"] = pd.to_datetime(g["date"])
    return g.sort_values(["date", "game_id"]).reset_index(drop=True)


def actual_minutes(season: int) -> pd.DataFrame:
    pg = pd.read_parquet(path("processed") / f"player_games_{season}.parquet", columns=["game_id", "team", "player", "sec"])
    pg = pg[pg["sec"] > 0]
    return pg.assign(min=pg["sec"] / 60)[["game_id", "team", "player", "min"]]


BOX = [-11.117, 1.042, 0.384, 0.877, 1.493, 1.098, -1.649, -0.859, -0.384, 0.474]   # regressione BPM del baseline


def season_box(season: int) -> pd.DataFrame:
    pg = pd.read_parquet(path("processed") / f"player_games_{season}.parquet")
    g = pd.read_parquet(path("processed") / f"games_{season}.parquet", columns=["game_id", "date"])
    pg = pg[pg["sec"] > 0].merge(g, on="game_id")
    pg["date"] = pd.to_datetime(pg["date"])
    pg["trb"] = pg["oreb"] + pg["dreb"]
    return pg


def box_priors(pg: pd.DataFrame, cutoff: pd.Timestamp, base: dict, P: dict) -> dict:
    """Aggiorna il prior di ogni giocatore con il box score della stagione in corso (partite prima di cutoff):
    stima del BPM dai dati per 36 minuti, pesata per i minuti giocati contro il peso del prior precedente."""
    if not P.get("box_w"):
        return base
    sub = pg[pg["date"] < cutoff]
    if sub.empty:
        return base
    a = sub.groupby("player")[["sec", "pts", "trb", "ast", "stl", "blk", "tov", "fga", "fta", "fg3m"]].sum()
    mins = a["sec"] / 60
    f = 36 / mins.clip(lower=1)
    bpm = (BOX[0] + BOX[1] * a["pts"] * f + BOX[2] * a["trb"] * f + BOX[3] * a["ast"] * f + BOX[4] * a["stl"] * f
           + BOX[5] * a["blk"] * f + BOX[6] * a["tov"] * f + BOX[7] * a["fga"] * f + BOX[8] * a["fta"] * f
           + BOX[9] * a["fg3m"] * f) * P["prior_scale"]
    out = dict(base)
    W = P["box_w"]
    for pid, m, b in zip(a.index, mins, bpm):
        o0, d0 = base.get(int(pid), (P["rookie_o"], P["rookie_d"]))
        tot0 = o0 + d0
        tot = (tot0 * W + b * m) / (W + m)
        out[int(pid)] = (o0 + (tot - tot0) / 2, d0 + (tot - tot0) / 2)
    return out


def cutoffs(dates: pd.Series, step: int) -> list[pd.Timestamp]:
    d0, d1 = dates.min(), dates.max()
    out, c = [], d0
    while c <= d1:
        out.append(c)
        c += pd.Timedelta(days=step)
    return out


def team_residuals(past: pd.DataFrame, cutoff: pd.Timestamp, lam: float, hl: float) -> dict:
    """Correzione di squadra: ridge sugli scarti non spiegati dai giocatori nelle partite passate (più peso alle
    recenti). past: game_id, date, home, away, resid."""
    if past.empty or not lam:
        return {}
    teams = sorted(set(past["home"]) | set(past["away"]))
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    w = 0.5 ** ((cutoff - past["date"]).dt.days.to_numpy() / hl)
    A = np.eye(n) * lam
    b = np.zeros(n)
    for (h, a, r, ww) in zip(past["home"], past["away"], past["resid"], w):
        i, j = ix[h], ix[a]
        A[i, i] += ww; A[j, j] += ww; A[i, j] -= ww; A[j, i] -= ww
        b[i] += ww * r; b[j] -= ww * r
    x = np.linalg.solve(A, b)
    return {t: float(x[ix[t]]) for t in teams}


def predict_season(season: int, P: dict | None = None, step: int = 7, minutes: pd.DataFrame | None = None) -> pd.DataFrame:
    P = {**R.DEFAULTS, "res_lam": 0.0, "res_hl": 45.0, **(P or {})}
    g = season_games(season)
    act = actual_minutes(season)
    mins = act if minutes is None else minutes
    st = R.load_stints([s for s in range(season - 2, season + 1) if s >= 2014])
    pr = priors(season, P)
    pgb = season_box(season) if P.get("box_w") else None
    cuts = cutoffs(g["date"], step)
    rows = []
    for i, c in enumerate(cuts):
        nxt = cuts[i + 1] if i + 1 < len(cuts) else c + pd.Timedelta(days=step)
        gg = g[(g["date"] >= c) & (g["date"] < nxt)]
        if gg.empty:
            continue
        f = R.fit(st, c, box_priors(pgb, c, pr, P) if pgb is not None else pr, P, season)
        net = dict(zip(f.players.tolist(), (f.O + f.D).tolist()))
        oo = dict(zip(f.players.tolist(), f.O.tolist()))
        dd = dict(zip(f.players.tolist(), f.D.tolist()))
        default_net = P["rookie_o"] + P["rookie_d"]
        res = {}
        if P["res_lam"]:
            gp = g[(g["date"] < c)]
            if len(gp):
                ma = act[act["game_id"].isin(gp["game_id"])].copy()
                ma["nw"] = ma["player"].map(net).fillna(default_net) * ma["min"] / 48
                ma["w"] = ma["min"] / 48
                ag = ma.groupby(["game_id", "team"])[["nw", "w"]].sum()
                pr_ = []
                for r in gp.itertuples():
                    try:
                        hh, aa = ag.loc[(r.game_id, r.home)], ag.loc[(r.game_id, r.away)]
                    except KeyError:
                        continue
                    pm = (f.h + hh["nw"] * 5 / hh["w"] - aa["nw"] * 5 / aa["w"]) * f.pace / 100
                    pr_.append((r.date, r.home, r.away, (r.hpts - r.apts) - pm))
                past = pd.DataFrame(pr_, columns=["date", "home", "away", "resid"])
                res = team_residuals(past, c, P["res_lam"], P["res_hl"])
        m = mins[mins["game_id"].isin(gg["game_id"])].copy()
        m["net"] = m["player"].map(net).fillna(default_net)
        m["O"] = m["player"].map(oo).fillna(P["rookie_o"])
        m["D"] = m["player"].map(dd).fillna(P["rookie_d"])
        m["w"] = m["min"] / 48.0
        agg = m.assign(nw=m["net"] * m["w"], ow=m["O"] * m["w"], dw=m["D"] * m["w"]).groupby(["game_id", "team"])[["nw", "ow", "dw", "w"]].sum()
        for r in gg.itertuples():
            try:
                hh, aa = agg.loc[(r.game_id, r.home)], agg.loc[(r.game_id, r.away)]
            except KeyError:
                continue
            # i minuti totali possono superare 240 (supplementari): normalizzo a 5 giocatori in campo
            hs, as_ = 5 / max(hh["w"], 1e-9), 5 / max(aa["w"], 1e-9)
            th = f.team_o.get(r.home, 0) + f.team_d.get(r.home, 0)
            ta = f.team_o.get(r.away, 0) + f.team_d.get(r.away, 0)
            neutral = bool(getattr(r, "neutral", False)) if pd.notna(getattr(r, "neutral", np.nan)) else False
            h = 0.0 if neutral else f.h
            per100 = h + hh["nw"] * hs - aa["nw"] * as_ + th - ta
            k = f.pace / 100
            corr = res.get(r.home, 0.0) - res.get(r.away, 0.0)
            hp = (f.mu + h / 2 + hh["ow"] * hs - aa["dw"] * as_ + f.team_o.get(r.home, 0) - f.team_d.get(r.away, 0)) * k
            ap = (f.mu - h / 2 + aa["ow"] * as_ - hh["dw"] * hs + f.team_o.get(r.away, 0) - f.team_d.get(r.home, 0)) * k
            rows.append({"game_id": r.game_id, "season": season, "date": r.date.strftime("%Y-%m-%d"), "home": r.home,
                         "away": r.away, "margin_pred": per100 * k + corr, "total_pred": hp + ap, "hpts": r.hpts, "apts": r.apts,
                         "cutoff": c.strftime("%Y-%m-%d")})
    return pd.DataFrame(rows)


def _one(args):
    s, P, step = args
    return predict_season(s, P, step)


def run(seasons: list[int], P: dict | None = None, step: int = 7, workers: int = 2) -> pd.DataFrame:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        parts = list(ex.map(_one, [(s, P, step) for s in seasons]))
    return pd.concat(parts, ignore_index=True)
