"""Dati per la pagina «Pronostici NBA 2026/27» (artifact su claude.ai), preparati qui su GitHub.

Prima tre attività pianificate di Claude leggevano siti web (ESPN, Basketball-Reference, Covers) e facevano girare il
modello della pagina: costavano molto. Ora tutto il lavoro avviene in questo workflow e l'unica attività di Claude
copia nel database della pagina le operazioni già pronte di predictions/pagina_sync.json ("ops").

Fonti: calendario, risultati e quote ESPN (già scaricati da `nba live update`), infortuni ESPN, statistiche dei
giocatori Basketball-Reference (una volta al giorno), box score ESPN dei giorni conclusi.
Il modello della pagina gira con node su pagina/index.html e pagina/tools/freeze.js: sono copie esatte dei file
pubblicati e vanno aggiornate ogni volta che la pagina viene ripubblicata.

Stato conservato nel repository (pagina/stato/): peso delle assenze imparato (injlearn.json), ultimo report
infortuni valido, statistiche già convertite, momento dell'ultimo cambiamento di ogni documento.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

from nba.config import TEAMS, path
from nba.config import team as norm_team
from nba.ingest.remote.http import get_json

ROOT = path("external").parents[1]
PAG = ROOT / "pagina"
STATO = PAG / "stato"
OUT = ROOT / "predictions" / "pagina_sync.json"
S = 2026
RES_FROM = "2026-11-18"          # la pagina incorpora già i risultati fino al 17/11
INJ_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={e}"
RESEND_H = 26                    # un documento cambiato viene rispedito per 26 ore (se un giro di copia salta)
ET = "America/New_York"

TEAM_NAMES = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN", "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET", "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS"}
IT = {"knee": "ginocchio", "ankle": "caviglia", "hamstring": "bicipite femorale", "back": "schiena", "foot": "piede",
      "hip": "anca", "groin": "inguine", "calf": "polpaccio", "shoulder": "spalla", "wrist": "polso", "hand": "mano",
      "finger": "dito", "thumb": "pollice", "toe": "alluce", "achilles": "tendine d'Achille", "quadriceps": "quadricipite",
      "thigh": "coscia", "elbow": "gomito", "neck": "collo", "illness": "malattia", "concussion": "commozione cerebrale",
      "rest": "riposo", "personal": "motivi personali", "suspension": "squalifica", "abdomen": "addome", "rib": "costola",
      "oblique": "obliquo", "chest": "torace", "eye": "occhio", "face": "viso", "nose": "naso", "leg": "gamba",
      "shin": "tibia", "heel": "tallone", "lower leg": "gamba", "pelvis": "bacino", "head": "testa",
      "sprain": "distorsione", "strain": "stiramento", "soreness": "dolore", "surgery": "operazione",
      "fracture": "frattura", "tear": "lesione", "contusion": "contusione", "tendinopathy": "tendinopatia",
      "tendinitis": "tendinite", "inflammation": "infiammazione", "spasms": "spasmi", "bruise": "contusione",
      "left": "sinistro", "right": "destro", "not injury related": "non per infortunio"}


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _et_date(ts) -> str:
    return pd.Timestamp(ts).tz_convert(ET).strftime("%Y-%m-%d")


def _load(name: str, default):
    f = STATO / name
    return json.loads(f.read_text()) if f.exists() else default


def _save(name: str, obj) -> None:
    STATO.mkdir(parents=True, exist_ok=True)
    (STATO / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def _page_embedded() -> dict:
    html = (PAG / "index.html").read_text(encoding="utf-8")
    m = re.search(r"window\.NBA_EMBEDDED = (\{.*?\});?\s*</script>", html, re.S)
    return json.loads(m.group(1))


# ---------------------------------------------------------------- partite, risultati, calendario aggiuntivo
def _games() -> pd.DataFrame:
    from nba.ingest.remote.live import regular
    sb = regular(pd.read_parquet(path("external") / "espn" / f"scoreboard_{S}.parquet"))
    fin = path("external") / "live" / f"finals_{S}.parquet"
    if fin.exists():
        f = pd.read_parquet(fin)[["event_id", "periods"]]
        sb = sb.merge(f.assign(event_id=f["event_id"].astype(str)), on="event_id", how="left")
    else:
        sb["periods"] = None
    return sb


def results_rows(g: pd.DataFrame) -> list[str]:
    done = g[g["completed"] & (g["date_et"] >= RES_FROM)].sort_values("date_utc")
    rows = []
    for r in done.itertuples():
        p = int(r.periods) if pd.notna(r.periods) else 4
        ot = "" if p <= 4 else ("OT" if p == 5 else f"{p - 4}OT")
        rows.append(f"{r.date_et}|{r.away}|{int(r.apts)}|{r.home}|{int(r.hpts)}|{ot}")
    return rows


def extra_rows(g: pd.DataFrame, emb: dict) -> list[str]:
    """Partite che contano per la classifica ma non sono nel calendario incorporato (NBA Cup, recuperi)."""
    sched = {}
    for s in emb["schedule"]:
        d, a, h = s.split(",")
        sched.setdefault((norm_team(a), norm_team(h)), []).append(dt.date.fromisoformat(d))
    out = []
    for r in g.sort_values("date_utc").itertuples():
        d = dt.date.fromisoformat(r.date_et)
        if not any(abs((d - x).days) <= 1 for x in sched.get((r.away, r.home), [])):
            out.append(f"{r.date_et}|{r.away}|{r.home}")
    return out


# ---------------------------------------------------------------- infortuni (ESPN)
def _it(*parts) -> str:
    words = []
    for p in parts:
        if not p:
            continue
        t = str(p).strip()
        words.append(IT.get(t.lower(), t.lower()))
    s = " ".join(words).strip()
    return (s[:1].upper() + s[1:]) if s else ""


def injuries_rows(today: str) -> tuple[list[str] | None, str]:
    js = get_json(INJ_URL, timeout=40)
    if not js or not isinstance(js.get("injuries"), list):
        return None, "infortuni ESPN non raggiungibili"
    rows, teams = [], set()
    for blk in js["injuries"]:
        t = TEAM_NAMES.get(blk.get("displayName") or "")
        for it in blk.get("injuries") or []:
            ath = it.get("athlete") or {}
            tt = t or norm_team(((ath.get("team") or {}).get("abbreviation")) or "")
            name = (ath.get("displayName") or "").replace("|", " ").strip()
            status = (it.get("status") or (it.get("type") or {}).get("description") or "").strip()
            if tt not in TEAMS or not name or not status:
                continue
            det = it.get("details") or {}
            ret = str(det.get("returnDate") or "")[:10]
            com = f"{it.get('shortComment') or ''} {it.get('longComment') or ''}".lower()
            if re.search(r"(rest of|remainder of|for) the (season|year)|season-ending|out for the season", com):
                ret = "2027-10-01"
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", ret) and ret[:4] == "2027" and int(ret[5:7]) >= 7:
                ret = "2027-10-01"
            elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ret):
                ret = ""
            if status.lower().startswith("out") and ret and ret <= today:
                w = re.search(r"(\d+)\s*(?:-|to)?\s*(\d+)?\s*weeks?", com)
                if w:
                    ret = (dt.date.fromisoformat(today) + dt.timedelta(weeks=int(w.group(2) or w.group(1)))).isoformat()
            note = _it(det.get("side") if det.get("side") not in (None, "Not Specified") else None, det.get("type"),
                       det.get("detail"))[:60] or "—"
            rows.append(f"{tt}|{name}|{status}|{ret}|{note.replace('|', ' ')}")
            teams.add(tt)
    if len(rows) < 10:
        return None, f"infortuni ESPN: solo {len(rows)} righe, report ignorato"
    return sorted(rows), f"infortuni ESPN: {len(rows)} giocatori di {len(teams)} squadre"


# ---------------------------------------------------------------- statistiche dei giocatori (Basketball-Reference)
def _f(v, nd=1) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    return str(int(round(x))) if nd == 0 else f"{x:.{nd}f}"


def bref_docs(today: str, log: list[str]) -> dict:
    """nba/pergame e nba/advanced, scaricati al massimo una volta per giorno USA."""
    from nba.ingest.remote import bref
    st = _load("bref.json", {})
    if st.get("asOf") != today:
        got = {}
        for kind in ("per_game", "advanced"):
            try:
                t = bref.season_table(S, kind)
            except Exception as e:  # noqa: BLE001
                t, _ = None, log.append(f"Basketball-Reference {kind}: errore {type(e).__name__}")
            if t is not None and len(t) > 300:
                got[kind] = t
        if len(got) == 2:
            pg, ad = got["per_game"], got["advanced"]
            pg_rows, ad_rows = ["Player,Team,G,MP,FGA,FTA,3P,TRB,AST,STL,BLK,TOV,PTS"], ["Player,Team,G,MP,USG,BPM"]
            for r in pg.to_dict("records"):
                tm = norm_team(r.get("Team"))
                if tm not in TEAMS or pd.isna(pd.to_numeric(r.get("MP"), errors="coerce")) or float(r["MP"]) < 15:
                    continue
                nm = str(r["Player"]).replace(",", "").strip()
                pg_rows.append(",".join([nm, tm, _f(r["G"], 0)] + [_f(r[c]) for c in ("MP", "FGA", "FTA", "3P", "TRB", "AST", "STL", "BLK", "TOV", "PTS")]))
            for r in ad.to_dict("records"):
                tm = norm_team(r.get("Team"))
                mp = pd.to_numeric(r.get("MP"), errors="coerce")
                if tm not in TEAMS or pd.isna(mp) or mp < 100:
                    continue
                nm = str(r["Player"]).replace(",", "").strip()
                ad_rows.append(",".join([nm, tm, _f(r["G"], 0), _f(mp, 0), _f(r.get("USG%")), _f(r.get("BPM"))]))
            teams_pg = {x.split(",")[1] for x in pg_rows[1:]}
            if len(pg_rows) > 200 and len(ad_rows) > 250 and len(teams_pg) == 30:
                st = {"asOf": today, "pergame": pg_rows, "advanced": ad_rows}
                _save("bref.json", st)
                pg.astype(str).to_parquet(path("external") / "bref" / f"per_game_{S}.parquet", index=False)
                ad.astype(str).to_parquet(path("external") / "bref" / f"advanced_{S}.parquet", index=False)
                log.append(f"statistiche giocatori: {len(pg_rows) - 1} + {len(ad_rows) - 1} righe")
            else:
                log.append(f"statistiche giocatori scartate ({len(pg_rows)}/{len(ad_rows)} righe, {len(teams_pg)} squadre)")
        else:
            log.append("statistiche giocatori non scaricate: restano quelle del " + str(st.get("asOf")))
    if not st.get("pergame"):
        return {}
    return {"nba/pergame": {"asOf": st["asOf"], "rows": st["pergame"]}, "nba/advanced": {"asOf": st["asOf"], "rows": st["advanced"]}}


# ---------------------------------------------------------------- statistiche reali delle giornate concluse
def _box_rows(e: str) -> tuple[list[str], dict] | None:
    js = get_json(SUMMARY.format(e=e), timeout=40)
    if not js or "boxscore" not in js:
        return None
    from nba.ingest import espn_pbp as E
    tm = E.teams_of(js)
    score = {}
    for c in js["header"]["competitions"][0]["competitors"]:
        score[norm_team(c["team"]["abbreviation"])] = int(float(c.get("score") or 0))
    rows = []
    for blk in js["boxscore"].get("players", []):
        t = tm.get(str(blk["team"]["id"]), (norm_team(blk["team"].get("abbreviation", "")), ""))[0]
        st = blk["statistics"][0]
        keys = st.get("keys") or []
        for a in st.get("athletes", []):
            v = dict(zip(keys, a.get("stats") or []))
            mp = pd.to_numeric(v.get("minutes"), errors="coerce")
            if a.get("didNotPlay") or pd.isna(mp) or mp <= 0:
                continue
            tp = str(v.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted") or "0-0").split("-")[0]
            nm = (a["athlete"].get("displayName") or "").replace("|", " ")
            rows.append(f"{t}|{nm}|{float(mp):.1f}|{int(float(v.get('points') or 0))}|{int(float(v.get('rebounds') or 0))}|"
                        f"{int(float(v.get('assists') or 0))}|{int(float(tp or 0))}")
    return rows, score


def pstats_docs(g: pd.DataFrame, today: str, log: list[str]) -> dict:
    """nba/pstats-AAAA-MM-GG per i 3 giorni USA più recenti con tutte le partite concluse (controllo: la somma dei
    punti dei giocatori deve dare il punteggio finale di ogni squadra)."""
    st = _load("pstats.json", {})
    lo = (dt.date.fromisoformat(today) - dt.timedelta(days=3)).isoformat()
    out = {}
    for d, grp in g[(g["date_et"] >= lo) & (g["date_et"] < today)].groupby("date_et"):
        if not grp["completed"].all():
            continue
        if d not in st:
            rows, bad = [], []
            for e in grp["event_id"].astype(str):
                r = _box_rows(e)
                if r is None:
                    bad.append(e)
                    continue
                pts = {}
                for x in r[0]:
                    p = x.split("|")
                    pts[p[0]] = pts.get(p[0], 0) + int(p[3])
                if pts != r[1]:
                    bad.append(e)
                    continue
                rows += r[0]
            if bad:
                log.append(f"statistiche del {d}: {len(bad)} partite non verificate, riprovo al prossimo giro")
                continue
            st[d] = {"rows": rows, "t": _now().strftime("%Y-%m-%dT%H:%M:%SZ")}
            log.append(f"statistiche del {d}: {len(rows)} giocatori")
        out[f"nba/pstats-{d}"] = {"d": d, "asOf": st[d]["t"], "rows": st[d]["rows"]}
    # tengo solo gli ultimi 10 giorni nello stato
    keep = (dt.date.fromisoformat(today) - dt.timedelta(days=10)).isoformat()
    _save("pstats.json", {k: v for k, v in st.items() if k >= keep})
    return out


# ---------------------------------------------------------------- modello della pagina (pronostici congelati)
def _odds_rows(g: pd.DataFrame) -> list[str]:
    f = path("external") / "espn" / f"odds_{S}.parquet"
    if not f.exists():
        return []
    od = pd.read_parquet(f)
    od["event_id"] = od["event_id"].astype(str)
    od = od.sort_values(["event_id", "priority"]).drop_duplicates("event_id")
    m = g.merge(od, on="event_id", how="inner")
    out = []
    for r in m.itertuples():
        sp = r.current_home_spread if pd.notna(r.current_home_spread) else r.spread
        mla = r.current_away_ml if pd.notna(r.current_away_ml) else r.away_ml
        mlh = r.current_home_ml if pd.notna(r.current_home_ml) else r.home_ml
        tot = r.current_total if pd.notna(r.current_total) else r.over_under
        if all(pd.isna(x) for x in (sp, mla, mlh)):
            continue
        fmt = lambda x, k=1: "" if pd.isna(x) else (f"{x:+.0f}" if k == 0 else f"{x:g}")  # noqa: E731
        out.append(f"{r.date_et}|{r.away}|{r.home}|{fmt(sp)}|{fmt(mla, 0)}|{fmt(mlh, 0)}|{fmt(tot)}|{r.provider} via ESPN")
    return out


def freeze(g: pd.DataFrame, docs: dict, inj: list[str] | None, log: list[str]) -> dict:
    now = _now()
    up = g[~g["completed"]].copy()
    up["tip"] = pd.to_datetime(up["date_utc"], utc=True)
    up = up[(up["tip"] > now) & (up["tip"] <= now + pd.Timedelta(hours=20))]
    if up.empty:
        log.append("pronostici della pagina: nessuna partita nelle prossime 20 ore")
        return {}
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "data"
        d.mkdir()
        w = lambda n, rows: (d / n).write_text("\n".join(rows) + "\n")  # noqa: E731
        w("games.txt", [f"{r.date_et}|{r.away}|{r.home}|{r.tip.strftime('%Y-%m-%dT%H:%M:%SZ')}" for r in up.itertuples()])
        w("results.txt", docs["nba/results"]["rows"])
        if docs.get("nba/extra", {}).get("rows"):
            w("extra.txt", docs["nba/extra"]["rows"])
        if inj:
            w("injuries.txt", inj)
        for k, n in (("nba/pergame", "pergame.csv"), ("nba/advanced", "advanced.csv")):
            if k in docs:
                w(n, docs[k]["rows"])
        od = _odds_rows(up)
        if od:
            w("odds.txt", od)
        if (STATO / "injlearn.json").exists():
            (d / "injlearn.json").write_text((STATO / "injlearn.json").read_text())
        outf = Path(tmp) / "out.json"
        cmd = ["node", str(PAG / "tools" / "freeze.js"), "--html", str(PAG / "index.html"), "--dir", str(d),
               "--now", now.strftime("%Y-%m-%dT%H:%M:%SZ"), "--out", str(outf)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 2 and od and (d / "odds.txt").exists():
            res = json.loads(outf.read_text()) if outf.exists() else {}
            if all("odds" in e for e in res.get("errors", [])):
                (d / "odds.txt").unlink()
                log.append("quote scartate dallo script: pronostici salvati senza quote")
                r = subprocess.run(cmd, capture_output=True, text=True)
        if not outf.exists():
            log.append("modello della pagina non eseguito: " + (r.stderr or r.stdout)[-300:])
            return {}
        res = json.loads(outf.read_text())
    if not res.get("ok"):
        log.append("modello della pagina: errori " + "; ".join(res.get("errors", []))[:400])
        return {}
    log += [x for x in res.get("summary", []) if x.startswith(("Peso", "Proiezioni"))]
    log.append(f"pronostici della pagina: {len(up)} partite (modello {res.get('modelVersion')})")
    sd = res.get("setDocs") or {}
    if "nba/injlearn" in sd:
        _save("injlearn.json", sd["nba/injlearn"])
    return {"merge": res.get("docs") or {}, "set": sd}


# ---------------------------------------------------------------- insieme
def _h(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def run() -> str:
    now = _now()
    today = _et_date(now)
    log: list[str] = []
    emb = _page_embedded()
    g = _games()
    # asOf = ultimo giorno USA con tutte le partite concluse (e tutti i giorni precedenti)
    late = g[(~g["completed"]) & (g["date_et"] < today)]["date_et"]
    done = g[g["completed"] & (g["date_et"] < today)]["date_et"]
    as_of = (dt.date.fromisoformat(late.min()) - dt.timedelta(days=1)).isoformat() if len(late) else (done.max() if len(done) else "")
    docs: dict = {"nba/results": {"asOf": as_of, "rows": results_rows(g)}}
    docs["nba/extra"] = {"rows": extra_rows(g, emb)}

    inj, msg = injuries_rows(today)
    log.append(msg)
    if inj is not None:
        _save("injuries.json", {"asOf": today, "rows": inj})
    else:
        old = _load("injuries.json", {})
        inj = old.get("rows")
        if inj:
            log.append(f"uso l'ultimo report infortuni valido ({old.get('asOf')})")
    if inj:
        docs["nba/injuries"] = {"asOf": _load("injuries.json", {}).get("asOf", today), "rows": inj}

    docs.update(bref_docs(today, log))
    docs.update(pstats_docs(g, today, log))

    fr = freeze(g, docs, inj, log)

    # momento dell'ultimo cambiamento di ogni documento "set": si rispedisce per RESEND_H ore
    seen = _load("inviati.json", {})
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    ops = []
    for k in sorted(docs):
        h = _h(docs[k])
        if seen.get(k, {}).get("h") != h:
            seen[k] = {"h": h, "t": ts}
        if now - pd.Timestamp(seen[k]["t"]) <= pd.Timedelta(hours=RESEND_H):
            ops.append({"op": "set", "path": k, "data": docs[k]})
    keep = (dt.date.fromisoformat(today) - dt.timedelta(days=12)).isoformat()
    seen = {k: v for k, v in seen.items() if not k.startswith("nba/pstats-") or k[-10:] >= keep}
    _save("inviati.json", seen)

    for k, v in (fr.get("merge") or {}).items():
        ops.append({"op": "merge", "path": k, "data": v})
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    for k, v in (old.get("docs") or {}).items():          # pronostici del modello nbaPRE (nba/newlog-AAAA-MM)
        ops.append({"op": "merge", "path": k, "data": v})
    for k, v in (fr.get("set") or {}).items():
        ops.append({"op": "set", "path": k, "data": v})
    note = "; ".join(x for x in log if not x.startswith("Proiezioni"))[:400]
    ops.append({"op": "set", "path": "nba/meta", "data": {"updated": ts, "note": "Dati da GitHub: " + note}})
    old.update({"generato": ts, "ops": ops, "log": log})
    OUT.write_text(json.dumps(old, ensure_ascii=False, separators=(",", ":")))
    size = len(json.dumps(ops, ensure_ascii=False))
    return f"pagina: {len(ops)} operazioni ({size // 1024} KB) · " + " · ".join(log)
