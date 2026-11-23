"""Modello "consapevole del mercato", tenuto separato dal modello puro.

Domanda: partendo dalla linea d'apertura, il nostro pronostico aiuta a prevedere dove andrà la linea di chiusura?
  movimento = chiusura − apertura (spread della squadra di casa)
  disaccordo = (−pronostico) − apertura (quanto il modello vede la partita diversamente dall'apertura)
  movimento previsto = β × disaccordo, con β stimato sulle stagioni precedenti con apertura.
Due insiemi di informazioni:
  all'apertura      modello giocatori senza injury report (approssima ciò che si sapeva all'apertura)
  prima della gara  pronostico finale con l'injury report di 45 minuti prima (non disponibile all'apertura)
Le linee d'apertura ci sono per 2014-15 → 2016-17 e 2023-24 → 2025-26.
CLV: si sceglie un lato confrontando il pronostico con l'apertura; si misura di quanti punti la linea si è poi
mossa a favore (positivo) o contro (negativo).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.evaluate.metrics import _boot_ci, attach_market

INFO = {"all'apertura (senza injury report)": "m_open_info", "prima della gara (con injury report)": "m_final"}


def table(x: pd.DataFrame) -> pd.DataFrame:
    """x: partite con open_spread_home, close_spread_home, season e le colonne in INFO."""
    return attach_market(x).dropna(subset=["open_spread_home", "close_spread_home"])


def run(x: pd.DataFrame, seasons: list[int], rng) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = table(x)
    mov = (x["close_spread_home"] - x["open_spread_home"]).to_numpy(float)
    rows, preds = [], []
    for label, col in INFO.items():
        ok = x[col].notna().to_numpy()
        dis = (-x[col] - x["open_spread_home"]).to_numpy(float)
        pred = np.full(len(x), np.nan)
        for s in seasons:
            tr = (x["season"] < s).to_numpy() & ok
            te = (x["season"] == s).to_numpy() & ok
            if tr.sum() < 300 or te.sum() == 0:
                continue
            beta = float(np.sum(dis[tr] * mov[tr]) / np.sum(dis[tr] ** 2))
            pred[te] = beta * dis[te]
        m = np.isfinite(pred) & x["season"].isin(seasons).to_numpy()
        if m.sum() == 0:
            continue
        mae_naive = np.abs(mov[m]).mean()
        mae_mod = np.abs(mov[m] - pred[m]).mean()
        d, lo, hi = _boot_ci(np.abs(mov[m] - pred[m]) - np.abs(mov[m]), rng)
        big = m & (np.abs(pred) >= 0.5) & (mov != 0)
        dir_ok = (np.sign(pred[big]) == np.sign(mov[big]))
        dm, dlo, dhi = _boot_ci(dir_ok.astype(float), rng)
        # CLV del lato scelto all'apertura con questo pronostico
        pick_home = dis[m] < 0          # il modello vede la casa più forte della linea d'apertura
        clv = np.where(pick_home, x["open_spread_home"].to_numpy(float)[m] - x["close_spread_home"].to_numpy(float)[m],
                       x["close_spread_home"].to_numpy(float)[m] - x["open_spread_home"].to_numpy(float)[m])
        cm, clo, chi = _boot_ci(clv, rng)
        strong = np.abs(dis[m]) >= 3
        sm, slo, shi = _boot_ci(clv[strong], rng) if strong.sum() >= 30 else (np.nan, np.nan, np.nan)
        rows.append({"informazione": label, "partite": int(m.sum()), "corr": float(np.corrcoef(pred[m], mov[m])[0, 1]),
                     "MAE_movimento_naive": mae_naive, "MAE_movimento_modello": mae_mod,
                     "dMAE": d, "dMAE_lo": lo, "dMAE_hi": hi,
                     "direzione_partite": int(big.sum()), "direzione": dm, "direzione_lo": dlo, "direzione_hi": dhi,
                     "CLV": cm, "CLV_lo": clo, "CLV_hi": chi, "CLV_quota_pos": float((clv > 0).mean()),
                     "CLV_forte_partite": int(strong.sum()), "CLV_forte": sm, "CLV_forte_lo": slo, "CLV_forte_hi": shi,
                     "beta": beta})
        preds.append(pd.DataFrame({"game_id": x["game_id"].to_numpy()[m], "info": label, "mov": mov[m], "pred": pred[m]}))
    return pd.DataFrame(rows), (pd.concat(preds) if preds else pd.DataFrame())
