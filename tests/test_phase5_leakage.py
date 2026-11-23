"""Anti-leakage per la fase 5: Elo, LightGBM, ensemble, distribuzione dello scarto e modello sul mercato
non devono cambiare se cambiano i risultati (o le linee di chiusura) di partite future."""
import numpy as np
import pandas as pd
import pytest

from nba.config import path

pytestmark = pytest.mark.skipif(not (path("processed") / "components.parquet").exists(), reason="dati elaborati assenti")


def _comp():
    c = pd.read_parquet(path("processed") / "components.parquet")
    return c[c["season"] <= 2024].reset_index(drop=True)


def _scramble_from(df, season):
    df = df.copy()
    rng = np.random.default_rng(3)
    fut = df["season"] >= season
    df.loc[fut, "hpts"] = rng.integers(70, 160, fut.sum()).astype(float)
    df.loc[fut, "apts"] = rng.integers(70, 160, fut.sum()).astype(float)
    return df


def test_elo_only_past():
    from nba.models import elo
    g = elo.games([2022, 2023])
    d = "2024-01-15"
    a = elo.run(g)
    g2 = g.copy()
    fut = g2["date"] >= d
    g2.loc[fut, "hpts"] = 200
    g2.loc[fut, "apts"] = 50
    b = elo.run(g2)
    ids = set(g.loc[g["date"] <= d, "game_id"])          # anche le partite del giorno stesso
    aa = a[a["game_id"].isin(ids)].sort_values("game_id")["elo_diff"].to_numpy()
    bb = b[b["game_id"].isin(ids)].sort_values("game_id")["elo_diff"].to_numpy()
    assert np.allclose(aa, bb)


def test_gbm_only_previous_seasons():
    from nba.models import gbm
    c = _comp()
    a = gbm.fit_predict(c, "margin", [2022])
    b = gbm.fit_predict(_scramble_from(c, 2022), "margin", [2022])
    assert np.allclose(a["pred"].to_numpy(), b["pred"].to_numpy())


def test_ensemble_only_previous_seasons():
    from nba.models import ensemble as EN
    c = _comp()
    cols = ["m_players", "m_team", "m_base", "m_elo", "m_gbm"]
    a = EN.fit_predict(c, cols, "margin", [2023])
    b = EN.fit_predict(_scramble_from(c, 2023), cols, "margin", [2023])
    assert np.allclose(a["pred"].to_numpy(), b["pred"].to_numpy())


def test_distribution_only_previous_seasons():
    from nba.models import distribution as D
    c = _comp().dropna(subset=["m_players", "t_players"]).reset_index(drop=True)
    p1, s1, _ = D.walk_forward(c, "m_players", "t_players", [2023], "t")
    p2, s2, _ = D.walk_forward(_scramble_from(c, 2023), "m_players", "t_players", [2023], "t")
    m = c["season"] == 2023
    assert np.allclose(p1[m].to_numpy(), p2[m].to_numpy()) and np.allclose(s1[m].to_numpy(), s2[m].to_numpy())


def test_market_model_only_previous_seasons():
    from nba.evaluate import market_aware as MA
    c = _comp()
    c["m_open_info"] = c["m_players_open"]
    c["m_final"] = np.nan
    x = MA.table(c)
    _, a = MA.run(c, [2024], np.random.default_rng(0))
    # linee di chiusura del 2024-25 alterate: il movimento previsto (fatto all'apertura) non deve cambiare
    import nba.evaluate.market_aware as mod
    orig = mod.attach_market

    def fake(df):
        out = orig(df)
        m = out["season"] >= 2024
        out.loc[m, "close_spread_home"] = out.loc[m, "close_spread_home"] + 5
        return out
    mod.attach_market = fake
    try:
        _, b = MA.run(c, [2024], np.random.default_rng(0))
    finally:
        mod.attach_market = orig
    assert len(x) > 0
    assert np.allclose(a["pred"].to_numpy(), b["pred"].to_numpy())
