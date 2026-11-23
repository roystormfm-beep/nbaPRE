"""Tabella delle partite: squadre di casa e trasferta, data (USA), punteggi finali dalle diverse fonti."""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import team as norm_team
from nba.ingest.events import _gid
from nba.ingest.pbp_download import raw_file


def _last_score(df: pd.DataFrame, gcol: str, ocol: str, hcol: str, acol: str) -> pd.DataFrame:
    x = df[[gcol, ocol, hcol, acol]].copy()
    x[hcol] = pd.to_numeric(x[hcol], errors="coerce")
    x[acol] = pd.to_numeric(x[acol], errors="coerce")
    x[ocol] = pd.to_numeric(x[ocol], errors="coerce")
    # il punteggio non diminuisce mai: il finale è il massimo (l'ultima riga può essere un evento fuori sequenza)
    last = x.dropna(subset=[hcol, acol]).groupby(gcol)[[hcol, acol]].max().reset_index()
    return pd.DataFrame({"game_id": _gid(last[gcol]).to_numpy(), "h": last[hcol].astype(int).to_numpy(),
                         "a": last[acol].astype(int).to_numpy()})


def build_games(season: int) -> pd.DataFrame:
    v3 = pd.read_parquet(raw_file("nbastatsv3", season),
                         columns=["gameId", "actionNumber", "location", "teamTricode", "scoreHome", "scoreAway", "period"])
    v3["game_id"] = _gid(v3["gameId"])
    loc = v3.dropna(subset=["location", "teamTricode"])
    loc = loc[loc["location"].isin(["h", "v"])]
    sides = (loc.groupby(["game_id", "location"])["teamTricode"].agg(lambda s: s.mode().iat[0]).unstack())
    g = pd.DataFrame({"game_id": sides.index, "home": sides["h"].map(norm_team).to_numpy(),
                      "away": sides["v"].map(norm_team).to_numpy()})
    g["season"] = season
    g["periods"] = g["game_id"].map(v3.groupby("game_id")["period"].max()).astype(int)
    s3 = _last_score(v3, "gameId", "actionNumber", "scoreHome", "scoreAway").rename(columns={"h": "h_v3", "a": "a_v3"})
    g = g.merge(s3, on="game_id", how="left")

    # NBA Stats v2: SCORE = "trasferta - casa"
    p2 = raw_file("nbastats", season)
    if p2.exists():
        v2 = pd.read_parquet(p2, columns=["GAME_ID", "EVENTNUM", "SCORE"]).dropna(subset=["SCORE"])
        sc = v2["SCORE"].str.extract(r"(\d+)\s*-\s*(\d+)")
        v2 = v2.assign(sa=sc[0], sh=sc[1])
        s2 = _last_score(v2, "GAME_ID", "EVENTNUM", "sh", "sa").rename(columns={"h": "h_v2", "a": "a_v2"})
        g = g.merge(s2, on="game_id", how="left")
    # cdn.nba.com: punteggio e orario reale delle azioni
    pc = raw_file("cdnnba", season)
    if pc.exists():
        c = pd.read_parquet(pc, columns=["gameId", "orderNumber", "scoreHome", "scoreAway", "timeActual"])
        sc = _last_score(c, "gameId", "orderNumber", "scoreHome", "scoreAway").rename(columns={"h": "h_cdn", "a": "a_cdn"})
        g = g.merge(sc, on="game_id", how="left")
        t = c.dropna(subset=["timeActual"]).copy()
        t["game_id"] = _gid(t["gameId"])
        t["ts"] = pd.to_datetime(t["timeActual"], utc=True, errors="coerce")
        first = t.groupby("game_id")["ts"].min()
        g["tip_utc"] = g["game_id"].map(first)
    # pbpstats: data della partita
    pp = raw_file("pbpstats", season)
    if pp.exists():
        p = pd.read_parquet(pp, columns=["GAMEID", "GAMEDATE"]).dropna().drop_duplicates("GAMEID")
        g["date_pbp"] = g["game_id"].map(dict(zip(_gid(p["GAMEID"]), p["GAMEDATE"])))
    if "tip_utc" in g:
        g["date_cdn"] = g["tip_utc"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    g["date"] = g.get("date_pbp", pd.Series(index=g.index, dtype=object))
    if "date_cdn" in g:
        g["date"] = g["date"].fillna(g["date_cdn"])
    return g.sort_values("game_id").reset_index(drop=True)
