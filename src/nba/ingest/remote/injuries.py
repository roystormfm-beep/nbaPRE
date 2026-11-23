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
import time
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


def _slot_candidates(target: pd.Timestamp) -> list[tuple[str, str]]:
    """Nomi di file possibili per l'ultimo report <= target, in ordine di probabilità.

    Nell'archivio convivono due formati: report orari "05PM" e aggiornamenti a 15 minuti "05_45PM"."""
    t15 = target.floor("15min")
    th = target.floor("h")
    seq = [(t15, True), (th, False), (t15 - pd.Timedelta(minutes=15), True), (t15 - pd.Timedelta(minutes=30), True),
           (th - pd.Timedelta(hours=1), False), (t15 - pd.Timedelta(minutes=45), True), (th - pd.Timedelta(hours=2), False)]
    out, seen = [], set()
    for x, new in seq:
        k = (x.strftime("%Y-%m-%d"), _fmt_time(x.hour, x.minute, new) if new else _fmt_time(x.hour, 0, False))
        if k not in seen and (new or x.minute == 0):
            seen.add(k)
            out.append(k)
    return out


def index(s: int, lead_min: int = 45) -> pd.DataFrame:
    """Per ogni fascia d'orario di inizio: l'ultimo report pubblicato almeno lead_min minuti prima.

    Le pagine di official.nba.com mostrano solo i report più recenti, quindi per il passato provo direttamente
    i nomi dei file (orario a 15 minuti o orario pieno), dal più recente all'indietro, fino a 3 ore prima."""
    lab = season_label(s)
    rows = []
    r = get(PAGE.format(lab=lab), timeout=60)
    if r is not None:
        for m in RX.finditer(r.text):
            d, t = _parse_name(m)
            rows.append({"url": m.group(0), "date": d, "time_et": t, "src": "pagina"})
    gp = path("processed") / f"games_{s}.parquet"
    if gp.exists():
        g = pd.read_parquet(gp, columns=["date", "tip_utc_espn"]).dropna()
        tips = pd.to_datetime(g["tip_utc_espn"], utc=True).dt.tz_convert(ET)
        targets = sorted({(tip - pd.Timedelta(minutes=lead_min)).floor("15min") for tip in tips})

        found = {}
        canary = None
        for i, target in enumerate(targets):
            found[target] = None
            for d, t in _slot_candidates(target):
                u = PDF.format(d=d, t=t)
                if _head(u):
                    found[target] = canary = canary or u
                    found[target] = u
                    break
            # ogni 40 fasce controllo di non essere stato bloccato (un file sicuramente esistente deve rispondere)
            if canary and i % 40 == 39 and not _head(canary):
                print(f"  {s}: possibile blocco, attendo 90 s", flush=True)
                time.sleep(90)
        for target, u in found.items():
            if u:
                d, t = _parse_name(RX.match(u))
                rows.append({"url": u, "date": d, "time_et": t, "src": "prova", "slot": target.isoformat()})
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["url", "date", "time_et", "src"])
    df = df.drop_duplicates("url")
    df["season"] = s
    df = df.sort_values(["date", "time_et"]).reset_index(drop=True)
    df.to_csv(_out_dir() / f"index_{s}.csv", index=False)
    return df


def _head(url: str) -> bool:
    time.sleep(0.6)                     # al massimo ~1,5 richieste al secondo: l'archivio blocca chi va più veloce
    for k in range(4):
        try:
            r = _session.head(url, timeout=20, allow_redirects=True)
            if r.status_code == 200:
                return True
            if r.status_code in (403, 404):
                return False
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.5 * (k + 1))
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
        ix = ix[ix["src"] == "prova"] if (ix["src"] == "prova").any() else ix
        pick = ix.iloc[[0, len(ix) // 2]] if len(ix) > 1 else ix
        for u in pick["url"].tolist():
            time.sleep(1)
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
