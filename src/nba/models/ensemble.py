"""Ensemble dei componenti: pesi non negativi stimati in walk-forward.

Per la stagione S i pesi si stimano sui pronostici (già fuori campione) delle stagioni precedenti, con più peso
alle più recenti (emivita in stagioni), più una costante. Pesi non negativi: un componente può solo aggiungere
informazione, non essere usato "al contrario".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import nnls

DEFAULTS = dict(hl_seasons=2.0, report_only=True, sum_to_one=False)


def fit_weights(X: np.ndarray, y: np.ndarray, w: np.ndarray, sum_to_one: bool = False) -> tuple[float, np.ndarray]:
    sw = np.sqrt(w)[:, None]
    A = np.column_stack([np.ones(len(y)), -np.ones(len(y)), X]) * sw
    b = y * sw[:, 0]
    if sum_to_one:                       # riga di vincolo molto pesante: somma dei pesi = 1 (media pesata)
        big = 1e4 * np.sqrt(w.sum())
        A = np.vstack([A, np.r_[0.0, 0.0, np.full(X.shape[1], big)]])
        b = np.r_[b, big]
    sol, _ = nnls(A, b)
    return sol[0] - sol[1], sol[2:]


def fit_predict(df: pd.DataFrame, cols: list[str], target: str, seasons: list[int], P: dict | None = None) -> pd.DataFrame:
    P = {**DEFAULTS, **(P or {})}
    y = (df["hpts"] - df["apts"] if target == "margin" else df["hpts"] + df["apts"]).astype(float).to_numpy()
    ok = df[cols].notna().all(axis=1).to_numpy()
    out, weights = [], {}
    for s in seasons:
        tr = (df["season"] < s).to_numpy() & ok
        if P["report_only"] and (tr & df["has_report"].to_numpy()).sum() >= 500:
            tr &= df["has_report"].to_numpy()
        if tr.sum() < 500:
            continue
        te = (df["season"] == s).to_numpy() & ok
        w = 0.5 ** ((s - 1 - df["season"].to_numpy()[tr]) / P["hl_seasons"])
        a, b = fit_weights(df.loc[tr, cols].to_numpy(float), y[tr], w, P["sum_to_one"])
        o = df.loc[te, ["game_id", "season"]].copy()
        o["pred"] = a + df.loc[te, cols].to_numpy(float) @ b
        out.append(o)
        weights[s] = {"costante": a, **dict(zip(cols, b))}
    fit_predict.last_weights = weights
    return pd.concat(out, ignore_index=True)
