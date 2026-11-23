"""Arbitri di ogni partita dal riepilogo partita di ESPN (gameInfo.officials).

Uscita: data/external/espn/officials_{S}.parquet con espn_id, nome dell'arbitro, ordine (1 = capo arbitro).
Le designazioni sono pubbliche la mattina della partita, quindi sono un'informazione pre-partita.
"""
from __future__ import annotations

import pandas as pd

from nba.config import path
from nba.ingest.remote.http import get_json, pmap

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={e}"


def _one(eid: str) -> list[dict]:
    js = get_json(URL.format(e=eid))
    if not js:
        return []
    offs = ((js.get("gameInfo") or {}).get("officials")) or []
    rows = []
    for i, o in enumerate(offs):
        rows.append({"espn_id": str(eid), "official": o.get("fullName") or o.get("displayName"),
                     "order": o.get("order", i + 1), "position": ((o.get("position") or {}).get("name"))})
    return rows


def run(seasons: list[int]) -> list[str]:
    out_dir = path("external") / "espn"
    out_dir.mkdir(parents=True, exist_ok=True)
    log = []
    for s in seasons:
        sb = out_dir / f"scoreboard_{s}.parquet"
        if not sb.exists():
            log.append(f"{s}: scoreboard assente")
            continue
        b = pd.read_parquet(sb)
        ids = b[(b["season_type"] == 2) & b["completed"]]["event_id"].astype(str).tolist()
        res = pmap(_one, ids, workers=4)
        df = pd.DataFrame([r for e in ids for r in res.get(e) or []])
        df.to_parquet(out_dir / f"officials_{s}.parquet", index=False)
        cov = df["espn_id"].nunique() / max(len(ids), 1) if len(df) else 0
        log.append(f"{s}: arbitri per {cov:.1%} delle {len(ids)} partite, {df['official'].nunique() if len(df) else 0} arbitri")
        print(log[-1], flush=True)
    return log
