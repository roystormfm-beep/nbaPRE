"""Test di lettura dei formati ESPN e Basketball-Reference su esempi costruiti a mano (senza rete)."""
import io

import pandas as pd

from nba.ingest.remote import espn


def test_scoreboard_row(monkeypatch):
    js = {"events": [{"id": "401810433", "date": "2026-01-16T00:00Z", "season": {"year": 2026, "type": 2},
                      "competitions": [{"neutralSite": False, "venue": {"fullName": "Kia Center", "address": {"city": "Orlando", "state": "FL"}},
                                        "status": {"type": {"completed": True}},
                                        "competitors": [{"homeAway": "home", "team": {"abbreviation": "ORL"}, "score": "118"},
                                                        {"homeAway": "away", "team": {"abbreviation": "MEM"}, "score": "111"}]}]}]}
    monkeypatch.setattr(espn, "get_json", lambda url, **k: js)
    rows = espn._sb_rows("20260115")
    assert rows[0]["home"] == "ORL" and rows[0]["away"] == "MEM"
    assert rows[0]["hpts"] == 118 and rows[0]["completed"] and rows[0]["season_type"] == 2


def test_odds_row(monkeypatch):
    js = {"items": [{"provider": {"id": "40", "name": "DraftKings", "priority": 1}, "details": "ORL -5.5",
                     "spread": -5.5, "overUnder": 227.5,
                     "homeTeamOdds": {"favorite": True, "moneyLine": -230,
                                      "open": {"pointSpread": {"american": "-4.5"}, "moneyLine": {"american": "-180"}},
                                      "close": {"pointSpread": {"american": "-5.5"}, "moneyLine": {"american": "-230"}}},
                     "awayTeamOdds": {"moneyLine": 190, "open": {"pointSpread": {"american": "+4.5"}, "moneyLine": {"american": "+150"}}},
                     "open": {"total": {"american": "230.5"}}, "close": {"total": {"alternateDisplayValue": "227.5"}}}]}
    monkeypatch.setattr(espn, "get_json", lambda url, **k: js)
    r = espn._odds_rows("401810433")[0]
    assert r["open_home_spread"] == -4.5 and r["close_home_spread"] == -5.5
    assert r["open_away_ml"] == 150 and r["open_total"] == 230.5 and r["close_total"] == 227.5
    assert r["provider"] == "DraftKings" and r["home_ml"] == -230


def test_val_formats():
    assert espn._val("+4.5") == 4.5 and espn._val("EVEN") == 100 and espn._val("o227.5") == 227.5
    assert espn._val({"american": "-110"}) == -110 and espn._val(None) is None


def test_bref_table_parsing(monkeypatch):
    from nba.ingest.remote import bref

    html = """<html><body><!--<table id="advanced"><thead><tr><th>Rk</th><th>Player</th><th>Team</th><th>G</th><th>MP</th><th>BPM</th></tr></thead>
    <tbody><tr><td>1</td><td>Nikola Jokić*</td><td>DEN</td><td>70</td><td>2500</td><td>13.2</td></tr>
    <tr><td>Rk</td><td>Player</td><td>Team</td><td>G</td><td>MP</td><td>BPM</td></tr>
    <tr><td>2</td><td>Jalen Brunson</td><td>NYK</td><td>75</td><td>2600</td><td>5.1</td></tr></tbody></table>--></body></html>"""

    class R:
        text = html
    monkeypatch.setattr(bref, "get", lambda *a, **k: R())
    t = bref.season_table(2025)
    assert list(t["Player"]) == ["Nikola Jokić", "Jalen Brunson"] and t["season"].iat[0] == 2025
