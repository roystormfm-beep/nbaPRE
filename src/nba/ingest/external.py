"""Unisce i dati raccolti da GitHub Actions (ESPN) alla tabella partite.

- ESPN scoreboard: terza fonte per il punteggio finale, data delle partite mancanti, sede e campo neutro.
- ESPN odds: linee per partita. Per ogni partita si sceglie un fornitore principale (vedi PROVIDER_ORDER)
  e si tengono apertura e chiusura dove esistono; 'current' dopo la fine della partita = ultima linea salvata.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import path

# Fornitore "principale" per partita, in ordine di preferenza (nomi normalizzati: minuscolo, senza spazi)
PROVIDER_ORDER = ["consensus", "pinnaclesports.com", "draftkings", "espnbet", "westgate", "caesarssportsbook",
                  "caesars", "mgm", "betonline.ag", "bovada.lv", "5dimes.eu", "unibet"]
# siti di pronostici o fornitori di dati, non bookmaker; "opening" è la linea d'apertura (usata solo come tale)
NOT_BOOKS = {"accuscore", "numberfire", "teamrankings", "betegy", "fantasy911.com", "betradar", "opening"}


def _norm_provider(p) -> str:
    return str(p or "").lower().replace(" ", "").replace("'", "")


def _american_to_prob(ml):
    if pd.isna(ml) or ml == 0:
        return np.nan
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)


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


def _first(*vals):
    for v in vals:
        if v is not None and pd.notna(v):
            return float(v)
    return np.nan


def _home_spread(r, ph):
    v = r.get(f"{ph}_home_spread")
    if (v is None or pd.isna(v)) and pd.notna(r.get(f"{ph}_away_spread")):
        v = -r[f"{ph}_away_spread"]
    return v


def game_lines(od: pd.DataFrame) -> pd.DataFrame:
    """Una riga per partita.

    Chiusura = mediana tra i bookmaker dell'ultima linea pre-partita salvata da ESPN ('close', altrimenti 'current',
    altrimenti il campo 'spread' che ESPN dà già dal punto di vista della squadra di casa).
    Le linee "Live Odds" (durante la partita) sono escluse. Apertura = fornitore "Opening" (anni 2014-2016) oppure
    il campo 'open' dei bookmaker che lo hanno (stagioni recenti).
    Probabilità di mercato = mediana tra i bookmaker delle probabilità implicite nella moneyline, senza margine."""
    if od is None or od.empty:
        return pd.DataFrame()
    od = od.copy()
    od["pn"] = od["provider"].map(_norm_provider)
    live = od["pn"].str.contains("live")
    opening = od[od["pn"] == "opening"]
    books = od[~live & ~od["pn"].isin(NOT_BOOKS)].copy()
    rank = {p: i for i, p in enumerate(PROVIDER_ORDER)}
    books["rank"] = books["pn"].map(rank).fillna(len(rank))
    books = books.sort_values(["event_id", "rank"])
    rows = []
    for eid, grp in books.groupby("event_id", sort=False):
        sp, tot, ph, osp, otot = [], [], [], [], []
        for _, r in grp.iterrows():
            sp.append(_first(_home_spread(r, "close"), _home_spread(r, "current"), r.get("spread")))
            tot.append(_first(r.get("close_total"), r.get("current_total"), r.get("over_under")))
            mh = _first(r.get("close_home_ml"), r.get("current_home_ml"), r.get("home_ml"))
            ma = _first(r.get("close_away_ml"), r.get("current_away_ml"), r.get("away_ml"))
            p_h, p_a = _american_to_prob(mh), _american_to_prob(ma)
            ph.append(p_h / (p_h + p_a) if pd.notna(p_h) and pd.notna(p_a) else np.nan)
            osp.append(_first(_home_spread(r, "open")))
            otot.append(_first(r.get("open_total")))
        top = grp.iloc[0]
        o = opening[opening["event_id"] == eid]
        open_sp = _first(*(o.apply(lambda r: _first(_home_spread(r, "current"), r.get("spread")), axis=1).tolist()
                           if len(o) else []), np.nanmedian(osp) if np.isfinite(osp).any() else np.nan)
        open_tot = _first(*(o.apply(lambda r: _first(r.get("current_total"), r.get("over_under")), axis=1).tolist()
                            if len(o) else []), np.nanmedian(otot) if np.isfinite(otot).any() else np.nan)
        sp_a, tot_a, ph_a = np.array(sp, float), np.array(tot, float), np.array(ph, float)
        rows.append({
            "espn_id": eid, "main_book": top["provider"], "n_books": int(np.isfinite(sp_a).sum()),
            "close_spread_home": float(np.nanmedian(sp_a)) if np.isfinite(sp_a).any() else np.nan,
            "close_spread_main": sp[0], "spread_range": float(np.nanmax(sp_a) - np.nanmin(sp_a)) if np.isfinite(sp_a).any() else np.nan,
            "close_total": float(np.nanmedian(tot_a)) if np.isfinite(tot_a).any() else np.nan,
            "p_home_mkt": float(np.nanmedian(ph_a)) if np.isfinite(ph_a).any() else np.nan,
            "open_spread_home": open_sp, "open_total": open_tot,
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
