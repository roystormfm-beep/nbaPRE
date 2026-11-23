"""Distribuzione dello scarto attorno al pronostico.

Tre forme a confronto, tutte stimate solo sulle stagioni precedenti (più peso alle recenti):
  normale    deviazione standard unica (errore tipico delle stagioni precedenti)
  normale_v  normale con deviazione standard che dipende dal totale atteso (ritmo e livello di punteggio)
             e dalla differenza di forza: sd = exp(c0 + c1·log(totale/225) + c2·|scarto|/10)
  t          come normale_v ma con le code di una t di Student (gradi di libertà stimati)
  empirica   residui standardizzati delle stagioni precedenti (nessuna forma imposta)
Da qui: probabilità di vittoria P(scarto > 0) e di coprire qualsiasi spread P(scarto > −spread).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats

KINDS = ["normale", "normale_v", "t", "empirica"]


def _sd(c, m, t):
    return np.exp(c[0] + c[1] * np.log(np.asarray(t) / 225.0) + c[2] * np.abs(np.asarray(m)) / 10.0)


def fit(r, m, t, w, kind: str) -> dict:
    r, m, t, w = (np.asarray(a, float) for a in (r, m, t, w))
    if kind == "normale":
        return {"kind": kind, "c": np.array([np.log(np.sqrt(np.average(r ** 2, weights=w))), 0.0, 0.0])}

    def nll(theta):
        c = theta[:3]
        s = _sd(c, m, t)
        if kind == "t":
            df = 2.0 + np.exp(theta[3])
            scale = s * np.sqrt((df - 2) / df)          # stessa deviazione standard della normale
            ll = stats.t.logpdf(r / scale, df) - np.log(scale)
        else:
            ll = stats.norm.logpdf(r / s) - np.log(s)
        return -np.sum(w * ll) / w.sum()

    x0 = np.r_[np.log(np.sqrt(np.average(r ** 2, weights=w))), 0.0, 0.0] if kind != "t" else \
        np.r_[np.log(np.sqrt(np.average(r ** 2, weights=w))), 0.0, 0.0, np.log(10.0)]
    res = optimize.minimize(nll, x0, method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-5, "fatol": 1e-8})
    out = {"kind": kind, "c": res.x[:3]}
    if kind == "t":
        out["df"] = 2.0 + float(np.exp(res.x[3]))
    if kind == "empirica":
        z = r / _sd(res.x[:3], m, t)
        out["z"], out["zw"] = z, w / w.sum()
    return out


def sd(F: dict, m, t):
    return _sd(F["c"], m, t)


def prob_above(F: dict, m, t, threshold=0.0):
    """P(scarto vero > threshold) dato il pronostico m e il totale atteso t."""
    m, thr = np.asarray(m, float), np.asarray(threshold, float)
    s = sd(F, m, t)
    z = (thr - m) / s
    if F["kind"] == "t":
        df = F["df"]
        return 1 - stats.t.cdf(z / np.sqrt((df - 2) / df), df)
    if F["kind"] == "empirica":
        order = np.argsort(F["z"])
        zs, cw = F["z"][order], np.cumsum(F["zw"][order])
        idx = np.searchsorted(zs, np.atleast_1d(z), side="right")
        cdf = np.where(idx > 0, cw[np.clip(idx - 1, 0, len(cw) - 1)], 0.0)
        return 1 - cdf.reshape(np.shape(z))
    return 1 - stats.norm.cdf(z)


def walk_forward(df: pd.DataFrame, pred_col: str, total_col: str, seasons: list[int], kind: str,
                 hl_seasons: float = 2.0, window: int = 4) -> tuple[pd.Series, pd.Series, dict]:
    """Per ogni stagione S stima la distribuzione sulle `window` stagioni precedenti; restituisce
    probabilità di vittoria e deviazione standard per le partite di S."""
    y = (df["hpts"] - df["apts"]).to_numpy(float)
    r = y - df[pred_col].to_numpy(float)
    p = pd.Series(np.nan, index=df.index)
    s_ = pd.Series(np.nan, index=df.index)
    fits = {}
    for s in seasons:
        tr = (df["season"] < s) & (df["season"] >= s - window) & df[pred_col].notna() & df[total_col].notna()
        te = (df["season"] == s) & df[pred_col].notna() & df[total_col].notna()
        if tr.sum() < 500 or te.sum() == 0:
            continue
        w = 0.5 ** ((s - 1 - df.loc[tr, "season"].to_numpy()) / hl_seasons)
        F = fit(r[tr.to_numpy()], df.loc[tr, pred_col], df.loc[tr, total_col], w, kind)
        fits[s] = F
        p[te] = prob_above(F, df.loc[te, pred_col], df.loc[te, total_col])
        s_[te] = sd(F, df.loc[te, pred_col], df.loc[te, total_col])
    return p, s_, fits
