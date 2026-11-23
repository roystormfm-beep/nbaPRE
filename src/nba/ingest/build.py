"""Costruzione dei dati elaborati di una stagione: partite, stint, statistiche per giocatore, problemi trovati.

Fonte degli eventi: cdn.nba.com dove esiste (2020→), altrimenti NBA Stats v2. Nelle stagioni in cui ci sono
entrambe, la seconda serve da controllo incrociato (vedi qc.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import path
from nba.ingest.events import _gid, from_cdn, from_nbastats_v2
from nba.ingest.games import build_games
from nba.ingest.pbp_download import raw_file
from nba.ingest.qc_quick import team_points
from nba.ingest.stints import build_season


def events_for(season: int, source: str | None = None) -> tuple[pd.DataFrame, str]:
    if source is None:
        source = "cdn" if raw_file("cdnnba", season).exists() else "v2"
    if source == "cdn":
        return from_cdn(pd.read_parquet(raw_file("cdnnba", season))), "cdn"
    return from_nbastats_v2(pd.read_parquet(raw_file("nbastats", season))), "v2"


def consensus_score(g: pd.DataFrame, min_total: int = 120) -> pd.DataFrame:
    """Punteggio finale: il valore su cui concorda il maggior numero di fonti indipendenti complete.

    Fonti: 'ev' (somma dei punti dagli eventi), 'cdn' (campo punteggio di cdn.nba.com), 'stats' (campo punteggio
    di NBA Stats: v2 e v3 vengono dallo stesso archivio, quindi contano come una sola fonte), 'espn' quando c'è."""
    g = g.copy()
    if "h_v2" in g or "h_v3" in g:
        hv2 = g["h_v2"] if "h_v2" in g else pd.Series(np.nan, index=g.index)
        av2 = g["a_v2"] if "a_v2" in g else pd.Series(np.nan, index=g.index)
        ok2 = (hv2 + av2) >= min_total
        g["h_stats"] = np.where(ok2, hv2, g.get("h_v3"))
        g["a_stats"] = np.where(ok2, av2, g.get("a_v3"))
    srcs = [s for s in ("ev", "cdn", "stats", "espn") if f"h_{s}" in g and f"a_{s}" in g]
    hs, as_, nagree, nsrc, chosen = [], [], [], [], []
    for _, r in g.iterrows():
        votes = {}
        n = 0
        for s in srcs:
            h, a = r.get(f"h_{s}"), r.get(f"a_{s}")
            if pd.isna(h) or pd.isna(a) or h + a < min_total:
                continue
            n += 1
            votes.setdefault((int(h), int(a)), []).append(s)
        if not votes:
            hs.append(np.nan); as_.append(np.nan); nagree.append(0); nsrc.append(0); chosen.append("")
            continue
        # a parità di voti preferisco il tabellino ufficiale (ESPN, poi NBA Stats), poi gli eventi
        best = max(votes.items(), key=lambda kv: (len(kv[1]), "espn" in kv[1], "stats" in kv[1], "ev" in kv[1]))
        hs.append(best[0][0]); as_.append(best[0][1]); nagree.append(len(best[1])); nsrc.append(n)
        chosen.append("+".join(best[1]))
    g["hpts"], g["apts"], g["score_agree"], g["score_sources"], g["score_from"] = hs, as_, nagree, nsrc, chosen
    return g


def player_names(season: int) -> pd.DataFrame:
    names = []
    p2 = raw_file("nbastats", season)
    if p2.exists():
        v2 = pd.read_parquet(p2, columns=["PLAYER1_ID", "PLAYER1_NAME", "PERSON1TYPE"])
        v2 = v2[v2["PERSON1TYPE"].isin([4, 5])].dropna(subset=["PLAYER1_NAME"])
        names.append(pd.DataFrame({"player": pd.to_numeric(v2["PLAYER1_ID"], errors="coerce"),
                                   "name": v2["PLAYER1_NAME"], "src": "v2"}))
    pm = raw_file("matchups", season)
    if not pm.exists():
        try:
            from nba.ingest.pbp_download import fetch
            fetch("matchups", season)
        except Exception:
            pass
    if pm.exists():
        m = pd.read_parquet(pm, columns=["person_id", "first_name", "family_name"]).dropna()
        names.append(pd.DataFrame({"player": pd.to_numeric(m["person_id"], errors="coerce"),
                                   "name": (m["first_name"].astype(str) + " " + m["family_name"].astype(str)).str.strip(),
                                   "src": "matchups"}))
    pc = raw_file("cdnnba", season)
    if pc.exists():
        c = pd.read_parquet(pc, columns=["personId", "playerNameI"]).dropna()
        names.append(pd.DataFrame({"player": pd.to_numeric(c["personId"], errors="coerce"),
                                   "name": c["playerNameI"], "src": "cdn"}))
    if not names:
        return pd.DataFrame(columns=["player", "name"])
    n = pd.concat(names).dropna()
    n = n[n["player"] > 0]
    n["player"] = n["player"].astype(np.int64)
    prio = {"v2": 0, "matchups": 1, "cdn": 2}
    n["prio"] = n["src"].map(prio)
    n = n.groupby(["player", "name", "prio"]).size().rename("cnt").reset_index()
    n = n.sort_values(["player", "prio", "cnt"], ascending=[True, True, False]).drop_duplicates("player")
    return n[["player", "name"]]


def build(season: int) -> dict:
    out_dir = path("processed")
    g = build_games(season)
    ev, src = events_for(season)
    stints, issues, pg = build_season(ev, g)
    tp = team_points(pg, g)
    g = g.merge(tp[["game_id", "h_ev", "a_ev"]], on="game_id", how="left")
    g = consensus_score(g)
    g["event_source"] = src
    # play-by-play utilizzabile per i quintetti: eventi completi e coerenti con il punteggio finale
    g["pbp_ok"] = (g["h_ev"] == g["hpts"]) & (g["a_ev"] == g["apts"])
    names = player_names(season)
    pg = pg.merge(names, on="player", how="left")
    pg["season"] = season
    stints["season"] = season
    issues["season"] = season
    keep = ["game_id", "season", "date", "tip_utc", "home", "away", "periods", "hpts", "apts", "score_agree",
            "score_sources", "score_from", "event_source", "pbp_ok"] + [c for c in g.columns if c[:2] in ("h_", "a_")]
    g = g[[c for c in keep if c in g.columns]]
    g.to_parquet(out_dir / f"games_{season}.parquet", index=False)
    stints.to_parquet(out_dir / f"stints_{season}.parquet", index=False)
    pg.to_parquet(out_dir / f"player_games_{season}.parquet", index=False)
    issues.to_parquet(out_dir / f"lineup_issues_{season}.parquet", index=False)
    return {"season": season, "source": src, "games": len(g), "stints": len(stints), "player_games": len(pg),
            "lineup_issues": len(issues)}
