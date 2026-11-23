"""Test anti-leakage: un pronostico del giorno d non deve cambiare se cambiano partite e statistiche da d in poi.

L'unica eccezione dichiarata è la versione "chi_ha_giocato", che usa per costruzione chi è sceso in campo
nella partita stessa (limite superiore ottimistico, non un pronostico vero).
"""
import numpy as np
import pytest

from nba.config import path
from nba.models import baseline as B

pytestmark = pytest.mark.skipif(not (path("processed") / "games_2023.parquet").exists(), reason="dati elaborati assenti")


def _preds(si, d, no_inj):
    raw, today = si.raw_for_day(d)
    ctx = B.build(raw, today=d)
    return np.array([B.predict(ctx, B.find_game(ctx, d, r.away, r.home), no_inj=no_inj)["margin"] for r in today.itertuples()])


def _scramble_future(si, d, include_today):
    rng = np.random.default_rng(0)
    fut = si.games["date"] >= d if include_today else si.games["date"] > d
    si.games.loc[fut, "hpts"] = rng.integers(70, 160, fut.sum())
    si.games.loc[fut, "apts"] = rng.integers(70, 160, fut.sum())
    fpg = si.pg["date"] >= d if include_today else si.pg["date"] > d
    for c in ("pts", "fga", "fta", "ast", "trb", "tov", "stl", "blk", "fg3m"):
        si.pg.loc[fpg, c] = rng.integers(0, 40, fpg.sum())
    si.pg.loc[fpg, "sec"] = rng.integers(60, 2800, fpg.sum())


@pytest.mark.parametrize("d", ["2023-11-20", "2024-02-01"])
def test_future_does_not_change_predictions(d):
    from nba.evaluate.history_inputs import SeasonInputs
    si = SeasonInputs(2023)
    before = _preds(si, d, no_inj=True)
    _scramble_future(si, d, include_today=True)          # anche i risultati e le statistiche del giorno stesso
    after = _preds(si, d, no_inj=True)
    assert np.allclose(before, after, atol=1e-12)


def test_oracle_uses_only_today_participation():
    from nba.evaluate.history_inputs import SeasonInputs
    si = SeasonInputs(2023)
    d = "2024-01-15"
    before = _preds(si, d, no_inj=False)
    _scramble_future(si, d, include_today=False)         # solo dal giorno dopo in poi
    after = _preds(si, d, no_inj=False)
    assert np.allclose(before, after, atol=1e-12)


def test_inputs_only_past_dates():
    from nba.evaluate.history_inputs import SeasonInputs
    si = SeasonInputs(2023)
    d = "2024-01-15"
    raw, today = si.raw_for_day(d)
    assert all(r.split("|")[0] < d for r in raw["results"])
    # partite giocate per squadra prima di d >= presenze di qualsiasi giocatore di quella squadra
    gp = {}
    for r in raw["results"]:
        _, a, _, h, _, _ = r.split("|")
        gp[a] = gp.get(a, 0) + 1
        gp[h] = gp.get(h, 0) + 1
    for line in raw["pergame"][1:]:
        p = line.split(",")
        assert int(p[2]) <= gp[p[1]]
    assert raw["prev"][0] == "Player,Team,G,MP,BPM"     # stagione precedente: nota prima dell'inizio
