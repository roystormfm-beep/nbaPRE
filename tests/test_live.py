"""Fase 6: lettore del play-by-play ESPN e gestione delle partite non ancora giocate."""
import gzip
import json

import numpy as np
import pandas as pd
import pytest

from nba.config import path

SAMPLES = path("external") / "probe_live"


@pytest.mark.skipif(not SAMPLES.exists(), reason="esempi ESPN assenti")
@pytest.mark.parametrize("event", ["401910035", "401909288"])
def test_espn_pbp_rebuilds_game(event):
    from nba.ingest import espn_pbp as E
    from nba.ingest.stints import build_season
    js = json.load(gzip.open(SAMPLES / f"espn_summary_{event}.json.gz"))
    gid = "2" + event
    ev, bx, fs = E.events(js, gid), E.box(js), E.final_score(js)
    tm = E.teams_of(js)
    home = [v[0] for v in tm.values() if v[1] == "home"][0]
    away = [v[0] for v in tm.values() if v[1] == "away"][0]
    st, iss, pg = build_season(ev, pd.DataFrame([{"game_id": gid, "home": home, "away": away}]))
    assert st["hpts"].sum() == fs["hpts"] and st["apts"].sum() == fs["apts"]       # punteggio dal play-by-play
    assert ((st["hn"] == 5) & (st["an"] == 5)).all() and len(iss) == 0               # sempre 5 contro 5
    assert np.allclose(pg.groupby("team")["min"].sum(), 240.0)                      # 240 minuti per squadra
    m = pg.merge(bx, left_on=["team", "player"], right_on=["team", "espn_id"])
    assert (m["min"] - m["min_box"]).abs().max() < 1.0                              # minuti come nel box score ESPN
    assert (m["pts"] == m["pts_box"]).all()                                          # punti come nel box score ESPN


def test_records_with_unplayed_games():
    from nba.features.context import team_records
    g = pd.DataFrame({"game_id": ["1", "2", "3"], "season": 2026, "date": ["2026-11-01", "2026-11-03", "2026-11-05"],
                      "home": ["BOS", "BOS", "BOS"], "away": ["NYK", "MIA", "CHI"],
                      "hpts": [110.0, 90.0, np.nan], "apts": [100.0, 95.0, np.nan]})
    r = team_records(g).set_index(["game_id", "team"])
    assert r.loc[("3", "BOS"), "g_before"] == 2 and r.loc[("3", "BOS"), "wpct"] == 0.5   # 1 vinta su 2 prima della 3a
    assert r.loc[("2", "BOS"), "wpct"] == 1.0


def test_elo_ignores_unplayed():
    from nba.models import elo
    g = pd.DataFrame({"game_id": ["1", "2"], "season": 2026, "date": ["2026-11-01", "2026-11-02"],
                      "home": ["BOS", "BOS"], "away": ["NYK", "MIA"], "hpts": [110.0, np.nan], "apts": [100.0, np.nan],
                      "neutral": False})
    e = elo.run(g)
    assert len(e) == 2 and np.isfinite(e["elo_diff"]).all()
