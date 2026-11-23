"""Tabelle elaborate della stagione in corso, dagli scaricamenti ESPN e pbpstats (nessuna richiesta di rete qui).

  games_{S}     tutte le partite di stagione regolare, anche future (punteggi vuoti), id = '2' + id ESPN
  stints_{S}    quintetti in campo ricostruiti dal play-by-play ESPN, con gli id NBA dei giocatori
  player_games_{S}, lineup_issues_{S}, lines_{S} come per le stagioni storiche
Traduzione degli id: per ogni partita i giocatori ESPN si abbinano per nome a quelli di pbpstats (id NBA) della
stessa squadra; chi non si trova usa l'abbinamento già visto in altre partite, poi i nomi delle due stagioni
precedenti; altrimenti riceve un id provvisorio (5.000.000.000 + id ESPN).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import path
from nba.ingest.injury_pdf import name_key
from nba.ingest.remote.live import game_id, regular
from nba.ingest.stints import build_season

SYNTH = 5_000_000_000


def _live(name: str, s: int) -> pd.DataFrame:
    f = path("external") / "live" / f"{name}_{s}.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame()


def games_table(s: int) -> pd.DataFrame:
    sb = regular(pd.read_parquet(path("external") / "espn" / f"scoreboard_{s}.parquet"))
    fin = _live("finals", s)
    g = pd.DataFrame({
        "game_id": sb["event_id"].astype(str).map(game_id), "season": s, "date": sb["date_et"],
        "tip_utc": sb["date_utc"], "home": sb["home"], "away": sb["away"],
        "espn_id": sb["event_id"].astype(str), "h_espn": sb["hpts"], "a_espn": sb["apts"], "date_espn": sb["date_et"],
        "tip_utc_espn": sb["date_utc"], "neutral": sb["neutral"].astype(bool), "venue": sb["venue"],
        "venue_city": sb["city"], "venue_country": sb["country"], "completed": sb["completed"].astype(bool)})
    if len(fin):
        f = fin.assign(espn_id=fin["event_id"].astype(str))[["espn_id", "hpts", "apts", "periods"]]
        g = g.merge(f, on="espn_id", how="left")
    else:
        g["hpts"] = g["apts"] = g["periods"] = np.nan
    # punteggio: summary ESPN, altrimenti tabellone; solo per le partite concluse
    g["hpts"] = g["hpts"].fillna(g["h_espn"]).where(g["completed"])
    g["apts"] = g["apts"].fillna(g["a_espn"]).where(g["completed"])
    return g.sort_values(["date", "game_id"]).reset_index(drop=True)


def id_map(s: int) -> pd.DataFrame:
    """espn_id -> id NBA (o provvisorio), con il nome ESPN."""
    bx = _live("box", s)
    pb = _live("pbpstats", s)
    if bx.empty:
        return pd.DataFrame(columns=["espn_id", "player", "name", "how"])
    bx = bx.copy()
    bx["key"] = bx["name"].map(name_key)
    out = {}
    if len(pb):
        pb = pb.copy()
        pb["key"] = pb["name"].map(name_key)
        m = bx.merge(pb[["event_id", "team", "key", "nba_id"]], on=["event_id", "team", "key"], how="inner")
        for e, grp in m.groupby("espn_id"):
            out[int(e)] = (int(grp["nba_id"].mode().iloc[0]), "pbpstats")
        # stessa partita e squadra, abbinamento per cognome quando è unico
        left = bx[~bx["espn_id"].isin(out)]
        if len(left):
            pb["last"] = pb["name"].fillna("").str.split().str[-1].map(name_key)
            left = left.assign(last=left["name"].fillna("").str.split().str[-1].map(name_key))
            mm = left.merge(pb[["event_id", "team", "last", "nba_id"]], on=["event_id", "team", "last"], how="inner")
            cnt = mm.groupby(["event_id", "team", "last"])["nba_id"].transform("nunique")
            for e, grp in mm[cnt == 1].groupby("espn_id"):
                out.setdefault(int(e), (int(grp["nba_id"].mode().iloc[0]), "pbpstats_cognome"))
    # nomi delle due stagioni precedenti (id NBA), quando la chiave è unica
    hist = []
    for y in (s - 1, s - 2):
        f = path("processed") / f"player_games_{y}.parquet"
        if f.exists():
            hist.append(pd.read_parquet(f, columns=["player", "name"]).dropna().drop_duplicates("player"))
    if hist:
        h = pd.concat(hist).drop_duplicates("player")
        h["key"] = h["name"].map(name_key)
        h = h[h["player"] < SYNTH]
        uniq = h.groupby("key")["player"].nunique()
        h = h[h["key"].isin(uniq[uniq == 1].index)].drop_duplicates("key").set_index("key")["player"]
        for e, k in bx.drop_duplicates("espn_id")[["espn_id", "key"]].itertuples(index=False):
            if int(e) not in out and k in h.index:
                out[int(e)] = (int(h[k]), "storico")
    names = bx.drop_duplicates("espn_id", keep="last").set_index("espn_id")["name"]
    rows = []
    for e, nm in names.items():
        pid, how = out.get(int(e), (SYNTH + int(e), "provvisorio"))
        rows.append({"espn_id": int(e), "player": pid, "name": nm, "how": how})
    return pd.DataFrame(rows)


def build(s: int) -> dict:
    proc = path("processed")
    g = games_table(s)
    ev = _live("events", s)
    im = id_map(s)
    info = {"stagione": s, "partite_calendario": len(g), "concluse": int(g["completed"].sum())}
    if len(ev) and len(im):
        mp = dict(zip(im["espn_id"], im["player"]))
        ev = ev.copy()
        ev["player"] = ev["player"].map(lambda p: mp.get(int(p), SYNTH + int(p)) if p else 0).astype(np.int64)
        done = g[g["completed"]]
        st, iss, pg = build_season(ev[ev["game_id"].isin(done["game_id"])].drop(columns=["event_id"], errors="ignore"),
                                   done)
        nm = dict(zip(im["player"], im["name"]))
        pg["name"] = pg["player"].map(nm)
        h_ev = st.groupby("game_id")["hpts"].sum()
        a_ev = st.groupby("game_id")["apts"].sum()
        g["h_ev"] = g["game_id"].map(h_ev)
        g["a_ev"] = g["game_id"].map(a_ev)
        g["pbp_ok"] = (g["h_ev"] == g["hpts"]) & (g["a_ev"] == g["apts"])
        st["season"] = s
        pg["season"] = s
        iss["season"] = s
        st.to_parquet(proc / f"stints_{s}.parquet", index=False)
        pg.to_parquet(proc / f"player_games_{s}.parquet", index=False)
        iss.to_parquet(proc / f"lineup_issues_{s}.parquet", index=False)
        st5 = st[(st["hn"] == 5) & (st["an"] == 5)]
        info.update({"pbp_coerente": float(g.loc[g["completed"], "pbp_ok"].mean()),
                     "tempo_5contro5": float(st5["dur"].sum() / st["dur"].sum()) if len(st) else None,
                     "giocatori": int(im["player"].nunique()),
                     "id_abbinati": im["how"].value_counts().to_dict()})
    else:
        g["h_ev"] = g["a_ev"] = np.nan
        g["pbp_ok"] = False
    g.drop(columns=["completed"]).to_parquet(proc / f"games_{s}.parquet", index=False)
    from nba.features.schedule import update
    update([s])
    return info


def lines(s: int) -> dict:
    from nba.ingest.external import game_lines
    f = path("external") / "espn" / f"odds_{s}.parquet"
    if not f.exists():
        return {"linee": 0}
    g = pd.read_parquet(path("processed") / f"games_{s}.parquet", columns=["game_id", "espn_id"])
    ln = game_lines(pd.read_parquet(f).assign(event_id=lambda d: d["event_id"].astype(str)))
    if ln.empty:
        return {"linee": 0}
    ln["espn_id"] = ln["espn_id"].astype(str)
    out = g.merge(ln, on="espn_id", how="inner")
    out.to_parquet(path("processed") / f"lines_{s}.parquet", index=False)
    return {"linee": int(out["close_spread_home"].notna().sum())}
