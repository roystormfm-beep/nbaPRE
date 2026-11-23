"""Confronto della stagione in corso: nuovo modello, modello della pagina e mercato, sulle stesse partite.

Tre campioni, sempre separati:
  ricostruiti  tutte le partite concluse, pronosticate a posteriori con le sole informazioni precedenti
  dal vivo     l'ultimo pronostico pubblicato prima della palla a due (predictions/registro_{S}.csv)
  pagina       i pronostici congelati dalla pagina (export dei documenti nba/predlog-*), se passati con --page
Uscita: predictions/confronto_{S}.json. Sotto le 500 partite i numeri sono solo indicativi.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nba.config import cfg, path
from nba.evaluate.metrics import _boot_ci
from nba.live.publish import OUT


def _results(season: int) -> pd.DataFrame:
    g = pd.read_parquet(path("processed") / f"games_{season}.parquet").dropna(subset=["hpts"])
    g = g[["game_id", "date", "away", "home", "apts", "hpts"]].rename(columns={"date": "d", "away": "a", "home": "h"})
    ln = path("processed") / f"lines_{season}.parquet"
    if ln.exists():
        g = g.merge(pd.read_parquet(ln)[["game_id", "close_spread_home", "p_home_mkt"]], on="game_id", how="left")
    return g


def _metrics(y: np.ndarray, m: np.ndarray, p: np.ndarray, mk_m: np.ndarray | None, mk_p: np.ndarray | None, rng) -> dict:
    win = (y > 0).astype(float)
    r = {"partite": int(len(y)), "MAE": float(np.abs(y - m).mean()), "Brier": float(((p - win) ** 2).mean()),
         "vincitori": float(((p > 0.5) == (win == 1)).mean())}
    if mk_m is not None:
        ok = np.isfinite(mk_m)
        r["MAE_mercato"] = float(np.abs(y[ok] - mk_m[ok]).mean()) if ok.any() else None
        if ok.sum() >= 2:
            d, lo, hi = _boot_ci(np.abs(y[ok] - m[ok]) - np.abs(y[ok] - mk_m[ok]), rng)
            r["vs_mercato"], r["vs_mercato_lo"], r["vs_mercato_hi"] = d, lo, hi
    if mk_p is not None:
        ok = np.isfinite(mk_p)
        r["Brier_mercato"] = float(((mk_p[ok] - win[ok]) ** 2).mean()) if ok.any() else None
    return r


def page_rows(page_file: str) -> pd.DataFrame:
    js = json.load(open(page_file))
    docs = js if isinstance(js, dict) else {}
    rows = []
    for k, v in docs.items():
        g = v.get("g") if isinstance(v, dict) and "g" in v else (v if isinstance(v, dict) else {})
        for key, r in (g or {}).items():
            if isinstance(r, dict) and "m" in r:
                rows.append(r)
    return pd.DataFrame(rows)


def run(season: int = 2026, page_file: str | None = None) -> str:
    rng = np.random.default_rng(cfg()["seed"])
    res = _results(season)
    out, lines = {}, []
    rc = OUT / f"ricostruiti_{season}.csv"
    if rc.exists():
        x = pd.read_csv(rc, dtype={"game_id": str}).dropna(subset=["hpts"])
        y = (x["hpts"] - x["apts"]).to_numpy(float)
        out["ricostruiti"] = _metrics(y, x["m_final"].to_numpy(float), x["p_home"].to_numpy(float),
                                      -x["close_spread_home"].to_numpy(float), x["p_home_mkt"].to_numpy(float), rng)
        out["ricostruiti_baseline"] = _metrics(y, x["m_base"].to_numpy(float), np.full(len(y), 0.5), None, None, rng)
        lines.append(f"Ricostruiti ({len(x)} partite): errore medio {out['ricostruiti']['MAE']:.2f}, mercato "
                     f"{out['ricostruiti'].get('MAE_mercato') or float('nan'):.2f}; baseline ritarato {out['ricostruiti_baseline']['MAE']:.2f}")
    rf = OUT / f"registro_{season}.csv"
    live = pd.DataFrame()
    if rf.exists():
        reg = pd.read_csv(rf)
        reg = reg[pd.to_datetime(reg["t"], utc=True) < pd.to_datetime(reg["tip"], utc=True)]
        live = reg.sort_values("t").groupby(["d", "a", "h"]).tail(1).merge(res, on=["d", "a", "h"], how="inner")
        if len(live):
            y = (live["hpts"] - live["apts"]).to_numpy(float)
            out["dal_vivo"] = _metrics(y, live["m"].to_numpy(float), live["p"].to_numpy(float),
                                       -live["mk_sp"].to_numpy(float), live["mk_ph"].to_numpy(float), rng)
            lines.append(f"Dal vivo ({len(live)} partite): errore medio {out['dal_vivo']['MAE']:.2f}")
    if page_file:
        pg = page_rows(page_file)
        if len(pg):
            pg = pg[pg.get("src", pd.Series("auto", index=pg.index)).fillna("auto") != "ricostruito"]
            pm = pg.merge(res, on=["d", "a", "h"], how="inner")
            ours = None
            if len(live):
                ours = live[["d", "a", "h", "m", "p"]].rename(columns={"m": "m_new", "p": "p_new"})
                src = "dal vivo"
            if (ours is None or ours.empty) and rc.exists():
                xr = pd.read_csv(rc, dtype={"game_id": str})
                ours = xr.rename(columns={"date": "d", "away": "a", "home": "h", "m_final": "m_new", "p_home": "p_new"})[["d", "a", "h", "m_new", "p_new"]]
                src = "ricostruiti"
            both = pm.merge(ours, on=["d", "a", "h"], how="inner") if ours is not None else pd.DataFrame()
            if len(both):
                y = (both["hpts"] - both["apts"]).to_numpy(float)
                mk = -both["close_spread_home"].to_numpy(float)
                out["pagina"] = _metrics(y, both["m"].to_numpy(float), both["p"].to_numpy(float), mk, both["p_home_mkt"].to_numpy(float), rng)
                out["nuovo_stesse_partite"] = _metrics(y, both["m_new"].to_numpy(float), both["p_new"].to_numpy(float), mk,
                                                       both["p_home_mkt"].to_numpy(float), rng)
                d, lo, hi = _boot_ci(np.abs(y - both["m_new"].to_numpy(float)) - np.abs(y - both["m"].to_numpy(float)), rng)
                out["nuovo_vs_pagina"] = {"partite": int(len(both)), "fonte_nuovo": src, "dMAE": d, "lo": lo, "hi": hi}
                lines.append(f"Pagina contro nuovo modello ({src}), {len(both)} partite in comune: errore medio "
                             f"{out['pagina']['MAE']:.2f} contro {out['nuovo_stesse_partite']['MAE']:.2f} "
                             f"(differenza {d:+.2f}, IC 95% {lo:+.2f}; {hi:+.2f})")
    (OUT / f"confronto_{season}.json").write_text(json.dumps(out, indent=1, default=float))
    return "\n".join(lines) or "nessun dato da confrontare"
