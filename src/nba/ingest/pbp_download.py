"""Scarica il play-by-play storico dal dataset pubblico shufinskiy/nba_data e lo converte in Parquet.

Fonti per stagione (anno di inizio):
  nbastatsv3  play-by-play NBA Stats v3 (1996→2025)
  nbastats    play-by-play NBA Stats v2 (1996→2024)
  cdnnba      play-by-play cdn.nba.com liveData (2020→2025): ha l'orario reale delle azioni
  pbpstats    possessi di pbpstats.com (2000→2024): ha la data della partita
"""
from __future__ import annotations

import io
import tarfile
import time
from pathlib import Path

import pandas as pd
import requests

from nba.config import cfg, path

# Colonne lette come testo per non perdere zeri iniziali o mescolare tipi
STR_COLS = {"gameId", "GAME_ID", "GAMEID", "personId", "teamId", "PLAYER1_ID", "PLAYER2_ID", "PLAYER3_ID",
            "PLAYER1_TEAM_ID", "PLAYER2_TEAM_ID", "PLAYER3_TEAM_ID", "clock", "PCTIMESTRING", "SCORE", "SCOREMARGIN",
            "timeActual", "qualifiers", "personIdsFilter", "descriptor", "subType", "actionType", "GAMEDATE",
            "description", "HOMEDESCRIPTION", "VISITORDESCRIPTION", "NEUTRALDESCRIPTION", "STARTTIME", "ENDTIME",
            "OPPONENT", "STARTTYPE", "EVENTS", "DESCRIPTION", "URL", "location", "teamTricode", "playerName",
            "playerNameI", "scoreHome", "scoreAway", "shotResult", "area", "areaDetail", "side", "edited",
            "PLAYER1_TEAM_ABBREVIATION", "PLAYER2_TEAM_ABBREVIATION", "PLAYER3_TEAM_ABBREVIATION",
            "PLAYER1_NAME", "PLAYER2_NAME", "PLAYER3_NAME", "WCTIMESTRING", "periodType", "possession",
            "officialId", "foulPersonalTotal", "foulTechnicalTotal", "isTargetScoreLastPeriod"}


def available() -> dict[str, str]:
    url = cfg()["sources"]["nba_data_list"]
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    out = {}
    for line in r.text.splitlines():
        if "=" in line:
            k, v = line.strip().split("=", 1)
            out[k] = v
    return out


def raw_file(kind: str, season: int) -> Path:
    return path("raw") / "pbp" / f"{kind}_{season}.parquet"


def fetch(kind: str, season: int, force: bool = False) -> Path | None:
    """Scarica un archivio e lo salva come Parquet. Restituisce None se la stagione non esiste per quella fonte."""
    out = raw_file(kind, season)
    if out.exists() and not force:
        return out
    name = f"{kind}_{season}"
    if name not in available():
        return None
    url = cfg()["sources"]["nba_data_raw"].format(name=name)
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:xz") as tf:
        member = next(m for m in tf.getmembers() if m.name.endswith(".csv"))
        f = tf.extractfile(member)
        head = pd.read_csv(f, nrows=0)
        dtypes = {c: "string" for c in head.columns if c in STR_COLS}
        f = tf.extractfile(member)
        df = pd.read_csv(f, dtype=dtypes, low_memory=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return out


def fetch_all(seasons: list[int], kinds: list[str] | None = None, force: bool = False) -> pd.DataFrame:
    kinds = kinds or cfg()["sources"]["kinds"]
    rows = []
    for s in seasons:
        for k in kinds:
            t0 = time.time()
            p = fetch(k, s, force=force)
            rows.append({"season": s, "kind": k, "file": str(p) if p else None,
                         "mb": round(p.stat().st_size / 1e6, 1) if p else None, "sec": round(time.time() - t0, 1)})
            print(f"  {k}_{s}: {'non disponibile' if p is None else 'ok'}", flush=True)
    return pd.DataFrame(rows)
