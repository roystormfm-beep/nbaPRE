"""Pubblicazione dei pronostici nel formato della pagina.

predictions/AAAA-MM-GG.json e predictions/latest.json:
  {"meta": {...}, "g": {"AAAA-MM-GG_AWAY_HOME": riga, ...}}   (stessa struttura dei documenti nba/predlog-* della pagina)
riga: d (data USA), a, h, tip (inizio UTC), t (quando è stato calcolato), src, mv (versione del modello),
      ap, hp (punti attesi), m (scarto casa), p (probabilità casa), sd, tot, outA, outH (assenze considerate),
      why (i 3 fattori principali), mk (linea di mercato al momento del calcolo), dmk (modello − mercato),
      motivo (codice quando il modello si stacca dalla linea di 3 punti o più), injAsOf (orario dell'injury report).
Una partita già iniziata non viene più riscritta: resta il pronostico congelato prima della palla a due.
predictions/registro_{S}.csv: ogni pronostico pubblicato (una riga per partita e per esecuzione).
predictions/ricostruiti_{S}.csv: tutte le partite della stagione con il pronostico ricostruito con le stesse regole
(solo informazioni precedenti a ogni partita), per il confronto con il mercato.
"""
from __future__ import annotations

import hashlib
import json
import subprocess

import numpy as np
import pandas as pd

from nba.config import ROOT, cfg, path

OUT = ROOT / "predictions"
LABEL_ST = {"out": "out", "doubtful": "molto in dubbio", "questionable": "in dubbio", "probable": "probabile"}


def _n(v, d=1):
    return f"{abs(v):.{d}f}".replace(".", ",")


def model_version() -> str:
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        h = ""
    c = hashlib.sha256(json.dumps(cfg()["models"], sort_keys=True).encode()).hexdigest()[:6]
    return f"{h or 'locale'}-{c}"


def _new(outs):
    """Assenze nuove: giocatori che avevano giocato di recente (le assenze lunghe sono già nei minuti recenti)."""
    return [o for o in outs if o[4] > 0]


def _outs(outs) -> str:
    """Assenze nuove con il loro effetto in punti di scarto per la squadra; poi quelle lunghe, già scontate."""
    new = sorted(_new(outs), key=lambda o: o[2])
    old = [o for o in outs if o[4] <= 0]
    parts = [f"{name} ({LABEL_ST.get(st, st)}) {'-' if eff < 0 else '+'}{_n(eff)}" for name, st, eff, base, _ in new[:4]]
    if old:
        parts.append("fuori da tempo, già nei minuti recenti: " + ", ".join(o[0] for o in old[:3]))
    return "; ".join(parts)


def _why(r, info) -> tuple[list[str], dict]:
    """Fattori in punti di scarto dal punto di vista della squadra di casa; la somma dà il pronostico."""
    h, a = r["home"], r["away"]
    f = {}
    f["campo"] = info["hca"]
    f["roster"] = info["h_str_no"] - info["a_str_no"] + info["team_adj"]
    f["ass_h"] = info["h_abs"]
    f["ass_a"] = -info["a_abs"]
    f["contesto"] = r["m_players"] - r["m_players_raw"]
    f["altri"] = r["m_final"] - r["m_players"]
    # ciò che resta (arrotondamenti dei minuti) va nella qualità dei roster
    f["roster"] += r["m_players_raw"] - (f["campo"] + f["roster"] + f["ass_h"] + f["ass_a"])
    c = info.get("ctx") or {}
    tags = []
    for side, t in (("h", h), ("a", a)):
        if c.get(f"{side}_rest0"):
            tags.append(f"{t} in back-to-back")
        elif c.get(f"{side}_three_in_four"):
            tags.append(f"{t} alla terza partita in 4 notti")
        if c.get(f"{side}_late_lowwin"):
            tags.append(f"{t} senza obiettivi a fine stagione")
        if c.get(f"{side}_late_top"):
            tags.append(f"{t} già sicura del piazzamento")
    names_h = ", ".join(o[0] for o in sorted(_new(info["h_outs"]), key=lambda o: o[2])[:3])
    names_a = ", ".join(o[0] for o in sorted(_new(info["a_outs"]), key=lambda o: o[2])[:3])
    # se le assenze favoriscono la squadra stessa, il modello valuta meglio chi entra al loro posto
    note_h = "; il modello valuta meglio chi li sostituisce" if f["ass_h"] > 0 else ""
    note_a = "; il modello valuta meglio chi li sostituisce" if f["ass_a"] < 0 else ""
    label = {"campo": "Fattore campo", "roster": "Qualità dei giocatori disponibili",
             "ass_h": f"Assenze {h}" + (f" ({names_h}{note_h})" if names_h else ""),
             "ass_a": f"Assenze {a}" + (f" ({names_a}{note_a})" if names_a else ""),
             "contesto": "Riposo e calendario" + (f" ({'; '.join(tags)})" if tags else ""),
             "altri": "Risultati recenti (altri modelli dell'ensemble)"}
    top = sorted(f.items(), key=lambda kv: -abs(kv[1]))[:3]
    why = [f"{label[k]}: +{_n(v)} per {h if v >= 0 else a}" for k, v in top if abs(v) >= 0.05]
    return why, f


