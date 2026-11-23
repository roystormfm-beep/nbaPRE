"""Valutazione della fase 4: contesto per lo scarto e modello dei totali, sulle stagioni di sviluppo."""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import path
from nba.evaluate.metrics import attach_market
from nba.models import context_model as CM

EVAL = [2018, 2019, 2020, 2021, 2022, 2023, 2024]


def base_table() -> pd.DataFrame:
    """Pronostico del modello giocatori (fase 3): con injury report dal 2018-19, senza prima."""
    proc = path("processed")
    a = pd.read_parquet(proc / "player_model_report_predictions.parquet")
    b = pd.read_parquet(proc / "player_model_noreport_2014_2017.parquet")
    cols = ["game_id", "season", "date", "home", "away", "hpts", "apts", "margin_pred", "total_pred", "pm_mu", "pm_pace",
            "eff_sum", "eff_diff"]
    base = pd.concat([b[cols], a[cols]], ignore_index=True)
    ctx = pd.read_parquet(proc / "context.parquet").drop(columns=["season", "date", "home", "away"])
    return base.merge(ctx, on="game_id", how="inner")


def report_games() -> set:
    has = set()
    for s in EVAL:
        f = path("external") / "injury" / f"needed_{s}.csv"
        if f.exists():
            has |= set(pd.read_csv(f, dtype={"game_id": str})["game_id"].str.zfill(10))
    return has


def margin_eval(groups_list: dict, P: dict | None = None) -> pd.DataFrame:
    df = base_table()
    df["y"] = df["hpts"] - df["apts"]
    df["base"] = df["margin_pred"]
    rows = []
    has = report_games()
    for label, groups in groups_list.items():
        pr = CM.fit_predict(df, "margin", EVAL, P, groups=groups)
        x = attach_market(df.merge(pr[["game_id", "pred"]], on="game_id"))
        x = x[x["game_id"].isin(has)].dropna(subset=["close_spread_home"])
        y = x["hpts"] - x["apts"]
        rows.append({"variante": label, "partite": len(x), "MAE": (y - x["pred"]).abs().mean(),
                     "MAE_base": (y - x["base"]).abs().mean(), "MAE_mercato": (y + x["close_spread_home"]).abs().mean(),
                     "RMSE": np.sqrt(((y - x["pred"]) ** 2).mean())})
    return pd.DataFrame(rows)
