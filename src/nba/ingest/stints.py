"""Ricostruisce i quintetti in campo (stint) e le statistiche per giocatore e partita dagli eventi normalizzati.

Uno stint è un intervallo di gioco in cui i dieci giocatori in campo non cambiano.
I quintetti di inizio periodo non sono scritti nel play-by-play: si deducono dai giocatori che compaiono
in campo (tiri, rimbalzi, falli...) o che escono prima di essere entrati.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

STAT_KINDS = ["FGM", "FGX", "FTM", "FTX", "OREB", "DREB", "TOV", "STL", "BLK", "AST", "PF"]


def period_len(p: int) -> float:
    return 720.0 if p <= 4 else 300.0


def period_start(p: int) -> float:
    return (p - 1) * 720.0 if p <= 4 else 2880.0 + (p - 5) * 300.0


def _assign_rebounds(ev: pd.DataFrame, home: str, away: str) -> pd.DataFrame:
    """Rimbalzi 'REB' (NBA Stats v2): offensivo se la squadra è quella che ha sbagliato l'ultimo tiro."""
    kinds = ev["kind"].to_numpy().copy()
    teams = ev["team"].to_numpy().copy()
    side = ev["side"].to_numpy() if "side" in ev else np.full(len(ev), "")
    last_miss_team = ""
    for i in range(len(kinds)):
        if teams[i] == "" and side[i] in ("H", "A"):
            teams[i] = home if side[i] == "H" else away
        k = kinds[i]
        if k in ("FGX", "FTX"):
            last_miss_team = teams[i]
        elif k == "REB":
            kinds[i] = "OREB" if teams[i] == last_miss_team and last_miss_team else "DREB"
    ev = ev.copy()
    ev["kind"] = kinds
    ev["team"] = teams
    return ev


def _starters(rows: list, team: str, prev_end: set) -> tuple[list, str]:
    """Deduce i 5 titolari di un periodo per una squadra. Restituisce (giocatori, esito)."""
    starters, subbed_in, seen_out = [], set(), set()
    first_in = {}   # giocatore -> indice del primo ingresso (SUBIN) senza un'uscita precedente
    for i, r in enumerate(rows):
        if r.team != team or r.player <= 0:
            continue
        if r.kind == "SUBIN":
            if r.player not in seen_out and r.player not in first_in:
                first_in[r.player] = i
            subbed_in.add(r.player)
        elif r.kind == "SUBOUT":
            if r.player not in subbed_in and r.player not in starters:
                starters.append(r.player)
            seen_out.add(r.player)
        elif r.presence and r.player not in subbed_in and r.player not in starters:
            starters.append(r.player)
    if len(starters) > 5:
        # chi "entra" più avanti senza essere mai uscito non era titolare: il suo primo evento è
        # registrato prima della sostituzione (fonte fuori sequenza)
        starters = [p for p in starters if p not in first_in] + [p for p in starters if p in first_in]
        keep = [p for p in starters if p not in first_in]
        if len(keep) >= 5:
            starters = keep if len(keep) == 5 else starters
        else:
            starters = keep + [p for p in starters if p in first_in][: 5 - len(keep)]
    status = "ok"
    if len(starters) < 5:
        # giocatore rimasto in campo tutto il periodo senza eventi: lo cerco tra chi chiudeva il periodo prima
        cand = [p for p in prev_end if p not in starters and p not in subbed_in]
        need = 5 - len(starters)
        if len(cand) == need:
            starters += cand
            status = "imputato"
        else:
            status = f"incompleto_{len(starters)}"
    elif len(starters) > 5:
        status = f"eccesso_{len(starters)}"
        starters = starters[:5]
    return starters, status


