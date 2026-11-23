"""Prova delle fonti per la stagione in corso: salva esempi grezzi in data/external/probe_live/.

ESPN 'summary' (box score e play-by-play di una partita) e alcune chiamate dell'API di pbpstats.
"""
from __future__ import annotations

import gzip
import json

import pandas as pd

from nba.config import path
from nba.ingest.remote.http import get

SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={e}"
PBPSTATS = [
    ("pbpstats_games", "https://api.pbpstats.com/get-games/nba?Season=2026-27&SeasonType=Regular%20Season"),
    ("pbpstats_game_player", "https://api.pbpstats.com/get-game-stats?GameId={g}&Type=Player"),
    ("pbpstats_game_lineup", "https://api.pbpstats.com/get-game-stats?GameId={g}&Type=Lineup"),
    ("pbpstats_game_lineupopp", "https://api.pbpstats.com/get-game-stats?GameId={g}&Type=LineupOpponent"),
    ("pbpstats_possessions", "https://api.pbpstats.com/get-possessions/nba?GameId={g}"),
]


def _save(name: str, r) -> dict:
    out = path("external") / "probe_live"
    out.mkdir(parents=True, exist_ok=True)
    if r is None:
        return {"name": name, "status": None}
    with gzip.open(out / f"{name}.json.gz", "wb") as f:
        f.write(r.content)
    return {"name": name, "status": r.status_code, "bytes": len(r.content), "type": r.headers.get("content-type")}


def run() -> list[str]:
    sb = pd.read_parquet(path("external") / "espn" / "scoreboard_2026.parquet")
    done = sb[(sb["season_type"] == 2) & sb["completed"]].sort_values("date_utc")
    events = [done.iloc[-1]["event_id"], done.iloc[len(done) // 2]["event_id"]]
    res = []
    for e in events:
        res.append(_save(f"espn_summary_{e}", get(SUMMARY.format(e=e), ok404=False)))
    g = None
    r = get(PBPSTATS[0][1], ok404=False)
    res.append(_save(PBPSTATS[0][0], r))
    try:
        games = r.json()["results"]
        g = sorted(games, key=lambda x: x.get("Date", ""))[-1]["GameId"]
    except Exception:  # noqa: BLE001
        g = "0022600200"
    for name, url in PBPSTATS[1:]:
        res.append(_save(name, get(url.format(g=g), ok404=False, tries=2)))
    (path("external") / "probe_live" / "index.json").write_text(json.dumps({"game": g, "events": events, "results": res}, indent=1))
    return [json.dumps(x) for x in res]
