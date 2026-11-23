"""Scaricamenti per la stagione in corso (da GitHub Actions): calendario completo, partite giocate, quote, injury report.

File in data/external/live/ (stagione S = anno di inizio):
  events_{S}.parquet   eventi del play-by-play ESPN di ogni partita conclusa (id giocatori ESPN)
  box_{S}.parquet      box score ESPN (squadra, id ESPN, nome, titolare, minuti, punti)
  finals_{S}.parquet   punteggio finale e periodi per partita
  pbpstats_{S}.parquet giocatori per partita secondo pbpstats (id NBA e nome): serve a tradurre gli id ESPN
Il calendario va in data/external/espn/scoreboard_{S}.parquet (anche le partite future), le quote in odds_{S}.parquet.
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from nba.config import TEAMS, path, season_label
from nba.ingest import espn_pbp as E
from nba.ingest.remote import espn
from nba.ingest.remote.http import get_json, pmap

SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={e}"
PBP_GAMES = "https://api.pbpstats.com/get-games/nba?Season={lab}&SeasonType=Regular%20Season"
PBP_PLAYERS = "https://api.pbpstats.com/get-game-stats?GameId={g}&Type=Player"


def _dir():
    d = path("external") / "live"
    d.mkdir(parents=True, exist_ok=True)
    return d


def game_id(event_id) -> str:
    """Id interno delle partite della stagione in corso: '2' + id ESPN (10 caratteri, stabile prima e dopo la gara)."""
    return "2" + str(event_id)


def regular(sb: pd.DataFrame) -> pd.DataFrame:
    """Partite che contano per la classifica: stagione regolare, squadre NBA, esclusa la finale di Coppa."""
    x = sb[(sb["season_type"] == 2) & sb["home"].isin(TEAMS) & sb["away"].isin(TEAMS)]
    return x[~x["headline"].fillna("").str.contains("Championship", case=False)].copy()


def schedule(s: int) -> pd.DataFrame:
    start, end = dt.date(s, 10, 1), dt.date(s + 1, 4, 30)
    days, d = [], start
    while d <= end:
        days.append(d.strftime("%Y%m%d"))
        d += dt.timedelta(days=1)
    res = pmap(espn._sb_rows, days, workers=4)
    sb = pd.DataFrame([r for d in days for r in res.get(d) or []]).drop_duplicates("event_id")
    sb["date_et"] = pd.to_datetime(sb["date_utc"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    sb["season"] = s
    sb = sb.sort_values("date_utc").reset_index(drop=True)
    sb.to_parquet(path("external") / "espn" / f"scoreboard_{s}.parquet", index=False)
    return sb


def _load(name: str, s: int) -> pd.DataFrame:
    f = _dir() / f"{name}_{s}.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame()


def games(s: int) -> str:
    sb = regular(pd.read_parquet(path("external") / "espn" / f"scoreboard_{s}.parquet"))
    done = sb[sb["completed"]]
    fin = _load("finals", s)
    have = set(fin["event_id"]) if len(fin) else set()
    new = [e for e in done["event_id"].astype(str) if e not in have]

    def one(e):
        js = get_json(SUMMARY.format(e=e))
        if not js or not js.get("plays"):
            return None
        gid = game_id(e)
        try:
            ev, bx, fs = E.events(js, gid), E.box(js), E.final_score(js)
        except Exception as ex:  # noqa: BLE001
            return f"errore {e}: {type(ex).__name__}"
        return ev.assign(event_id=e), bx.assign(event_id=e, game_id=gid), {"event_id": e, "game_id": gid, **fs}

    res = pmap(one, new, workers=4)
    evs, bxs, fins, bad = [], [], [], 0
    for e in new:
        v = res.get(e)
        if isinstance(v, tuple):
            evs.append(v[0]); bxs.append(v[1]); fins.append(v[2])
        else:
            bad += 1
    if fins:
        for name, parts in (("events", evs), ("box", bxs)):
            old = _load(name, s)
            pd.concat([old] + parts, ignore_index=True).to_parquet(_dir() / f"{name}_{s}.parquet", index=False)
        pd.concat([fin, pd.DataFrame(fins)], ignore_index=True).to_parquet(_dir() / f"finals_{s}.parquet", index=False)
    msg = f"{s}: {len(done)} partite concluse, {len(fins)} nuove scaricate, {bad} non disponibili"
    return msg + "; " + pbpstats_players(s, sb)


def pbpstats_players(s: int, sb: pd.DataFrame) -> str:
    """Giocatori di ogni partita con l'id NBA (da pbpstats), abbinati alla partita ESPN per data e squadre."""
    js = get_json(PBP_GAMES.format(lab=season_label(s)))
    if not js:
        return "pbpstats non raggiungibile"
    pg = pd.DataFrame(js.get("results") or [])
    if pg.empty:
        return "pbpstats: nessuna partita"
    from nba.config import team as norm_team
    pg["home"] = pg["HomeTeamAbbreviation"].map(norm_team)
    pg["away"] = pg["AwayTeamAbbreviation"].map(norm_team)
    done = sb[sb["completed"]][["event_id", "date_et", "home", "away"]]
    m = done.merge(pg[["GameId", "Date", "home", "away"]], left_on=["date_et", "home", "away"],
                   right_on=["Date", "home", "away"], how="inner")
    old = _load("pbpstats", s)
    have = set(old["event_id"]) if len(old) else set()
    todo = m[~m["event_id"].astype(str).isin(have)]

    def one(gid):
        j = get_json(PBP_PLAYERS.format(g=gid), tries=3)
        if not j or "stats" not in j:
            return None
        rows = []
        for side, team_key in (("Home", "home_team_abbreviation"), ("Away", "away_team_abbreviation")):
            for x in (j["stats"].get(side) or {}).get("FullGame") or []:
                if str(x.get("EntityId")) not in ("0", ""):
                    rows.append({"team": norm_team(j.get(team_key, "")), "nba_id": int(x["EntityId"]), "name": x.get("Name"),
                                 "min_pbp": x.get("Minutes")})
        return rows

    res = pmap(one, todo["GameId"].tolist(), workers=2)
    rows = []
    for r in todo.itertuples():
        for x in res.get(r.GameId) or []:
            rows.append({"event_id": str(r.event_id), "nba_game_id": r.GameId, **x})
    if rows:
        pd.concat([old, pd.DataFrame(rows)], ignore_index=True).to_parquet(_dir() / f"pbpstats_{s}.parquet", index=False)
    return f"pbpstats: {len(m)} partite abbinate, {todo.shape[0]} nuove"


