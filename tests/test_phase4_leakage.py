"""Anti-leakage per la fase 4: record di squadra, modello di ritmo/efficienza e correzione di contesto
non devono cambiare se cambiano i risultati di partite future."""
import numpy as np
import pandas as pd
import pytest

from nba.config import path

pytestmark = pytest.mark.skipif(not (path("processed") / "games_2023.parquet").exists(), reason="dati elaborati assenti")


def _scramble(df, mask, cols=("hpts", "apts")):
    rng = np.random.default_rng(1)
    df = df.copy()
    for c in cols:
        df.loc[mask, c] = rng.integers(70, 160, mask.sum())
    return df


def test_team_records_only_past():
    from nba.features.context import team_records
    g = pd.read_parquet(path("processed") / "games_2023.parquet").dropna(subset=["date", "hpts"]).assign(season=2023)
    d = "2024-01-15"
    before = team_records(g)
    after = team_records(_scramble(g, g["date"] >= d))            # anche le partite del giorno stesso
    ids = set(g.loc[g["date"] <= d, "game_id"])
    a = before[before["game_id"].isin(ids)].sort_values(["game_id", "team"])["wpct"].to_numpy()
    b = after[after["game_id"].isin(ids)].sort_values(["game_id", "team"])["wpct"].to_numpy()
    assert np.allclose(a, b)


def test_team_ratings_only_past():
    from nba.models.team_ratings import DEFAULTS, fit, game_table
    g = game_table([2022, 2023])
    cut = pd.Timestamp("2024-01-15")
    f1 = fit(g, cut, DEFAULTS)
    g2 = _scramble(g, g["date"] >= cut)
    g2.loc[g2["date"] >= cut, "poss"] = 120.0
    g2.loc[g2["date"] >= cut, "poss48"] = 120.0
    f2 = fit(g2, cut, DEFAULTS)
    for k in ("lg_pace", "lg_eff", "h"):
        assert np.isclose(f1[k], f2[k])
    for k in ("pace", "O", "D"):
        assert np.allclose(f1[k], f2[k])


def test_context_correction_only_previous_seasons():
    from nba.evaluate.phase4 import base_table
    from nba.models import context_model as CM
    df = base_table()
    df["y"] = (df["hpts"] - df["apts"]).astype(float)
    df["base"] = df["margin_pred"]
    p1 = CM.fit_predict(df, "margin", [2022])
    df2 = df.copy()
    fut = df2["season"] >= 2022
    df2.loc[fut, "y"] = np.random.default_rng(2).normal(0, 30, fut.sum())
    p2 = CM.fit_predict(df2, "margin", [2022])
    assert np.allclose(p1["pred"].to_numpy(), p2["pred"].to_numpy())
