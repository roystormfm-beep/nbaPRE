"""Analisi degli errori: le partite peggiori e i motivi, calcolati a partita finita (analisi, non pronostico).

Codici motivo:
  TIRO3        tiro da tre molto sopra o sotto la media della lega (punti in più o in meno rispetto all'atteso)
  LIBERI       tiri liberi molto sopra o sotto la media
  ASSENZA      giocatori di rotazione attesi in campo (almeno 15 minuti proiettati) che non hanno giocato
  RIENTRO      giocatori che hanno giocato almeno 20 minuti con meno di 5 minuti proiettati
  SUPPL        partita finita ai supplementari
  SENSO_UNICO  scarto finale di 25 punti o più (spesso con riserve in campo nel finale)
  MERCATO      il mercato vedeva la partita in modo diverso (almeno 3 punti) ed era più vicino al risultato
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import path


def _team_shooting(season: int) -> pd.DataFrame:
    pg = pd.read_parquet(path("processed") / f"player_games_{season}.parquet")
    t = pg.groupby(["game_id", "team"])[["fg3m", "fg3a", "ftm", "fta"]].sum().reset_index()
    l3 = t["fg3m"].sum() / t["fg3a"].sum()
    lft = t["ftm"].sum() / t["fta"].sum()
    t["luck3"] = 3 * (t["fg3m"] - t["fg3a"] * l3)
    t["luckft"] = t["ftm"] - t["fta"] * lft
    return t


def _absences(season: int) -> pd.DataFrame:
    proc = path("processed")
    f = proc / f"minutes_proj_report_{season}.parquet"
    if not f.exists():
        return pd.DataFrame(columns=["game_id", "team", "assenti", "min_assenti", "rientri"])
    mp = pd.read_parquet(f)
    pg = pd.read_parquet(proc / f"player_games_{season}.parquet")[["game_id", "team", "player", "min", "name"]]
    names = pg.drop_duplicates("player").set_index("player")["name"]
    x = mp.merge(pg.rename(columns={"min": "min_real"}), on=["game_id", "team", "player"], how="outer")
    x["min"] = x["min"].fillna(0.0)
    x["min_real"] = x["min_real"].fillna(0.0)
    x["nome"] = x["player"].map(names).fillna(x["player"].astype(str))
    miss = x[(x["min"] >= 15) & (x["min_real"] == 0)]
    back = x[(x["min"] < 5) & (x["min_real"] >= 20)]
    a = miss.groupby(["game_id", "team"]).agg(assenti=("nome", lambda s: ", ".join(s)), min_assenti=("min", "sum"))
    b = back.groupby(["game_id", "team"]).agg(rientri=("nome", lambda s: ", ".join(s)))
    return a.join(b, how="outer").reset_index()


def worst(x: pd.DataFrame, season: int, n: int = 50) -> pd.DataFrame:
    """x: pronostici della stagione con m_final, close_spread_home, hpts, apts, home, away, date, game_id."""
    g = pd.read_parquet(path("processed") / f"games_{season}.parquet")[["game_id", "periods"]]
    x = x.merge(g, on="game_id", how="left").copy()
    y = x["hpts"] - x["apts"]
    x["errore"] = y - x["m_final"]
    x = x.reindex(x["errore"].abs().sort_values(ascending=False).index).head(n).copy()
    sh = _team_shooting(season)
    ab = _absences(season)
    for side in ("home", "away"):
        s = sh.rename(columns={"team": side})[["game_id", side, "luck3", "luckft"]]
        x = x.merge(s.rename(columns={"luck3": f"{side}_l3", "luckft": f"{side}_lft"}), on=["game_id", side], how="left")
        a = ab.rename(columns={"team": side})
        x = x.merge(a.rename(columns={"assenti": f"{side}_ass", "min_assenti": f"{side}_minass", "rientri": f"{side}_rie"}),
                    on=["game_id", side], how="left")
    x["tiro3"] = x["home_l3"] - x["away_l3"]          # punti in più per la casa dovuti al tiro da tre
    x["liberi"] = x["home_lft"] - x["away_lft"]
    rows = []
    for r in x.itertuples():
        codes = []
        e = r.errore
        if abs(r.tiro3) >= 6 and np.sign(r.tiro3) == np.sign(e):
            codes.append((abs(r.tiro3), f"TIRO3 ({r.tiro3:+.0f} punti per la casa)"))
        if abs(r.liberi) >= 4 and np.sign(r.liberi) == np.sign(e):
            codes.append((abs(r.liberi), f"LIBERI ({r.liberi:+.0f} punti per la casa)"))
        for side, sign in (("home", -1), ("away", 1)):
            ass = getattr(r, f"{side}_ass")
            if isinstance(ass, str) and np.sign(e) == sign:
                codes.append((getattr(r, f"{side}_minass") / 6, f"ASSENZA {getattr(r, side)}: {ass}"))
            rie = getattr(r, f"{side}_rie")
            if isinstance(rie, str) and np.sign(e) == -sign:
                codes.append((3.0, f"RIENTRO {getattr(r, side)}: {rie}"))
        if r.periods and r.periods > 4:
            codes.append((1.0, "SUPPL"))
        if abs(r.hpts - r.apts) >= 25:
            codes.append((2.0, "SENSO_UNICO"))
        mkt = -r.close_spread_home if pd.notna(r.close_spread_home) else np.nan
        if np.isfinite(mkt) and abs(mkt - r.m_final) >= 3 and abs((r.hpts - r.apts) - mkt) + 3 <= abs(e):
            codes.append((abs(mkt - r.m_final), f"MERCATO (linea {r.close_spread_home:+.1f})"))
        codes.sort(key=lambda c: -c[0])
        rows.append({"data": str(r.date)[:10], "partita": f"{r.away} @ {r.home}", "risultato": f"{int(r.apts)}-{int(r.hpts)}",
                     "scarto_vero": int(r.hpts - r.apts), "pronostico": round(r.m_final, 1),
                     "mercato": round(mkt, 1) if np.isfinite(mkt) else None, "errore": round(e, 1),
                     "tiro3": round(r.tiro3, 1), "liberi": round(r.liberi, 1),
                     "motivi": "; ".join(c[1] for c in codes) if codes else "nessun motivo evidente (varianza)"})
    return pd.DataFrame(rows)


def reason_summary(w: pd.DataFrame) -> dict:
    out = {}
    for code in ("TIRO3", "LIBERI", "ASSENZA", "RIENTRO", "SUPPL", "SENSO_UNICO", "MERCATO", "nessun motivo"):
        out[code] = int(w["motivi"].str.contains(code).sum())
    return out
