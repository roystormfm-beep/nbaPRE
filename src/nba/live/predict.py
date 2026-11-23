"""Pronostici del giorno per la stagione in corso, con lo stesso modello valutato nelle fasi 3-5.

Passi: minuti proiettati (injury report più recente) → modello giocatori con i rating stimati al giorno stesso →
baseline con injury report → contesto, rating di squadra, Elo, LightGBM → ensemble → distribuzione dello scarto.
Per le partite già concluse della stagione si ottengono, con le stesse regole, i pronostici "ricostruiti".
Uscite: predictions/AAAA-MM-GG.json, predictions/latest.json, predictions/registro_{S}.csv,
predictions/ricostruiti_{S}.csv (vedi nba.live.publish).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nba.config import path
from nba.features.minutes import MinutesProjector, project_season
from nba.ingest.injury_pdf import name_key

LABEL_ST = {"out": "out", "doubtful": "molto in dubbio", "questionable": "in dubbio", "probable": "probabile"}


def today_ny() -> str:
    return pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")


def _strength(m: pd.DataFrame, net: dict, default: float) -> float:
    """Forza di una squadra per 100 possessi: rating dei giocatori pesati per i minuti, riportati a 5 in campo."""
    if m is None or m.empty:
        return 0.0
    w = m["min"].to_numpy(float) / 48.0
    v = m["player"].map(net).fillna(default).to_numpy(float)
    return float((v * w).sum() * 5 / max(w.sum(), 1e-9))


def run(season: int = 2026, date: str | None = None) -> str:
    from nba.evaluate import backtest_baseline as BB
    from nba.evaluate import components
    from nba.evaluate.phase3 import status_probs
    from nba.evaluate.phase5 import final
    from nba.evaluate.player_model import predict_season
    from nba.features import context
    from nba.features.availability import pregame_reports
    from nba.live import publish
    from nba.models import rapm as R

    D = date or today_ny()
    proc = path("processed")
    g = pd.read_parquet(proc / f"games_{season}.parquet")
    todays = g[g["date"] == D]
    if todays.empty:
        return f"{D}: nessuna partita in calendario"

    # 1. minuti proiettati con l'injury report e modello giocatori (rating stimati al giorno D)
    sp = status_probs(list(range(2018, season)))
    rep = pregame_reports(season)
    mins = project_season(season, injuries=rep if len(rep) else None, status_p=sp, max_date=D)
    mins.to_parquet(proc / f"minutes_proj_report_{season}.parquet", index=False)
    pm = predict_season(season, minutes=mins[["game_id", "team", "player", "min"]], max_date=D, extra_cutoffs=[D],
                        include_unplayed=True)
    pm.to_parquet(proc / f"player_model_report_live_{season}.parquet", index=False)
    fit = predict_season.fits[pd.Timestamp(D)]

    # 2. baseline della pagina (ritarato) con l'injury report
    opts = json.load(open(proc / "baseline_retuned_params.json"))
    b = BB.run_season(season, opts, with_reports=True, include_unplayed=True, max_date=D)
    b.to_parquet(proc / f"baseline_report_live_{season}.parquet", index=False)

    # 3. contesto, componenti, ensemble e distribuzione
    context.build(list(range(2014, season + 1))).to_parquet(proc / "context.parquet", index=False)
    components.build(max_season=season)
    x = final(season)

    # 4. scomposizione del pronostico e assenze, solo per le partite del giorno
    P = {**R.DEFAULTS}
    default_net = P["rookie_o"] + P["rookie_d"]
    net = dict(zip(fit.players.tolist(), (fit.O + fit.D).tolist()))
    pg = pd.read_parquet(proc / f"player_games_{season}.parquet")
    mp = MinutesProjector(pg, g.dropna(subset=["date"]), None, sp)
    names = pg.drop_duplicates("player", keep="last").set_index("player")["name"].to_dict()
    inj = {k: v for k, v in rep.groupby(["game_id", "team"])} if len(rep) else {}
    ctx = pd.read_parquet(proc / "context.parquet")
    played = g.dropna(subset=["hpts"])
    gp = pd.concat([played["home"], played["away"]]).value_counts().to_dict()
    detail = {}
    for r in todays.itertuples():
        row = pm[pm["game_id"] == r.game_id]
        if row.empty:
            continue
        row = row.iloc[0]
        k = fit.pace / 100
        info = {"k": k, "hca": float(row["hca"]) * k, "team_adj": float(row["team_adj"]) * k}
        for side, t in (("h", r.home), ("a", r.away)):
            rep_t = inj.get((r.game_id, t))
            m_rep = mp.project(r.game_id, t, D, rep_t)
            m_no = mp.project(r.game_id, t, D, None)
            s_rep, s_no = _strength(m_rep, net, default_net), _strength(m_no, net, default_net)
            info[f"{side}_str_no"] = s_no * k
            info[f"{side}_abs"] = (s_rep - s_no) * k
            outs = []
            listed = m_rep[m_rep["listed"].astype(str).str.lower().isin(["out", "doubtful", "questionable"])]
            for p in listed.itertuples():
                if p.base < 8:
                    continue
                # effetto del solo giocatore: si applica il suo stato e si lasciano gli altri come senza report
                key = mp.key.get(p.player, "")
                sub = rep_t[rep_t["player_name"].map(name_key) == key]
                s_i = _strength(mp.project(r.game_id, t, D, sub), net, default_net)
                outs.append((names.get(p.player, str(p.player)), str(p.listed).lower(), (s_i - s_no) * k, p.base))
            outs.sort(key=lambda o: o[2])
            info[f"{side}_outs"] = outs
            info[f"{side}_quest"] = any(o[1] in ("questionable", "doubtful") and o[3] >= 20 for o in outs)
            info[f"{side}_gp"] = int(gp.get(t, 0))
            rt = rep_t["report_ts"].iloc[0] if rep_t is not None and len(rep_t) else None
            info["report_ts"] = rt or info.get("report_ts")
        c = ctx[ctx["game_id"] == r.game_id]
        info["ctx"] = c.iloc[0].to_dict() if len(c) else {}
        detail[r.game_id] = info
    return publish.write(season, D, x, detail)
