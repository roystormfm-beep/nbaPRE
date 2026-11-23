"""Play-by-play e box score dal 'summary' di ESPN, nello stesso formato di eventi delle altre fonti.

Serve per la stagione in corso, quando cdn.nba.com e stats.nba.com non rispondono dai server cloud.
Regole ESPN (verificate sugli esempi in data/external/probe_live):
  - tiri: shootingPlay; segnato se scoringPlay; da tre se pointsAttempted == 3; participants = [tiratore, assist]
    se segnato, [tiratore, stoppatore] se nel testo c'è "blocks";
  - tiri liberi: tipo "Free Throw ...", segnato se scoringPlay;
  - palle perse: tipo con "Turnover"; participants = [chi la perde, chi ruba] se nel testo c'è "steals";
  - rimbalzi: "Offensive Rebound" / "Defensive Rebound", senza participants se di squadra;
  - sostituzioni: participants = [chi entra, chi esce];
  - la squadra di ogni giocatore si prende dal box score (più affidabile del campo "team" dell'azione).
Gli id dei giocatori restano quelli ESPN: la conversione agli id NBA si fa dopo (nba.live.idmap).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import team as norm_team
from nba.ingest.events import EVENT_COLS


def _clock(s) -> float:
    s = str(s or "0")
    if ":" in s:
        m, x = s.split(":", 1)
        return float(m) * 60 + float(x)
    try:
        return float(s)
    except ValueError:
        return 0.0


def _ids(p) -> list[int]:
    out = []
    for x in p.get("participants") or []:
        try:
            out.append(int((x.get("athlete") or {}).get("id")))
        except (TypeError, ValueError):
            out.append(0)
    return out


def teams_of(js: dict) -> dict:
    """{espn_team_id: (sigla, 'home'|'away')}"""
    out = {}
    for c in js["header"]["competitions"][0]["competitors"]:
        out[str(c["team"]["id"])] = (norm_team(c["team"]["abbreviation"]), c["homeAway"])
    return out


def box(js: dict) -> pd.DataFrame:
    """Box score ESPN: una riga per giocatore (anche chi non ha giocato)."""
    tm = teams_of(js)
    rows = []
    for blk in js["boxscore"].get("players", []):
        t = tm.get(str(blk["team"]["id"]), (norm_team(blk["team"].get("abbreviation", "")), ""))[0]
        st = blk["statistics"][0]
        keys = st.get("keys") or []
        for a in st.get("athletes", []):
            vals = dict(zip(keys, a.get("stats") or []))
            r = {"team": t, "espn_id": int(a["athlete"]["id"]), "name": a["athlete"].get("displayName"),
                 "starter": bool(a.get("starter")), "dnp": bool(a.get("didNotPlay")) or not a.get("stats"),
                 "min_box": pd.to_numeric(vals.get("minutes"), errors="coerce"),
                 "pts_box": pd.to_numeric(vals.get("points"), errors="coerce")}
            rows.append(r)
    return pd.DataFrame(rows)


def events(js: dict, game_id: str) -> pd.DataFrame:
    """Eventi nel formato comune (EVENT_COLS), con gli id ESPN dei giocatori."""
    tm = teams_of(js)
    bx = box(js)
    pteam = dict(zip(bx["espn_id"], bx["team"])) if len(bx) else {}
    rows = []

    def add(p, sec, period, ordv, player, kind, is3=False, presence=True, team=None):
        t = pteam.get(player) if player else None
        if t is None:
            t = team or ""
        rows.append((game_id, period, sec, ordv, t, int(player or 0), kind, bool(is3), bool(presence)))

    for p in js.get("plays") or []:
        typ = str((p.get("type") or {}).get("text") or "")
        tl = typ.lower()
        text = str(p.get("text") or "").lower()
        period = int((p.get("period") or {}).get("number") or 0)
        if period <= 0:
            continue
        sec = _clock((p.get("clock") or {}).get("displayValue"))
        try:
            o = int(p.get("sequenceNumber")) * 10
        except (TypeError, ValueError):
            o = len(rows) * 10
        team = tm.get(str((p.get("team") or {}).get("id")), ("", ""))[0]
        ids = _ids(p)
        p0 = ids[0] if ids else 0
        if tl == "substitution":
            if len(ids) >= 2:
                add(p, sec, period, o, ids[1], "SUBOUT", presence=False, team=team)
                add(p, sec, period, o + 1, ids[0], "SUBIN", presence=False, team=team)
            continue
        if tl.startswith("free throw"):
            if p0:
                add(p, sec, period, o, p0, "FTM" if p.get("scoringPlay") else "FTX", team=team)
            continue
        if p.get("shootingPlay"):
            if not p0:
                continue
            is3 = (p.get("pointsAttempted") == 3) or ("three point" in text)
            if p.get("scoringPlay"):
                add(p, sec, period, o, p0, "FGM", is3, team=team)
                if len(ids) >= 2 and ids[1]:
                    add(p, sec, period, o + 1, ids[1], "AST")
            else:
                add(p, sec, period, o, p0, "FGX", is3, team=team)
                if len(ids) >= 2 and ids[1] and "block" in text:
                    add(p, sec, period, o + 1, ids[1], "BLK")
            continue
        if "rebound" in tl:
            kind = "OREB" if "offensive" in tl else "DREB"
            if p0:
                add(p, sec, period, o, p0, kind)
            else:
                add(p, sec, period, o, 0, kind, presence=False, team=team)
            continue
        if "turnover" in tl:
            if p0:
                add(p, sec, period, o, p0, "TOV")
            else:
                add(p, sec, period, o, 0, "TOV", presence=False, team=team)
            if len(ids) >= 2 and ids[1] and "steal" in text:
                add(p, sec, period, o + 1, ids[1], "STL")
            continue
        if "technical" in tl:
            if p0:
                add(p, sec, period, o, p0, "TECH", presence=False)
            continue
        if "foul" in tl:
            if p0:
                add(p, sec, period, o, p0, "PF")
            continue
        if tl == "jumpball":
            for k, pid in enumerate(ids[:2]):
                if pid:
                    add(p, sec, period, o + k, pid, "JUMP")
            continue
        if tl in ("end period", "end game"):
            add(p, sec, period, o, 0, "PEND", presence=False)
            continue
        if p0 and pteam.get(p0):
            add(p, sec, period, o, p0, "OTHER")
    ev = pd.DataFrame(rows, columns=EVENT_COLS)
    ev["side"] = ""
    return ev.sort_values(["period", "ord"], kind="stable").reset_index(drop=True)


def final_score(js: dict) -> dict:
    out = {"periods": None}
    comp = js["header"]["competitions"][0]
    for c in comp["competitors"]:
        sc = pd.to_numeric(c.get("score"), errors="coerce")
        out["hpts" if c["homeAway"] == "home" else "apts"] = sc
        ls = c.get("linescores") or []
        out["periods"] = max(out["periods"] or 0, len(ls)) or None
    return out
