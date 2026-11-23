"""Disponibilità dei giocatori prima della partita, dagli injury report ufficiali.

Per ogni partita si usa l'ultimo report pubblicato almeno 45 minuti prima della palla a due (scelto in fase di
scaricamento: data/external/injury/needed_S.csv). Dal report si prendono le righe della partita (matchup
"AWAY@HOME") e della squadra.
"""
from __future__ import annotations

import pandas as pd

from nba.config import path, team as norm_team
from nba.ingest.injury_pdf import name_key


def pregame_reports(season: int) -> pd.DataFrame:
    """Righe dell'injury report pre-partita: game_id, team, player_name, status, reason, report_ts."""
    d = path("external") / "injury"
    rp, nd = d / f"reports_{season}.parquet", d / f"needed_{season}.csv"
    if not rp.exists() or not nd.exists():
        return pd.DataFrame(columns=["game_id", "team", "player_name", "status", "reason", "report_ts"])
    rep = pd.read_parquet(rp)
    if rep.empty or "team" not in rep.columns:
        return pd.DataFrame(columns=["game_id", "team", "player_name", "status", "reason", "report_ts"])
    need = pd.read_csv(nd, dtype={"game_id": str})
    need["game_id"] = need["game_id"].str.zfill(10)
    rep = rep.dropna(subset=["team"])
    mt = rep["matchup"].fillna("").str.extract(r"([A-Z]{2,3})@([A-Z]{2,3})")
    rep = rep.assign(m_away=mt[0].map(norm_team), m_home=mt[1].map(norm_team))
    x = need.merge(rep, on="url", how="inner")
    gd = pd.to_datetime(x["game_date"], format="%m/%d/%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    x = x[(x["m_away"] == x["away"]) & (x["m_home"] == x["home"]) & ((gd == x["date"]) | gd.isna())]
    x = x[(x["team"] == x["home"]) | (x["team"] == x["away"])]
    x["status"] = x["status"].fillna("").str.strip()
    return x[["game_id", "team", "player_name", "status", "reason", "report_ts"]].drop_duplicates(["game_id", "team", "player_name"])


def label_participation(rep: pd.DataFrame, season: int) -> pd.DataFrame:
    """Aggiunge a ogni riga del report se il giocatore è poi sceso in campo e quanti minuti ha giocato."""
    pg = pd.read_parquet(path("processed") / f"player_games_{season}.parquet", columns=["game_id", "team", "player", "name", "sec"])
    pg["key"] = pg["name"].map(name_key)
    played = pg[pg["sec"] > 0].set_index(["game_id", "team", "key"])["sec"]
    rep = rep.copy()
    rep["key"] = rep["player_name"].map(name_key)
    idx = list(zip(rep["game_id"], rep["team"], rep["key"]))
    rep["sec"] = [played.get(i, 0.0) for i in idx]
    rep["played"] = rep["sec"] > 0
    return rep


def status_rates(seasons: list[int]) -> pd.DataFrame:
    """Quota di giocatori scesi in campo per stato dell'injury report (solo stagioni indicate)."""
    parts = []
    for s in seasons:
        r = pregame_reports(s)
        if len(r):
            parts.append(label_participation(r, s).assign(season=s))
    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts)
    x["st"] = x["status"].str.lower()
    return x.groupby("st").agg(righe=("played", "size"), quota_in_campo=("played", "mean"),
                               minuti_se_in_campo=("sec", lambda v: (v[v > 0] / 60).mean())).sort_values("righe", ascending=False)