def _motivo(r, f, info, mk) -> str | None:
    if mk is None or mk.get("sp") is None:
        return None
    diff = r["m_final"] + mk["sp"]
    if abs(diff) < 3:
        return None
    codes = []
    if info["h_quest"] or info["a_quest"]:
        codes.append("DUBBI: giocatori importanti in dubbio, il mercato può sapere di più")
    if max(abs(f["ass_h"]), abs(f["ass_a"])) >= 2.5:
        codes.append("ASSENZE: il modello pesa molto le assenze dell'injury report")
    if abs(f["contesto"]) >= 1.5:
        codes.append("RIPOSO: forte effetto di riposo o calendario")
    if min(info["h_gp"], info["a_gp"]) < 10:
        codes.append("POCHE_PARTITE: meno di 10 partite giocate in stagione")
    if abs(r["m_base"] - r["m_players"]) >= 4:
        codes.append("MODELLI_DIVERSI: modello giocatori e baseline in disaccordo")
    if not codes:
        codes.append("SCONOSCIUTO: probabilmente al modello manca un'informazione (notizie, riposi non annunciati)")
    return f"Modello {'+' if diff > 0 else '-'}{_n(diff)} rispetto alla linea. " + " | ".join(codes)


SLIM = ("d", "a", "h", "tip", "t", "src", "mv", "ap", "hp", "m", "p", "sd", "tot", "outA", "outH", "why", "dmk", "motivo",
        "injAsOf")


def slim(r: dict) -> dict:
    """Riga ridotta per il database della pagina (senza la scomposizione completa dei fattori)."""
    out = {k: r[k] for k in SLIM if k in r and r[k] is not None}
    if r.get("mk"):
        out["mk"] = {k: r["mk"][k] for k in ("sp", "tot", "ph", "src") if r["mk"].get(k) is not None}
    return out


def sync_page(D: str) -> None:
    """predictions/pagina_sync.json: le partite del giorno D e del giorno prima, già nel formato dei documenti
    nba/newlog-AAAA-MM del database della pagina (l'attività pianificata le copia con un merge)."""
    docs = {}
    for day in (str((pd.Timestamp(D) - pd.Timedelta(days=1)).date()), D):
        f = OUT / f"{day}.json"
        if not f.exists():
            continue
        for k, r in json.loads(f.read_text()).get("g", {}).items():
            docs.setdefault(f"nba/newlog-{day[:7]}", {"g": {}})["g"][k] = slim(r)
    (OUT / "pagina_sync.json").write_text(json.dumps({"generato": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                       "giorni": D, "docs": docs}, ensure_ascii=False, separators=(",", ":")))


