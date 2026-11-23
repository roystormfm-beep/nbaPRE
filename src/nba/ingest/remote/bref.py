"""Basketball-Reference: statistiche avanzate di fine stagione (BPM, minuti) per ogni stagione.

Serve come prior "stagione precedente" (informazione nota prima dell'inizio della stagione successiva).
Il sito limita la frequenza delle richieste: una pagina ogni ~4 secondi.
Uscita: data/external/bref/advanced_{S}.parquet (S = anno di inizio, 2025 = 2025-26).
"""
from __future__ import annotations

import io
import time

import pandas as pd

from nba.config import path
from nba.ingest.remote.http import get

URL = "https://www.basketball-reference.com/leagues/NBA_{y}_{kind}.html"


def season_table(s: int, kind: str = "advanced") -> pd.DataFrame | None:
    r = get(URL.format(y=s + 1, kind=kind), pause=4.0, timeout=60)
    if r is None:
        return None
    html = r.text.replace("<!--", "").replace("-->", "")   # alcune tabelle sono dentro commenti HTML
    tables = pd.read_html(io.StringIO(html))
    t = max(tables, key=len)
    t = t[t["Player"] != "Player"].copy()                    # righe di intestazione ripetute
    if "Tm" in t.columns and "Team" not in t.columns:
        t = t.rename(columns={"Tm": "Team"})
    t = t.loc[:, ~t.columns.astype(str).str.startswith("Unnamed")]
    t["Player"] = t["Player"].astype(str).str.replace("*", "", regex=False).str.strip()
    t["season"] = s
    return t


def run(seasons: list[int]) -> list[str]:
    out_dir = path("external") / "bref"
    out_dir.mkdir(parents=True, exist_ok=True)
    log = []
    for s in seasons:
        for kind in ("advanced", "per_game"):
            try:
                t = season_table(s, kind)
            except Exception as e:  # noqa: BLE001
                t = None
                log.append(f"{s} {kind}: errore {e}")
            if t is None or t.empty:
                log.append(f"{s} {kind}: non disponibile")
                continue
            t.astype(str).to_parquet(out_dir / f"{kind}_{s}.parquet", index=False)
            log.append(f"{s} {kind}: {len(t)} righe")
            print(log[-1], flush=True)
            time.sleep(4)
    return log
