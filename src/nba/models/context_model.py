"""Secondo stadio: correzione di contesto sopra il modello giocatori.

Per ogni stagione S si stima una regressione ridge sugli scarti (risultato vero meno pronostico del modello
giocatori) delle sole stagioni precedenti, con più peso alle più recenti; poi la si applica alle partite di S.
Variabili: vantaggio campo generale e per squadra (con shrinkage), riposo, viaggi, fusi, calendario, altura,
fine stagione; per i totali anche gli arbitri (effetto di ciascun arbitro, con shrinkage).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import TEAMS
from nba.features.context import design

DEFAULTS = dict(lam=200.0, lam_team=2000.0, lam_ref=3000.0, hl_seasons=2.0, min_season=2014)


def _ref_matrix(x: pd.DataFrame, refs: pd.DataFrame | None, names: list[str]) -> np.ndarray:
    if refs is None or not names:
        return np.zeros((len(x), 0))
    ix = {n: i for i, n in enumerate(names)}
    M = np.zeros((len(x), len(names)))
    pos = {g: i for i, g in enumerate(x["game_id"])}
    for g, o in zip(refs["game_id"], refs["official"]):
        i, j = pos.get(g), ix.get(o)
        if i is not None and j is not None:
            M[i, j] = 1.0
    return M


def fit_predict(df: pd.DataFrame, target: str, seasons: list[int], P: dict | None = None,
                refs: pd.DataFrame | None = None, groups: set[str] | None = None) -> pd.DataFrame:
    """df: una riga per partita con season, base (pronostico di partenza), y (risultato) e il contesto.
    target: 'margin' o 'total'. groups: gruppi di variabili da usare (None = tutti)."""
    P = {**DEFAULTS, **(P or {})}
    teams = TEAMS if (groups is None or "squadre" in groups) and target == "margin" else None
    X, names = design(df, target, teams)
    if groups is not None:
        keep = [i for i, n in enumerate(names) if _group(n) in groups]
        X, names = X[:, keep], [names[i] for i in keep]
    use_refs = refs is not None and target == "total" and (groups is None or "arbitri" in groups)
    out = []
    for s in seasons:
        tr = (df["season"] < s) & (df["season"] >= P["min_season"])
        te = df["season"] == s
        if tr.sum() < 500:
            continue
        ref_names = sorted(set(refs.loc[refs["game_id"].isin(df.loc[tr, "game_id"]), "official"])) if use_refs else []
        Xtr = np.column_stack([X[tr.to_numpy()], _ref_matrix(df[tr], refs, ref_names)]) if ref_names else X[tr.to_numpy()]
        Xte = np.column_stack([X[te.to_numpy()], _ref_matrix(df[te], refs, ref_names)]) if ref_names else X[te.to_numpy()]
        lam = np.array([P["lam_team"] if n.startswith("casa_") else 0.0 if n in ("costante",) else P["lam"] for n in names]
                       + [P["lam_ref"]] * len(ref_names))
        w = 0.5 ** ((s - 1 - df.loc[tr, "season"].to_numpy()) / P["hl_seasons"])
        r = (df.loc[tr, "y"] - df.loc[tr, "base"]).to_numpy(float)
        A = (Xtr.T * w) @ Xtr + np.diag(lam + 1e-6)
        beta = np.linalg.solve(A, (Xtr.T * w) @ r)
        pred = df.loc[te, "base"].to_numpy(float) + Xte @ beta
        o = df.loc[te, ["game_id", "season"]].copy()
        o["pred"] = pred
        o["correction"] = Xte @ beta
        out.append(o)
        if s == max(seasons):
            fit_predict.last_coef = dict(zip(names + [f"arbitro_{n}" for n in ref_names], beta))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def _group(name: str) -> str:
    if name.startswith("casa_"):
        return "squadre"
    if name in ("vantaggio_campo", "costante"):
        return "base"
    if any(k in name for k in ("rest0", "rest1", "rest3", "three_in_four", "dens", "b2b_road")):
        return "riposo"
    if any(k in name for k in ("trav", "tz")):
        return "viaggi"
    if name == "altura":
        return "altura"
    if "late_" in name:
        return "fine_stagione"
    if name == "avanzamento_stagione":
        return "stagione"
    return "altro"
