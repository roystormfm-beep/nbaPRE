"""Archivio degli injury report ufficiali NBA (PDF pubblicati più volte al giorno, con l'orario nel nome del file).

Passi:
  index   elenco dei PDF disponibili per stagione (pagine di official.nba.com; se una pagina non esiste, prova
          gli orari tipici per ogni giorno di partita) -> data/external/injury/index_{S}.csv
  samples alcuni PDF di stagioni diverse in data/external/injury/samples/ (per scrivere e provare il lettore)
  fetch   per ogni partita scarica l'ultimo report pubblicato almeno 45 minuti prima della palla a due,
          lo legge e salva le righe -> data/external/injury/reports_{S}.parquet
"""
from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

import pandas as pd

from nba.config import path, season_label
from nba.ingest.remote.http import _session, get, pmap

PAGE = "https://official.nba.com/nba-injury-report-{lab}-season/"
PDF = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{d}_{t}.pdf"
RX = re.compile(r"https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})(?:_(\d{2}))?(AM|PM)\.pdf")
ET = ZoneInfo("America/New_York")


def _out_dir():
    p = path("external") / "injury"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _parse_name(m) -> tuple[str, str]:
    d, hh, mm, ap = m.group(1), int(m.group(2)), int(m.group(3) or 0), m.group(4)
    h24 = (hh % 12) + (12 if ap == "PM" else 0)
    return d, f"{h24:02d}:{mm:02d}"


def _fmt_time(h24: int, mm: int, new_style: bool) -> str:
    ap = "PM" if h24 >= 12 else "AM"
    hh = h24 % 12 or 12
    return f"{hh:02d}_{mm:02d}{ap}" if new_style else f"{hh:02d}{ap}"


def index(s: int) -> pd.DataFrame:
    lab = season_label(s)
    r = get(PAGE.format(lab=lab), timeout=60)
    rows = []
    if r is not None:
        for m in RX.finditer(r.text):
            d, t = _parse_name(m)
            rows.append({"url": m.group(0), "date": d, "time_et": t, "src": "pagina"})
    df = pd.DataFrame(rows).drop_duplicates("url") if rows else pd.DataFrame(columns=["url", "date", "time_et", "src"])
    # giorni di partita senza alcun link nella pagina: provo gli orari tipici (vecchio formato orario e nuovo a 15')
    gp = path("processed") / f"games_{s}.parquet"
    if gp.exists():
        days = sorted(pd.read_parquet(gp, columns=["date"])["date"].dropna().unique())
        missing = [d for d in days if d not in set(df["date"])]
        cand = [(d, _fmt_time(h, m, new)) for d in missing for h in range(11, 22) for (m, new) in ((0, False), (0, True), (30, True))]
        found = pmap(lambda dt_: _head(PDF.format(d=dt_[0], t=dt_[1])), cand, workers=8)
        extra = [{"url": PDF.format(d=d, t=t), "date": d, "time_et": _parse_name(RX.match(PDF.format(d=d, t=t)))[1], "src": "prova"}
                 for (d, t), ok in found.items() if ok]
        if extra:
            df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True).drop_duplicates("url")
    df["season"] = s
    df = df.sort_values(["date", "time_et"]).reset_index(drop=True)
    df.to_csv(_out_dir() / f"index_{s}.csv", index=False)
    return df


def _head(url: str) -> bool:
    try:
        return _session.head(url, timeout=20, allow_redirects=True).status_code == 200
    except Exception:  # noqa: BLE001
        return False


def samples(seasons: list[int]) -> list[str]:
    out = _out_dir() / "samples"
    out.mkdir(exist_ok=True)
    saved = []
    for s in seasons:
        f = _out_dir() / f"index_{s}.csv"
        if not f.exists():
            continue
        ix = pd.read_csv(f)
        if ix.empty:
            continue
        mid = ix[ix["date"] >= f"{s + 1}-01-10"].head(1)
        for u in (ix.head(1)["url"].tolist() + mid["url"].tolist() + ix.tail(1)["url"].tolist()):
            r = get(u, timeout=60)
            if r is not None and r.content[:4] == b"%PDF":
                name = u.rsplit("/", 1)[1]
                (out / name).write_bytes(r.content)
                saved.append(name)
    return saved


def needed_reports(s: int, lead_min: int = 45) -> pd.DataFrame:
    """Per ogni partita: l'ultimo report pubblicato almeno lead_min minuti prima dell'inizio (orario ESPN)."""
    ix = pd.read_csv(_out_dir() / f"index_{s}.csv")
    g = pd.read_parquet(path("processed") / f"games_{s}.parquet", columns=["game_id", "date", "home", "away", "tip_utc_espn"])
    ix["ts"] = pd.to_datetime(ix["date"] + " " + ix["time_et"]).dt.tz_localize(ET)
    g["tip"] = pd.to_datetime(g["tip_utc_espn"], utc=True).dt.tz_convert(ET)
    rows = []
    for r in g.itertuples():
        if pd.isna(r.tip):
            continue
        lim = r.tip - pd.Timedelta(minutes=lead_min)
        c = ix[(ix["ts"] <= lim) & (ix["ts"] >= lim - pd.Timedelta(hours=36))]
        if len(c):
            best = c.iloc[-1]
            rows.append({"game_id": r.game_id, "date": r.date, "home": r.home, "away": r.away, "tip": r.tip.isoformat(),
                         "url": best["url"], "report_ts": best["ts"].isoformat()})
    return pd.DataFrame(rows)


def fetch(s: int) -> str:
    from nba.ingest.injury_pdf import parse_pdf
    need = needed_reports(s)
    if need.empty:
        return f"{s}: nessun report da scaricare"
    urls = sorted(need["url"].unique())

    def one(u):
        r = get(u, timeout=60)
        if r is None or r.content[:4] != b"%PDF":
            return None
        try:
            return parse_pdf(r.content)
        except Exception as e:  # noqa: BLE001
            return f"errore: {type(e).__name__}: {e}"

    res = pmap(one, urls, workers=6)
    parts, bad = [], 0
    for u, v in res.items():
        if isinstance(v, pd.DataFrame):
            parts.append(v.assign(url=u))
        else:
            bad += 1
    rep = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    rep.to_parquet(_out_dir() / f"reports_{s}.parquet", index=False)
    need.to_csv(_out_dir() / f"needed_{s}.csv", index=False)
    return f"{s}: {len(urls)} report per {len(need)} partite, {len(rep)} righe lette, {bad} non letti"


def run(seasons: list[int], step: str) -> list[str]:
    log = []
    if step in ("index", "all"):
        for s in seasons:
            ix = index(s)
            log.append(f"{s}: {len(ix)} report nell'indice ({(ix['src'] == 'pagina').sum()} dalla pagina), "
                       f"{ix['date'].nunique() if len(ix) else 0} giorni")
            print(log[-1], flush=True)
    if step in ("samples", "index", "all"):
        log.append("campioni: " + ", ".join(samples(seasons)))
    if step in ("fetch", "all"):
        for s in seasons:
            log.append(fetch(s))
            print(log[-1], flush=True)
    return log
