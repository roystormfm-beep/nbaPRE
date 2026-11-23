"""Unisce i dati raccolti da GitHub Actions (ESPN) alla tabella partite.

- ESPN scoreboard: terza fonte per il punteggio finale, data delle partite mancanti, sede e campo neutro.
- ESPN odds: linee per partita. Per ogni partita si sceglie un fornitore principale (vedi PROVIDER_ORDER)
  e si tengono apertura e chiusura dove esistono; 'current' dopo la fine della partita = ultima linea salvata.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import path

# Ordine di preferenza dei fornitori di quote (i più presenti e affidabili prima)
PROVIDER_ORDER = ["consensus", "DraftKings", "ESPN BET", "Caesars Sportsbook", "Caesars", "MGM", "William Hill",
                  "Westgate", "FanDuel", "BetMGM", "PointsBet", "Unibet"]
NOT_BOOKS = {"accuscore", "numberfire", "teamrankings"}   # siti di pronostici, non bookmaker


def _espn_file(kind: str, s: int):
    p = path("external") / "espn" / f"{kind}_{s}.parquet"
    return p if p.exists() else None


def match_espn(games: pd.DataFrame, sb: pd.DataFrame) -> pd.DataFrame:
    """Abbina le partite ESPN alle nostre per squadre e data (tolleranza ±1 giorno)."""
    sb = sb[sb["season_type"] == 2].copy()
    sb["d"] = pd.to_datetime(sb["date_et"])
    g = games.copy()
    g["d"] = pd.to_datetime(g["date"])
    out = []
    used = set()
    by_pair = {k: v for k, v in sb.groupby(["home", "away"])}
    for _, r in g.iterrows():
        cand = by_pair.get((r["home"], r["away"]))
        best = None
        if cand is not None:
            c = cand[~cand["event_id"].isin(used)]
            if pd.notna(r["d"]):
                c = c.assign(dd=(c["d"] - r["d"]).abs().dt.days).query("dd <= 1").sort_values("dd")
            elif len(c) != 1:
                c = c.iloc[0:0]
            if len(c):
                best = c.iloc[0]
                used.add(best["event_id"])
        out.append({"game_id": r["game_id"],
                    "espn_id": None if best is None else best["event_id"],
                    "h_espn": np.nan if best is None else best["hpts"],
                    "a_espn": np.nan if best is None else best["apts"],
                    "date_espn": None if best is None else best["date_et"],
                    "tip_utc_espn": None if best is None else best["date_utc"],
                    "neutral": None if best is None else bool(best["neutral"]),
                    "venue": None if best is None else best["venue"],
                    "venue_city": None if best is None else best["city"],
                    "venue_country": None if best is None else best.get("country")})
    return pd.DataFrame(out)


def game_lines(od: pd.DataFrame) -> pd.DataFrame:
    """Una riga per partita: linea del fornitore preferito, con apertura e chiusura dove disponibili."""
    if od is None or od.empty:
        return pd.DataFrame()
    od = od[~od["provider"].fillna("").str.lower().isin(NOT_BOOKS)].copy()
    rank = {p.lower(): i for i, p in enumerate(PROVIDER_ORDER)}
    od["rank"] = od["provider"].fillna("").str.lower().map(rank).fillna(len(rank))
    od = od.sort_values(["event_id", "rank", "priority"])

    def home_spread(r, ph):
        v = r.get(f"{ph}_home_spread")
        if pd.isna(v) and pd.notna(r.get(f"{ph}_away_spread")):
            v = -r[f"{ph}_away_spread"]
        return v

    rows = []
    for eid, grp in od.groupby("event_id", sort=False):
        r = grp.iloc[0]
        close_sp = home_spread(r, "close")
        cur_sp = home_spread(r, "current")
        # 'spread' in cima all'oggetto ESPN è già dal punto di vista della squadra di casa
        final_sp = close_sp if pd.notna(close_sp) else (cur_sp if pd.notna(cur_sp) else r.get("spread"))
        final_tot = next((x for x in (r.get("close_total"), r.get("current_total"), r.get("over_under")) if pd.notna(x)), np.nan)
        rows.append({
            "espn_id": eid, "book": r["provider"], "n_books": grp["provider"].nunique(),
            "open_spread_home": home_spread(r, "open"), "close_spread_home": final_sp,
            "open_total": r.get("open_total"), "close_total": final_tot,
            "close_ml_home": next((x for x in (r.get("close_home_ml"), r.get("current_home_ml"), r.get("home_ml")) if pd.notna(x)), np.nan),
            "close_ml_away": next((x for x in (r.get("close_away_ml"), r.get("current_away_ml"), r.get("away_ml")) if pd.notna(x)), np.nan),
            "spread_median_books": grp.apply(lambda x: x["spread"], axis=1).median(),
        })
    return pd.DataFrame(rows)


def attach(season: int) -> dict:
    """Aggiorna games_{S}.parquet con ESPN e scrive lines_{S}.parquet. Restituisce un piccolo riepilogo."""
    from nba.ingest.build import consensus_score
    gp = path("processed") / f"games_{season}.parquet"
    g = pd.read_parquet(gp)
    sbf = _espn_file("scoreboard", season)
    if sbf is None:
        return {"season": season, "espn": "assente"}
    m = match_espn(g, pd.read_parquet(sbf))
    g = g.drop(columns=[c for c in m.columns if c != "game_id" and c in g.columns]).merge(m, on="game_id", how="left")
    g["date"] = g["date"].fillna(g["date_espn"])
    g = consensus_score(g)
    g["pbp_ok"] = (g["h_ev"] == g["hpts"]) & (g["a_ev"] == g["apts"])
    g.to_parquet(gp, index=False)
    res = {"season": season, "abbinate": int(m["espn_id"].notna().sum()), "partite": len(g),
           "espn_uguale_finale": float(((g["h_espn"] == g["hpts"]) & (g["a_espn"] == g["apts"])).mean())}
    odf = _espn_file("odds", season)
    if odf is not None:
        lines = game_lines(pd.read_parquet(odf))
        lines = g[["game_id", "espn_id"]].merge(lines, on="espn_id", how="inner")
        lines.to_parquet(path("processed") / f"lines_{season}.parquet", index=False)
        res["con_linea"] = float(lines["close_spread_home"].notna().sum() / len(g))
        res["con_apertura"] = float(lines["open_spread_home"].notna().sum() / len(g))
    return res
