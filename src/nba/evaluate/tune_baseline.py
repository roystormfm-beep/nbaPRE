"""Ritaratura del baseline sulle sole stagioni di sviluppo (2014-15 → 2024-25), per un confronto pulito sul test.

Il modello v2 della pagina è stato tarato sul 2025-26, che qui è la stagione di test: i suoi numeri su quella
stagione sono quindi ottimistici. Qui provo variazioni di un parametro alla volta attorno ai valori della pagina,
scelgo per ciascun parametro il valore con l'errore quadratico medio più basso sullo scarto (versione con le
assenze "chi ha giocato") e verifico la combinazione finale. La deviazione standard (sigma) si sceglie dopo,
minimizzando il log loss sulle stesse stagioni.
"""
from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from nba.config import cfg, path
from nba.evaluate.history_inputs import SeasonInputs
from nba.models import baseline as B

GRID = {"halfLife": [20, 45, 60], "lambda_": [4, 16], "rosterK": [0.75, 1.75], "injK": [0.4, 0.8],
        "repl": [-2.0, -4.0], "b2b": [0.5, 1.5], "Hprior": [1.5, 3.0], "movCap": [15, 30]}


def configs_one_at_a_time() -> list[dict]:
    out = [{}]
    for k, vals in GRID.items():
        out += [{k: v} for v in vals]
    return out


def _season_errors(args) -> pd.DataFrame:
    season, configs = args
    si = SeasonInputs(season)
    rows = []
    for d in si.days():
        raw, today = si.raw_for_day(d)
        data = B.parse_data(raw)
        for ci, opts in enumerate(configs):
            ctx = B.build_from_data(data, today=d, **opts)
            for r in today.itertuples():
                g = B.find_game(ctx, d, r.away, r.home)
                if g is None:
                    continue
                p = B.predict(ctx, g)
                rows.append((ci, season, r.game_id, p["margin"], p["sd"], r.hpts - r.apts))
    return pd.DataFrame(rows, columns=["cfg", "season", "game_id", "margin_pred", "sd", "margin"])


def evaluate_configs(configs: list[dict], seasons: list[int], workers: int = 2) -> pd.DataFrame:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        parts = list(ex.map(_season_errors, [(s, configs) for s in seasons]))
    return pd.concat(parts, ignore_index=True)


def best_sigma(df: pd.DataFrame) -> tuple[float, pd.Series]:
    """Sigma che minimizza il log loss: sd_nuova = sqrt(sigma^2 + var_rating), var_rating = sd^2 - 10.5^2."""
    var_r = np.maximum(df["sd"].to_numpy() ** 2 - B.DEFAULTS["sigma"] ** 2, 0)
    m, y = df["margin_pred"].to_numpy(), (df["margin"] > 0).to_numpy()
    res = {}
    for s in np.arange(9.0, 15.01, 0.25):
        sd = np.sqrt(s * s + var_r)
        p = np.clip(np.array([B.Phi(x) for x in m / sd]), 1e-6, 1 - 1e-6)
        res[round(float(s), 2)] = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    ser = pd.Series(res)
    return float(ser.idxmin()), ser


def run() -> dict:
    dev = cfg()["seasons"]["dev"]
    configs = configs_one_at_a_time()
    err = evaluate_configs(configs, dev)
    err["se"] = (err["margin"] - err["margin_pred"]) ** 2
    summ = err.groupby("cfg")["se"].mean().pow(0.5).rename("rmse").to_frame()
    summ["config"] = [str(configs[i]) for i in summ.index]
    base = summ.loc[0, "rmse"]
    chosen = {}
    for k in GRID:
        cand = {0: B.DEFAULTS[k]}
        cand.update({i: configs[i][k] for i in range(1, len(configs)) if k in configs[i]})
        best_i = min(cand, key=lambda i: summ.loc[i, "rmse"])
        if best_i != 0 and summ.loc[best_i, "rmse"] < base - 0.005:
            chosen[k] = cand[best_i]
    final = evaluate_configs([{}, chosen], dev)
    final["se"] = (final["margin"] - final["margin_pred"]) ** 2
    rm = final.groupby("cfg")["se"].mean().pow(0.5)
    sigma, ll = best_sigma(final[final["cfg"] == 1])
    chosen_all = dict(chosen, sigma=sigma)
    out = {"griglia": summ.reset_index().to_dict("records"), "scelti": chosen_all,
           "rmse_pagina": float(rm.loc[0]), "rmse_ritarato": float(rm.loc[1]),
           "logloss_per_sigma": ll.round(5).to_dict()}
    pd.Series(chosen_all).to_json(path("processed") / "baseline_retuned_params.json")
    return out
