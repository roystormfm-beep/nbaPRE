"""Gradient boosting (LightGBM) su feature di squadra e di contesto, stimato stagione per stagione.

Per la stagione S si allena su tutte le stagioni precedenti e si pronostica S. Le feature sono tutte note prima
della palla a due: rating Elo, ritmo ed efficienza di squadra, riposo, viaggi, fusi, calendario, record,
altura, campo neutro, momento della stagione. Niente rating dei giocatori: quelli sono un altro componente.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import cfg

CTX = ["rest0", "rest1", "rest3", "three_in_four", "trav", "tz", "tz_east", "dens", "late_lowwin", "late_top", "wpct",
       "b2b_road"]
FEATURES = (["elo_diff", "m_team", "t_team", "pace_pred", "eff_home", "eff_away", "lg_eff", "lg_pace", "altitude",
             "neutral", "season_frac"] + [f"h_{c}" for c in CTX] + [f"a_{c}" for c in CTX])
DEFAULTS = dict(n_estimators=200, learning_rate=0.03, num_leaves=7, min_data_in_leaf=200, bagging_fraction=0.8,
                bagging_freq=1, feature_fraction=0.8, lambda_l2=10.0)


def fit_predict(df: pd.DataFrame, target: str, seasons: list[int], P: dict | None = None,
                min_train_seasons: int = 2) -> pd.DataFrame:
    import lightgbm as lgb
    P = {**DEFAULTS, **(P or {})}
    X = df[FEATURES].astype(float)
    # si stima la correzione rispetto ai rating di squadra: gli alberi non sanno estrapolare a livelli di punteggio mai visti
    base = (df["m_team"] if target == "margin" else df["t_team"]).astype(float)
    y = (df["hpts"] - df["apts"] if target == "margin" else df["hpts"] + df["apts"]).astype(float) - base
    out = []
    for s in seasons:
        tr = df["season"] < s
        if df.loc[tr, "season"].nunique() < min_train_seasons:
            continue
        te = df["season"] == s
        params = {k: v for k, v in P.items() if k != "n_estimators"}
        params.update(objective="regression", seed=cfg()["seed"], verbose=-1, num_threads=1, deterministic=True)
        m = lgb.train(params, lgb.Dataset(X[tr], y[tr]), num_boost_round=int(P["n_estimators"]))
        o = df.loc[te, ["game_id", "season"]].copy()
        o["pred"] = base[te].to_numpy() + m.predict(X[te])
        out.append(o)
        fit_predict.last_model = m
    return pd.concat(out, ignore_index=True)


def importance(model) -> pd.Series:
    g = model.feature_importance(importance_type="gain")
    return pd.Series(g / g.sum(), index=FEATURES).sort_values(ascending=False)