def odds(s: int, days_back: int = 3, days_ahead: int = 1) -> str:
    """Quote ESPN delle partite degli ultimi giorni e di oggi/domani (le altre restano quelle già salvate)."""
    sb = regular(pd.read_parquet(path("external") / "espn" / f"scoreboard_{s}.parquet"))
    today = pd.Timestamp.now(tz="America/New_York").normalize()
    lo = (today - pd.Timedelta(days=days_back)).strftime("%Y-%m-%d")
    hi = (today + pd.Timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    ev = sb[(sb["date_et"] >= lo) & (sb["date_et"] <= hi)]["event_id"].astype(str).tolist()
    f = path("external") / "espn" / f"odds_{s}.parquet"
    old = pd.read_parquet(f) if f.exists() else pd.DataFrame()
    # partite concluse prima della finestra e non ancora salvate: si recuperano una volta
    if len(old):
        missing = set(sb[sb["completed"] & (sb["date_et"] < lo)]["event_id"].astype(str)) - set(old["event_id"].astype(str))
        ev += sorted(missing)
    new = espn.odds(ev)
    if len(old):
        old = old[~old["event_id"].astype(str).isin(set(ev))]
    out = pd.concat([old, new], ignore_index=True)
    out.to_parquet(f, index=False)
    return f"quote: {new['event_id'].nunique() if len(new) else 0} partite aggiornate"


def injuries(s: int, days_back: int = 2) -> str:
    """Injury report: elenco aggiornato (pagina ufficiale + prove sugli orari delle partite recenti e di oggi),
    poi scaricamento dei soli report nuovi necessari."""
    import time

    from nba.ingest.injury_pdf import parse_pdf
    from nba.ingest.remote import injuries as INJ
    from nba.ingest.remote.http import get

    ixf = path("external") / "injury" / f"index_{s}.csv"
    old = pd.read_csv(ixf) if ixf.exists() else pd.DataFrame(columns=["url", "date", "time_et", "src", "season"])
    rows = []
    r = get(INJ.PAGE.format(lab=season_label(s)), timeout=60)
    if r is not None:
        for m in INJ.RX.finditer(r.text):
            d, t = INJ._parse_name(m)
            rows.append({"url": m.group(0), "date": d, "time_et": t, "src": "pagina", "season": s})
    g = pd.read_parquet(path("processed") / f"games_{s}.parquet", columns=["date", "tip_utc_espn"]).dropna()
    now = pd.Timestamp.now(tz=INJ.ET)
    tips = pd.to_datetime(g["tip_utc_espn"], utc=True).dt.tz_convert(INJ.ET)
    tips = tips[tips <= now + pd.Timedelta(hours=30)]
    known = set(old["url"]) | {x["url"] for x in rows}
    # fasce già provate (per le partite passate basta una volta); quelle di oggi si riprovano a ogni esecuzione
    pf = path("external") / "injury" / f"probed_{s}.txt"
    probed = set(pf.read_text().split()) if pf.exists() else set()
    targets = sorted({min(t - pd.Timedelta(minutes=45), now).floor("15min") for t in tips})
    for target in targets:
        tag = target.strftime("%Y-%m-%dT%H:%M")
        if tag in probed:
            continue
        if target < now - pd.Timedelta(hours=1):
            probed.add(tag)
        for d, t in INJ._slot_candidates(target):
            u = INJ.PDF.format(d=d, t=t)
            if u in known:
                break
            if INJ._head(u):
                dd, tt = INJ._parse_name(INJ.RX.match(u))
                rows.append({"url": u, "date": dd, "time_et": tt, "src": "prova", "season": s})
                known.add(u)
                break
    pf.write_text("\n".join(sorted(probed)) + "\n")
    ix = pd.concat([old, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("url")
    ix = ix.sort_values(["date", "time_et"]).reset_index(drop=True)
    ix.to_csv(ixf, index=False)
    need = INJ.needed_reports(s)
    rf = path("external") / "injury" / f"reports_{s}.parquet"
    rep = pd.read_parquet(rf) if rf.exists() else pd.DataFrame()
    have = set(rep["url"]) if len(rep) and "url" in rep else set()
    todo = sorted(set(need["url"]) - have) if len(need) else []
    parts, bad = [], 0
    for u in todo:
        time.sleep(0.6)
        resp = get(u, timeout=60)
        if resp is None or resp.content[:4] != b"%PDF":
            bad += 1
            continue
        try:
            parts.append(parse_pdf(resp.content).assign(url=u))
        except Exception:  # noqa: BLE001
            bad += 1
    if parts:
        rep = pd.concat([rep] + parts, ignore_index=True)
        rep.to_parquet(rf, index=False)
    need.to_csv(path("external") / "injury" / f"needed_{s}.csv", index=False)
    return f"injury report: {len(ix)} nell'elenco, {len(todo)} nuovi da leggere, {bad} non letti, {len(need)} partite coperte"


def run(s: int) -> list[str]:
    import time
    from nba.live import build
    log, t0 = [], time.time()

    def note(msg):
        line = f"[{time.time() - t0:5.0f} s] {msg}"
        print(line, flush=True)
        log.append(line)

    sb = schedule(s)
    note(f"calendario {s}: {len(regular(sb))} partite di stagione regolare, {int(regular(sb)['completed'].sum())} concluse")
    note(games(s))
    note(json.dumps(build.build(s)))
    note(odds(s))
    note(injuries(s))
    note(json.dumps(build.lines(s)))
    return log
