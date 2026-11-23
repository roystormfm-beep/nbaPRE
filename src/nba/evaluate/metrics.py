"""Metriche di valutazione, sempre affiancate a quelle del mercato sullo stesso campione.

Per ogni gruppo di partite: errore sullo scarto (MAE, RMSE), errore sul totale, Brier, log loss, calibrazione (ECE),
vincitori indovinati, record contro lo spread di chiusura e ROI a -110, valore rispetto alla chiusura (CLV) dove
c'è la linea d'apertura. Le differenze con il mercato hanno intervalli di confidenza al 95% da bootstrap appaiato.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import cfg, path

N_BOOT = 2000


def attach_market(pred: pd.DataFrame) -> pd.DataFrame:
    seasons = sorted(pred["season"].unique())
    L = pd.concat([pd.read_parquet(path("processed") / f"lines_{s}.parquet") for s in seasons
                   if (path("processed") / f"lines_{s}.parquet").exists()], ignore_index=True)
    cols = ["game_id", "close_spread_home", "close_total", "p_home_mkt", "open_spread_home", "open_total"]
    return pred.merge(L[cols], on="game_id", how="left")


def _ece(p, y, bins=10):
    p, y = np.asarray(p), np.asarray(y)
    idx = np.clip((p * bins).astype(int), 0, bins - 1)
    e = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return e


def _logloss(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _boot_ci(x, rng, n=N_BOOT):
    """Media e IC 95% bootstrap di un vettore (per le differenze appaiate passare già la differenza)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return np.nan, np.nan, np.nan
    idx = rng.integers(0, len(x), size=(n, len(x)))
    m = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def evaluate(df: pd.DataFrame, seed: int | None = None) -> dict:
    """df: colonne margin_pred, total_pred, p_home, hpts, apts + mercato (close_spread_home, close_total, p_home_mkt...)."""
    rng = np.random.default_rng(seed if seed is not None else cfg()["seed"])
    d = df.dropna(subset=["close_spread_home", "p_home_mkt"]).copy()
    y_m = (d["hpts"] - d["apts"]).to_numpy(float)
    y_t = (d["hpts"] + d["apts"]).to_numpy(float)
    win = (y_m > 0).astype(float)
    mod_m, mkt_m = d["margin_pred"].to_numpy(float), -d["close_spread_home"].to_numpy(float)
    mod_p, mkt_p = d["p_home"].to_numpy(float), d["p_home_mkt"].to_numpy(float)
    ae_mod, ae_mkt = np.abs(y_m - mod_m), np.abs(y_m - mkt_m)
    br_mod, br_mkt = (mod_p - win) ** 2, (mkt_p - win) ** 2
    ll_mod, ll_mkt = _logloss(mod_p, win), _logloss(mkt_p, win)
    tot_ok = d["close_total"].notna().to_numpy()
    r = {"partite": len(d)}
    r["MAE_scarto_modello"], r["MAE_scarto_mercato"] = ae_mod.mean(), ae_mkt.mean()
    r["RMSE_scarto_modello"], r["RMSE_scarto_mercato"] = np.sqrt(((y_m - mod_m) ** 2).mean()), np.sqrt(((y_m - mkt_m) ** 2).mean())
    r["MAE_totale_modello"] = np.abs(y_t - d["total_pred"].to_numpy(float))[tot_ok].mean()
    r["MAE_totale_mercato"] = np.abs(y_t - d["close_total"].to_numpy(float))[tot_ok].mean()
    r["Brier_modello"], r["Brier_mercato"] = br_mod.mean(), br_mkt.mean()
    r["LogLoss_modello"], r["LogLoss_mercato"] = ll_mod.mean(), ll_mkt.mean()
    r["ECE_modello"], r["ECE_mercato"] = _ece(mod_p, win), _ece(mkt_p, win)
    r["vincitori_modello"] = ((mod_p > 0.5) == (win == 1)).mean()
    r["vincitori_mercato"] = ((mkt_p > 0.5) == (win == 1)).mean()
    # differenze appaiate (modello - mercato): negativo = modello migliore
    for k, x in (("dMAE", ae_mod - ae_mkt), ("dBrier", br_mod - br_mkt), ("dLogLoss", ll_mod - ll_mkt)):
        m, lo, hi = _boot_ci(x, rng)
        r[k], r[k + "_lo"], r[k + "_hi"] = m, lo, hi
    # contro lo spread di chiusura: lato scelto dal modello
    edge = mod_m - mkt_m
    cover = y_m - mkt_m                      # > 0: la squadra di casa copre
    pick_home = edge > 0
    valid = (edge != 0) & (cover != 0)
    won = np.where(pick_home, cover > 0, cover < 0)[valid]
    r["ATS_vinte"], r["ATS_perse"], r["ATS_push"] = int(won.sum()), int((~won).sum()), int((cover == 0).sum())
    m, lo, hi = _boot_ci(won.astype(float), rng)
    r["ATS_pct"], r["ATS_lo"], r["ATS_hi"] = m, lo, hi
    roi = np.where(won, 100 / 110, -1.0)
    m, lo, hi = _boot_ci(roi, rng)
    r["ROI"], r["ROI_lo"], r["ROI_hi"] = m, lo, hi
    # valore rispetto alla chiusura: lato scelto con la linea d'apertura, punti guadagnati sulla chiusura
    o = d["open_spread_home"].to_numpy(float)
    has_o = np.isfinite(o)
    if has_o.sum() >= 50:
        pick_h_open = (mod_m + o) > 0
        clv = np.where(pick_h_open, o - d["close_spread_home"].to_numpy(float), d["close_spread_home"].to_numpy(float) - o)[has_o]
        m, lo, hi = _boot_ci(clv, rng)
        r["CLV_partite"], r["CLV_punti"], r["CLV_lo"], r["CLV_hi"] = int(has_o.sum()), m, lo, hi
        r["CLV_quota_positivo"] = float((clv > 0).mean())
    return r


def table(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    rows = []
    for k, g in df.groupby(by):
        r = evaluate(g)
        r.update(dict(zip(by, k if isinstance(k, tuple) else (k,))))
        rows.append(r)
    return pd.DataFrame(rows)