def build_game(ev: pd.DataFrame, game_id: str, home: str, away: str):
    # ordine per tempo di gioco (a parità di cronometro resta l'ordine della fonte): evita stint sovrapposti
    # quando la fonte registra una sostituzione fuori sequenza
    ev = ev.sort_values(["period", "sec_left", "ord"], ascending=[True, False, True], kind="stable")
    ev = _assign_rebounds(ev, home, away)
    stints, issues = [], []
    pstats = defaultdict(lambda: defaultdict(float))   # (team, player) -> statistiche
    psec = defaultdict(float)
    prev_end = {home: set(), away: set()}
    for p, pev in ev.groupby("period", sort=True):
        rows = list(pev.itertuples(index=False))
        on = {}
        for t in (home, away):
            st, status = _starters(rows, t, prev_end[t])
            on[t] = set(st)
            if status != "ok":
                issues.append({"game_id": game_id, "period": p, "team": t, "issue": status})
        L, P0 = period_len(p), period_start(p)
        cur = _new_stint(game_id, p, P0, on, home, away)
        for r in rows:
            t = r.team
            if r.kind in ("SUBOUT", "SUBIN") and t in on:
                el = P0 + (L - r.sec_left)
                if el > cur["start"] or cur["changed"]:
                    pass
                _close(cur, el, stints, psec, home, away)
                if r.kind == "SUBOUT":
                    if r.player in on[t]:
                        on[t].discard(r.player)
                    else:
                        issues.append({"game_id": game_id, "period": p, "team": t, "issue": "esce_non_in_campo"})
                else:
                    if r.player in on[t]:
                        issues.append({"game_id": game_id, "period": p, "team": t, "issue": "entra_gia_in_campo"})
                    on[t].add(r.player)
                cur = _new_stint(game_id, p, el, on, home, away)
                continue
            if r.kind in STAT_KINDS and t in (home, away):
                side = "h" if t == home else "a"
                k = r.kind
                if k == "FGM":
                    pts = 3 if r.is3 else 2
                    cur[side + "pts"] += pts
                    cur[side + "fga"] += 1
                    if r.is3:
                        cur[side + "fg3a"] += 1
                        cur[side + "fg3m"] += 1
                elif k == "FGX":
                    cur[side + "fga"] += 1
                    if r.is3:
                        cur[side + "fg3a"] += 1
                elif k == "FTM":
                    cur[side + "pts"] += 1
                    cur[side + "fta"] += 1
                    cur[side + "ftm"] += 1
                elif k == "FTX":
                    cur[side + "fta"] += 1
                elif k == "OREB":
                    cur[side + "oreb"] += 1
                elif k == "TOV":
                    cur[side + "tov"] += 1
                if r.player > 0:
                    s = pstats[(t, r.player)]
                    s[k] += 1
                    if k in ("FGM", "FGX") and r.is3:
                        s["3PA"] += 1
                        if k == "FGM":
                            s["3PM"] += 1
        _close(cur, P0 + L, stints, psec, home, away)
        prev_end = {t: set(on[t]) for t in (home, away)}
    return stints, issues, pstats, psec


def _new_stint(game_id, p, start, on, home, away):
    return {"game_id": game_id, "period": p, "start": start, "home_ids": tuple(sorted(on[home])),
            "away_ids": tuple(sorted(on[away])), "hpts": 0, "apts": 0, "hfga": 0, "afga": 0, "hfta": 0, "afta": 0,
            "horeb": 0, "aoreb": 0, "htov": 0, "atov": 0, "hfg3a": 0, "afg3a": 0, "hfg3m": 0, "afg3m": 0,
            "hftm": 0, "aftm": 0, "changed": False}


def _close(cur, end, stints, psec, home, away):
    cur["end"] = max(end, cur["start"])
    dur = cur["end"] - cur["start"]
    has_events = any(cur[k] for k in ("hpts", "apts", "hfga", "afga", "hfta", "afta", "htov", "atov"))
    if dur > 0 or has_events:
        for pl in cur["home_ids"]:
            psec[(home, pl)] += dur
        for pl in cur["away_ids"]:
            psec[(away, pl)] += dur
        c = dict(cur)
        c.pop("changed")
        stints.append(c)


def build_season(events: pd.DataFrame, games: pd.DataFrame):
    """Restituisce (stints, issues, player_games) per tutta la stagione."""
    gmap = games.set_index("game_id")[["home", "away"]].to_dict("index")
    all_st, all_is, rows = [], [], []
    for gid, gev in events.groupby("game_id", sort=True):
        if gid not in gmap:
            continue
        h, a = gmap[gid]["home"], gmap[gid]["away"]
        st, iss, pst, psec = build_game(gev, gid, h, a)
        all_st += st
        all_is += iss
        players = set(pst) | set(psec)
        for (t, pl) in players:
            s = pst.get((t, pl), {})
            fgm, fgx, ftm, ftx = s.get("FGM", 0), s.get("FGX", 0), s.get("FTM", 0), s.get("FTX", 0)
            m3 = s.get("3PM", 0)
            rows.append({"game_id": gid, "team": t, "player": pl, "sec": psec.get((t, pl), 0.0),
                         "pts": 2 * fgm + m3 + ftm, "fgm": fgm, "fga": fgm + fgx, "fg3m": m3, "fg3a": s.get("3PA", 0),
                         "ftm": ftm, "fta": ftm + ftx, "oreb": s.get("OREB", 0), "dreb": s.get("DREB", 0),
                         "ast": s.get("AST", 0), "stl": s.get("STL", 0), "blk": s.get("BLK", 0),
                         "tov": s.get("TOV", 0), "pf": s.get("PF", 0)})
    stints = pd.DataFrame(all_st)
    for side in ("home", "away"):
        ids = pd.DataFrame(stints[f"{side}_ids"].tolist(), index=stints.index)
        for k in range(5):
            stints[f"{side[0]}{k + 1}"] = ids[k].fillna(0).astype(np.int64) if k in ids else 0
        stints[f"{side[0]}n"] = stints[f"{side}_ids"].map(len)
    stints = stints.drop(columns=["home_ids", "away_ids"])
    stints["dur"] = stints["end"] - stints["start"]
    pg = pd.DataFrame(rows)
    pg["min"] = pg["sec"] / 60.0
    return stints, pd.DataFrame(all_is, columns=["game_id", "period", "team", "issue"]), pg