def write(season: int, D: str, x: pd.DataFrame, detail: dict) -> str:
    OUT.mkdir(exist_ok=True)
    now = pd.Timestamp.now(tz="UTC")
    mv = model_version()
    lines = pd.read_parquet(path("processed") / f"lines_{season}.parquet") if (path("processed") / f"lines_{season}.parquet").exists() else pd.DataFrame()
    g = pd.read_parquet(path("processed") / f"games_{season}.parquet")
    tips = dict(zip(g["game_id"], g["tip_utc_espn"]))
    day = x[(x["season"] == season) & (x["date"] == D)]
    f_day = OUT / f"{D}.json"
    doc = json.loads(f_day.read_text()) if f_day.exists() else {"meta": {}, "g": {}}
    written, frozen, reg = 0, 0, []
    for _, r in day.iterrows():
        info = detail.get(r["game_id"])
        if info is None:
            continue
        key = f"{D}_{r['away']}_{r['home']}"
        tip = tips.get(r["game_id"])
        if tip and pd.Timestamp(tip) <= now and key in doc["g"]:
            frozen += 1                    # già iniziata: resta il pronostico congelato
            continue
        if tip and pd.Timestamp(tip) <= now:
            continue                       # iniziata e mai pubblicata: non si pubblica a posteriori
        mk = None
        if len(lines):
            ln = lines[lines["game_id"] == r["game_id"]]
            if len(ln) and pd.notna(ln.iloc[0]["close_spread_home"]):
                l0 = ln.iloc[0]
                mk = {"sp": float(l0["close_spread_home"]), "tot": None if pd.isna(l0["close_total"]) else float(l0["close_total"]),
                      "ph": None if pd.isna(l0["p_home_mkt"]) else round(float(l0["p_home_mkt"]), 3),
                      "src": f"{l0['main_book']} via ESPN", "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        why, f = _why(r, info)
        row = {"d": D, "a": r["away"], "h": r["home"], "tip": tip, "t": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "src": "dal vivo", "mv": mv, "ap": round(float(r["ap"]), 1), "hp": round(float(r["hp"]), 1),
               "m": round(float(r["m_final"]), 1), "p": round(float(r["p_home"]), 3), "sd": round(float(r["sd"]), 1),
               "tot": round(float(r["t_final"]), 1), "outA": _outs(info["a_outs"]), "outH": _outs(info["h_outs"]),
               "why": why, "mk": mk, "dmk": None if mk is None else round(float(r["m_final"]) + mk["sp"], 1),
               "motivo": _motivo(r, f, info, mk), "injAsOf": info.get("report_ts"),
               "fattori": {k: round(float(v), 2) for k, v in f.items()}}
        doc["g"][key] = row
        written += 1
        reg.append({k: row[k] for k in ("d", "a", "h", "tip", "t", "mv", "ap", "hp", "m", "p", "sd", "tot", "dmk")}
                   | {"mk_sp": None if mk is None else mk["sp"], "mk_tot": None if mk is None else mk["tot"],
                      "mk_ph": None if mk is None else mk["ph"]})
    doc["meta"] = {"aggiornato": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "modello": mv, "data": D,
                   "nota": "Pronostici informativi, non consigli di scommessa. Quando il modello si stacca di 3 punti o più "
                           "dalla linea, nei test ha avuto ragione più spesso il mercato."}
    txt = json.dumps(doc, ensure_ascii=False, indent=1)
    f_day.write_text(txt)
    (OUT / "latest.json").write_text(txt)
    sync_page(D)
    if reg:
        rf = OUT / f"registro_{season}.csv"
        old = pd.read_csv(rf) if rf.exists() else pd.DataFrame()
        pd.concat([old, pd.DataFrame(reg)], ignore_index=True).to_csv(rf, index=False)
    # pronostici ricostruiti della stagione (partite concluse) con mercato e risultato
    done = x[(x["season"] == season) & x["hpts"].notna()].copy()
    if len(done):
        cols = ["game_id", "date", "away", "home", "apts", "hpts", "m_final", "t_final", "p_home", "sd", "m_base", "m_players"]
        rc = done[cols]
        if len(lines):
            rc = rc.merge(lines[["game_id", "close_spread_home", "close_total", "p_home_mkt"]], on="game_id", how="left")
        rc.round(3).to_csv(OUT / f"ricostruiti_{season}.csv", index=False)
    summary = [f"{D}: {written} pronostici pubblicati, {frozen} partite già iniziate lasciate com'erano"]
    for k, r in sorted(doc["g"].items()):
        mk = r.get("mk") or {}
        fav = r["h"] if r["p"] >= 0.5 else r["a"]
        line = f"{r['a']} {r['ap']} - {r['hp']} {r['h']} | {fav} {round(max(r['p'], 1 - r['p']) * 100)}%"
        if mk:
            line += f" | linea {r['h']} {mk['sp']:+.1f}"
        summary.append(line + (" | " + r["motivo"] if r.get("motivo") else ""))
    return "\n".join(summary)
