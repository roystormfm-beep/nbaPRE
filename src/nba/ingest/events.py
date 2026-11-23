"""Normalizza il play-by-play delle diverse fonti in un unico formato di eventi.

Formato (una riga per evento elementare):
  game_id   '0021400001'
  period    1..4, 5+ supplementari
  sec_left  secondi rimasti nel periodo
  ord       ordine nella partita (crescente)
  team      sigla della squadra dell'evento ('' se nessuna)
  player    id del giocatore (0 = evento di squadra)
  kind      FGM FGX FTM FTX OREB DREB TOV STL BLK AST PF TECH SUBOUT SUBIN JUMP OTHER PSTART PEND
  is3       tiro da tre
  presence  l'evento prova che il giocatore è in campo (serve per ricostruire i quintetti)
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from nba.config import team as norm_team

EVENT_COLS = ["game_id", "period", "sec_left", "ord", "team", "player", "kind", "is3", "presence"]
TECH_V2 = {11, 12, 13, 16, 18, 19, 25, 30}   # tipi di fallo tecnico in NBA Stats v2


def _clock_mmss(s: pd.Series) -> np.ndarray:
    parts = s.fillna("0:00").str.split(":", n=1, expand=True)
    return parts[0].astype(float).to_numpy() * 60 + parts[1].astype(float).to_numpy()


def _clock_iso(s: pd.Series) -> np.ndarray:
    m = s.fillna("PT0M0S").str.extract(r"PT(\d+)M([\d.]+)S")
    return m[0].astype(float).to_numpy() * 60 + m[1].astype(float).to_numpy()


def _gid(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)


def _frame(**cols) -> pd.DataFrame:
    df = pd.DataFrame(cols)
    for c in EVENT_COLS:
        if c not in df:
            df[c] = False if c in ("is3", "presence") else ""
    return df[EVENT_COLS]


def from_nbastats_v2(v2: pd.DataFrame) -> pd.DataFrame:
    """NBA Stats v2: EVENTMSGTYPE 1 tiro segnato, 2 sbagliato, 3 tiro libero, 4 rimbalzo, 5 palla persa,
    6 fallo, 7 violazione, 8 sostituzione (P1 esce, P2 entra), 10 palla a due, 11 espulsione, 12/13 inizio/fine periodo."""
    d = v2.drop_duplicates().copy()   # la fonte contiene righe ripetute identiche (es. 118 nel 2017-18)
    d["game_id"] = _gid(d["GAME_ID"])
    d = d.drop_duplicates(["game_id", "EVENTNUM"])
    d["sec_left"] = _clock_mmss(d["PCTIMESTRING"])
    d["period"] = d["PERIOD"].astype(int)
    d["ord"] = d["EVENTNUM"].astype(int)
    desc = (d["HOMEDESCRIPTION"].fillna("") + " " + d["VISITORDESCRIPTION"].fillna("") + " "
            + d["NEUTRALDESCRIPTION"].fillna("")).str.upper()
    t = d["EVENTMSGTYPE"].astype(int).to_numpy()
    at = d["EVENTMSGACTIONTYPE"].fillna(0).astype(int).to_numpy()
    pt1 = d["PERSON1TYPE"].fillna(0).astype(int).to_numpy()

    def pid(k):
        return pd.to_numeric(d[f"PLAYER{k}_ID"], errors="coerce").fillna(0).astype(np.int64).to_numpy()

    def tm(k):
        return d[f"PLAYER{k}_TEAM_ABBREVIATION"].fillna("").map(norm_team).to_numpy()

    p1, p2, p3 = pid(1), pid(2), pid(3)
    t1, t2, t3 = tm(1), tm(2), tm(3)
    is_player1 = np.isin(pt1, [4, 5])
    # squadra degli eventi di squadra (PERSON1TYPE 2 = casa, 3 = trasferta): si ricava dopo con la tabella partite
    home_side = np.where(pt1 == 2, "H", np.where(pt1 == 3, "A", ""))
    is3 = desc.str.contains("3PT").to_numpy()
    miss = desc.str.contains("MISS").to_numpy()
    out = []
    base = dict(game_id=d["game_id"].to_numpy(), period=d["period"].to_numpy(), sec_left=d["sec_left"].to_numpy())

    def add(mask, ordoff, team, player, kind, is3v=False, presence=True, side=None):
        if not mask.any():
            return
        f = _frame(game_id=base["game_id"][mask], period=base["period"][mask], sec_left=base["sec_left"][mask],
                   ord=d["ord"].to_numpy()[mask] * 10 + ordoff, team=np.asarray(team)[mask],
                   player=np.asarray(player)[mask],
                   kind=np.asarray(kind)[mask] if not isinstance(kind, str) else kind,
                   is3=np.asarray(is3v)[mask] if not isinstance(is3v, bool) else is3v,
                   presence=np.asarray(presence)[mask] if not isinstance(presence, bool) else presence)
        f["side"] = side[mask] if side is not None else ""
        out.append(f)

    add(t == 1, 0, t1, p1, "FGM", is3)
    add((t == 1) & (p2 > 0), 1, t2, p2, "AST")
    add(t == 2, 0, t1, p1, "FGX", is3)
    add((t == 2) & (p3 > 0), 1, t3, p3, "BLK")
    add((t == 3) & is_player1, 0, t1, p1, np.where(miss, "FTX", "FTM"))
    # rimbalzi: offensivo o difensivo si decide dopo, in base al tiro sbagliato precedente
    add((t == 4) & is_player1, 0, t1, p1, "REB")
    add((t == 4) & ~is_player1, 0, t1, np.zeros_like(p1), "REB", presence=False, side=home_side)
    add((t == 5) & is_player1, 0, t1, p1, "TOV")
    add((t == 5) & ~is_player1, 0, t1, np.zeros_like(p1), "TOV", presence=False, side=home_side)
    add((t == 5) & (p2 > 0) & np.isin(d["PERSON2TYPE"].fillna(0).astype(int), [4, 5]), 1, t2, p2, "STL")
    tech = np.isin(at, list(TECH_V2))
    add((t == 6) & is_player1 & ~tech, 0, t1, p1, "PF")
    add((t == 6) & is_player1 & tech, 0, t1, p1, "TECH", presence=False)
    add((t == 6) & (p2 > 0) & ~tech & np.isin(d["PERSON2TYPE"].fillna(0).astype(int), [4, 5]), 1, t2, p2, "OTHER")
    add((t == 7) & is_player1, 0, t1, p1, "OTHER")
    add(t == 8, 0, t1, p1, "SUBOUT", presence=False)
    add(t == 8, 1, t2, p2, "SUBIN", presence=False)
    for k, (pp, tt) in enumerate([(p1, t1), (p2, t2), (p3, t3)]):
        add((t == 10) & (pp > 0) & (tt != ""), k, tt, pp, "JUMP")
    add(t == 12, 0, np.full(len(d), ""), np.zeros_like(p1), "PSTART", presence=False)
    add(t == 13, 0, np.full(len(d), ""), np.zeros_like(p1), "PEND", presence=False)
    ev = pd.concat(out, ignore_index=True)
    return ev.sort_values(["game_id", "ord"], kind="stable").reset_index(drop=True)


def from_cdn(c: pd.DataFrame) -> pd.DataFrame:
    """cdn.nba.com liveData (2020→): un'azione per riga, sostituzioni separate in 'out' e 'in'."""
    d = c.copy()
    d["game_id"] = _gid(d["gameId"])
    d["sec_left"] = _clock_iso(d["clock"])
    d["period"] = d["period"].astype(int)
    d["ord"] = pd.to_numeric(d["orderNumber"], errors="coerce").fillna(0).astype(np.int64) // 10
    a = d["actionType"].fillna("").str.lower().to_numpy()
    st = d["subType"].fillna("").str.lower().to_numpy()
    res = d["shotResult"].fillna("").str.lower().to_numpy()
    pid = pd.to_numeric(d["personId"], errors="coerce").fillna(0).astype(np.int64).to_numpy()
    tm = d["teamTricode"].fillna("").map(norm_team).to_numpy()
    out = []

    def add(mask, ordoff, team, player, kind, is3v=False, presence=True):
        if not mask.any():
            return
        out.append(_frame(game_id=d["game_id"].to_numpy()[mask], period=d["period"].to_numpy()[mask],
                          sec_left=d["sec_left"].to_numpy()[mask], ord=d["ord"].to_numpy()[mask] * 10 + ordoff,
                          team=np.asarray(team)[mask], player=np.asarray(player)[mask],
                          kind=np.asarray(kind)[mask] if not isinstance(kind, str) else kind,
                          is3=np.asarray(is3v)[mask] if not isinstance(is3v, bool) else is3v,
                          presence=np.asarray(presence)[mask] if not isinstance(presence, bool) else presence))

    shot = np.isin(a, ["2pt", "3pt"])
    is3 = a == "3pt"
    add(shot & (res == "made"), 0, tm, pid, "FGM", is3)
    add(shot & (res != "made"), 0, tm, pid, "FGX", is3)
    ast = pd.to_numeric(d["assistPersonId"], errors="coerce").fillna(0).astype(np.int64).to_numpy()
    add(shot & (res == "made") & (ast > 0), 1, tm, ast, "AST")
    add(a == "freethrow", 0, tm, pid, np.where(res == "made", "FTM", "FTX"))
    reb_kind = np.where(st == "offensive", "OREB", "DREB")
    add((a == "rebound") & (pid > 0), 0, tm, pid, reb_kind)
    add((a == "rebound") & (pid == 0), 0, tm, pid, reb_kind, presence=False)
    add((a == "turnover") & (pid > 0), 0, tm, pid, "TOV")
    add((a == "turnover") & (pid == 0), 0, tm, pid, "TOV", presence=False)
    add((a == "steal") & (pid > 0), 0, tm, pid, "STL")
    add((a == "block") & (pid > 0), 0, tm, pid, "BLK")
    add((a == "foul") & (pid > 0) & (st != "technical"), 0, tm, pid, "PF")
    add((a == "foul") & (pid > 0) & (st == "technical"), 0, tm, pid, "TECH", presence=False)
    add((a == "substitution") & (st == "out"), 0, tm, pid, "SUBOUT", presence=False)
    add((a == "substitution") & (st == "in"), 0, tm, pid, "SUBIN", presence=False)
    add((a == "jumpball") & (pid > 0), 0, tm, pid, "JUMP")
    add((a == "violation") & (pid > 0), 0, tm, pid, "OTHER")
    add((a == "period") & (st == "start"), 0, np.full(len(d), ""), np.zeros_like(pid), "PSTART", presence=False)
    add((a == "period") & (st == "end"), 0, np.full(len(d), ""), np.zeros_like(pid), "PEND", presence=False)
    ev = pd.concat(out, ignore_index=True)
    ev["side"] = ""
    return ev.sort_values(["game_id", "ord"], kind="stable").reset_index(drop=True)
