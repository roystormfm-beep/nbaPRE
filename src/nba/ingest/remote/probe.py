"""Prova di raggiungibilità delle fonti dal computer che esegue (GitHub Actions o il tuo PC).

Scrive data/external/probe.json: per ogni fonte esito HTTP, dimensione, tempo.
Cerca anche da quando esiste l'archivio degli injury report ufficiali (PDF con l'orario).
"""
from __future__ import annotations

import datetime as dt
import json
import time

from nba.config import path
from nba.ingest.remote.http import _session

STATS_H = {"Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "x-nba-stats-origin": "stats",
           "x-nba-stats-token": "true", "Accept": "application/json, text/plain, */*"}

TARGETS = {
    "stats.nba.com leaguegamelog": ("https://stats.nba.com/stats/leaguegamelog?Counter=10&Direction=DESC&LeagueID=00"
                                    "&PlayerOrTeam=T&Season=2026-27&SeasonType=Regular+Season&Sorter=DATE", STATS_H),
    "cdn.nba.com schedule": ("https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json", None),
    "cdn.nba.com boxscore 0022600200": ("https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022600200.json", None),
    "cdn.nba.com playbyplay 0022600200": ("https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_0022600200.json", None),
    "pbpstats get-games 2026-27": ("https://api.pbpstats.com/get-games/nba?Season=2026-27&SeasonType=Regular%2BSeason", None),
    "basketball-reference 2027 games": ("https://www.basketball-reference.com/leagues/NBA_2027_games-november.html", None),
    "official.nba.com referee": ("https://official.nba.com/referee-assignments/", None),
    "official.nba.com injury page": ("https://official.nba.com/nba-injury-report-2026-27-season/", None),
    "espn scoreboard": ("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", None),
}


def _try(url, headers=None, method="GET"):
    t0 = time.time()
    try:
        r = _session.request(method, url, headers=headers, timeout=25)
        return {"status": r.status_code, "bytes": len(r.content), "sec": round(time.time() - t0, 2),
                "type": r.headers.get("content-type", "")[:40]}
    except Exception as e:  # noqa: BLE001
        return {"status": None, "error": type(e).__name__, "sec": round(time.time() - t0, 2)}


def injury_archive() -> dict:
    """Prova URL di injury report in date diverse, con i due formati di orario noti."""
    out = {}
    for day in ["2019-01-15", "2020-01-15", "2021-01-15", "2021-12-15", "2022-01-15", "2022-11-15", "2023-01-15",
                "2023-11-15", "2024-01-15", "2024-11-15", "2025-01-15", "2025-11-15", "2026-01-15"]:
        hits = []
        for hh in ["05PM", "06PM", "01PM", "05_00PM", "05_30PM", "06_00PM", "01_00PM"]:
            url = f"https://ak-static.cms.nba.com/referee/injury/Injury-Report_{day}_{hh}.pdf"
            r = _try(url, method="HEAD")
            if r.get("status") == 200:
                hits.append(hh)
        out[day] = hits
    return out


def run() -> dict:
    res = {"when": dt.datetime.utcnow().isoformat() + "Z", "targets": {}}
    for k, (u, h) in TARGETS.items():
        res["targets"][k] = _try(u, h)
        print(k, res["targets"][k], flush=True)
    res["injury_archive"] = injury_archive()
    print("injury archive", res["injury_archive"], flush=True)
    with open(path("external") / "probe.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return res
