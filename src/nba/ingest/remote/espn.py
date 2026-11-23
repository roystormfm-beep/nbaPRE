"""ESPN: calendario con risultati e sede (scoreboard) e quote per partita (API 'core').

Uscite in data/external/espn/:
  scoreboard_{S}.parquet  una riga per partita di stagione regolare: id ESPN, data, squadre, punteggio, sede, campo neutro
  odds_{S}.parquet        una riga per partita e fornitore di quote: spread, totale, moneyline in apertura/chiusura/attuale
S = anno di inizio della stagione (2025 = 2025-26). API non documentate: i campi possono cambiare.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from nba.config import path, team as norm_team
from nba.ingest.remote.http import get_json, pmap

SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}&limit=200"
ODDS = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{e}/competitions/{e}/odds?limit=100"


def season_dates(s: int) -> list[str]:
    start = dt.date(s, 10, 1)
    end = dt.date(s + 1, 8, 31) if s == 2019 else dt.date(s + 1, 6, 30)   # 2019-20: partite nella "bolla" ad agosto
    end = min(end, dt.date.today() - dt.timedelta(days=1))
    out, d = [], start
    while d <= end:
        out.append(d.strftime("%Y%m%d"))
        d += dt.timedelta(days=1)
    return out


def _sb_rows(day: str) -> list[dict]:
    js = get_json(SB.format(d=day))
    rows = []
    for ev in (js or {}).get("events", []):
        try:
            comp = ev["competitions"][0]
            stype = (ev.get("season") or {}).get("type")
            teams = {c["homeAway"]: c for c in comp["competitors"]}
            venue = comp.get("venue") or {}
            addr = venue.get("address") or {}
            rows.append({
                "event_id": str(ev["id"]), "espn_season": (ev.get("season") or {}).get("year"), "season_type": stype,
                "date_utc": ev.get("date"), "home": norm_team(teams["home"]["team"]["abbreviation"]),
                "away": norm_team(teams["away"]["team"]["abbreviation"]),
                "hpts": pd.to_numeric(teams["home"].get("score"), errors="coerce"),
                "apts": pd.to_numeric(teams["away"].get("score"), errors="coerce"),
                "completed": bool(((comp.get("status") or ev.get("status") or {}).get("type") or {}).get("completed")),
                "neutral": bool(comp.get("neutralSite")), "venue": venue.get("fullName"),
                "city": addr.get("city"), "state": addr.get("state"), "country": addr.get("country"),
                "headline": ";".join(n.get("headline", "") for n in comp.get("notes") or []),
            })
        except (KeyError, IndexError, TypeError):
            continue
    return rows


def scoreboard(s: int, workers: int = 4) -> pd.DataFrame:
    days = season_dates(s)
    res = pmap(_sb_rows, days, workers=workers)
    df = pd.DataFrame([r for d in days for r in res.get(d) or []])
    if df.empty:
        return df
    df = df.drop_duplicates("event_id")
    df["date_et"] = (pd.to_datetime(df["date_utc"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d"))
    df["season"] = s
    return df.sort_values("date_utc").reset_index(drop=True)


def _val(o):
    """Valore numerico da un campo quota ESPN (stringa '+4.5', '-180', numero, o dizionario con 'american'...)."""
    if o is None:
        return None
    if isinstance(o, dict):
        for k in ("american", "alternateDisplayValue", "displayValue", "value"):
            if k in o and o[k] not in (None, ""):
                return _val(o[k])
        return None
    if isinstance(o, (int, float)):
        return float(o)
    s = str(o).strip().replace("+", "")
    if s.upper() in ("EVEN", "EV"):
        return 100.0
    if s.lower().startswith(("o", "u")) and len(s) > 1:
        s = s[1:]
    try:
        return float(s)
    except ValueError:
        return None


def _odds_rows(eid: str) -> list[dict]:
    js = get_json(ODDS.format(e=eid))
    if not js:
        return []
    items = js.get("items") or []
    rows = []
    for it in items:
        if set(it) <= {"$ref"}:
            it = get_json(it["$ref"]) or {}
        prov = it.get("provider") or {}
        r = {"event_id": eid, "provider_id": str(prov.get("id")), "provider": prov.get("name"),
             "priority": prov.get("priority"), "details": it.get("details"),
             "spread": _val(it.get("spread")), "over_under": _val(it.get("overUnder"))}
        h, a = it.get("homeTeamOdds") or {}, it.get("awayTeamOdds") or {}
        r["home_ml"], r["away_ml"] = _val(h.get("moneyLine")), _val(a.get("moneyLine"))
        r["home_fav"] = h.get("favorite")
        for ph in ("open", "close", "current"):
            hp, ap, tp = h.get(ph) or {}, a.get(ph) or {}, it.get(ph) or {}
            r[f"{ph}_home_spread"] = _val(hp.get("pointSpread"))
            r[f"{ph}_away_spread"] = _val(ap.get("pointSpread"))
            r[f"{ph}_home_ml"] = _val(hp.get("moneyLine"))
            r[f"{ph}_away_ml"] = _val(ap.get("moneyLine"))
            r[f"{ph}_total"] = _val(tp.get("total"))
        rows.append(r)
    return rows


def odds(event_ids: list[str], workers: int = 4) -> pd.DataFrame:
    res = pmap(_odds_rows, event_ids, workers=workers)
    return pd.DataFrame([r for e in event_ids for r in res.get(e) or []])


def run(seasons: list[int], with_odds: bool = True) -> list[str]:
    out_dir = path("external") / "espn"
    out_dir.mkdir(parents=True, exist_ok=True)
    log = []
    for s in seasons:
        sb = scoreboard(s)
        if sb.empty:
            log.append(f"{s}: scoreboard vuoto")
            continue
        sb.to_parquet(out_dir / f"scoreboard_{s}.parquet", index=False)
        reg = sb[(sb["season_type"] == 2) & sb["completed"]]
        msg = f"{s}: {len(sb)} partite ESPN ({len(reg)} di stagione regolare concluse)"
        if with_odds and len(reg):
            od = odds(reg["event_id"].tolist())
            od.to_parquet(out_dir / f"odds_{s}.parquet", index=False)
            cov = od["event_id"].nunique() / len(reg) if len(od) else 0
            msg += f"; quote per {cov:.1%} delle partite, {od['provider'].nunique() if len(od) else 0} fornitori"
        print(msg, flush=True)
        log.append(msg)
    return log
