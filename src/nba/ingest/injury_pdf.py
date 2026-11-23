"""Lettura dei PDF degli injury report ufficiali NBA.

Colonne del report: Game Date | Game Time | Matchup | Team | Player Name | Current Status | Reason.
Data, ora, partita e squadra compaiono solo sulla prima riga del loro blocco: vanno riportate sulle righe sotto.
Il motivo può andare a capo: la riga successiva con il solo motivo si unisce a quella sopra.
Le colonne si riconoscono dalla posizione orizzontale delle intestazioni, pagina per pagina.
"""
from __future__ import annotations

import io
import re

import pandas as pd

TEAM_NAMES = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN", "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET", "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}
STATUSES = ["Out", "Doubtful", "Questionable", "Probable", "Available"]
HEADERS = ["Game Date", "Game Time", "Matchup", "Team", "Player Name", "Current Status", "Reason"]
COLS = ["game_date", "game_time", "matchup", "team_name", "player", "status", "reason"]
DATE_RX = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TIME_RX = re.compile(r"^\d{1,2}:\d{2}\s*\(?ET\)?$|^\d{1,2}:\d{2}$")
MATCH_RX = re.compile(r"^[A-Z]{2,3}@[A-Z]{2,3}$")


def _header_positions(words):
    """x di inizio di ogni colonna, dalle parole dell'intestazione."""
    pos = {}
    toks = [(w["text"], w["x0"], w["top"]) for w in words]
    for h in HEADERS:
        first = h.split()[0]
        second = h.split()[1] if " " in h else None
        for i, (t, x, top) in enumerate(toks):
            if t == first and (second is None or (i + 1 < len(toks) and toks[i + 1][0] == second)):
                if h == "Team" and i > 0 and toks[i - 1][0] in ("Game",):
                    continue
                pos.setdefault(h, (x, top))
                break
    return pos


def _lines(words, tol=3.0):
    """Raggruppa le parole in righe per posizione verticale."""
    words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    lines, cur, y = [], [], None
    for w in words:
        if y is None or abs(w["top"] - y) <= tol:
            cur.append(w)
            y = w["top"] if y is None else y
        else:
            lines.append(cur)
            cur, y = [w], w["top"]
    if cur:
        lines.append(cur)
    return lines


def parse_pdf(content: bytes) -> pd.DataFrame:
    import pdfplumber
    rows = []
    report_title = ""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        bounds = None
        last = {c: "" for c in COLS}
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=1.5, y_tolerance=2)
            if not words:
                continue
            text = " ".join(w["text"] for w in words[:12])
            m = re.search(r"Injury Report:\s*([\d/]+\s+[\d:]+\s*[AP]M)", text)
            if m:
                report_title = m.group(1)
            hp = _header_positions(words)
            if len(hp) >= 6:
                xs = sorted((v[0], k) for k, v in hp.items())
                bounds = [(x, HEADERS.index(k)) for x, k in xs]
                header_y = max(v[1] for v in hp.values())
            else:
                header_y = -1
            if bounds is None:
                continue
            for ln in _lines(words):
                if ln[0]["top"] <= header_y + 2:
                    continue
                cells = [""] * 7
                for w in ln:
                    ci = 0
                    for x, idx in bounds:
                        if w["x0"] >= x - 2:
                            ci = idx
                    cells[ci] = (cells[ci] + " " + w["text"]).strip()
                line_text = " ".join(cells)
                if line_text.startswith("Page ") or "Injury Report:" in line_text:
                    continue
                # riga di solo motivo che va a capo: la unisco alla precedente
                if not any(cells[:6]) and cells[6] and rows:
                    rows[-1]["reason"] = (rows[-1]["reason"] + " " + cells[6]).strip()
                    continue
                rec = dict(zip(COLS, cells))
                for c in ("game_date", "game_time", "matchup", "team_name"):
                    if rec[c]:
                        last[c] = rec[c]
                        if c in ("game_date", "game_time", "matchup"):
                            # nuova partita: la squadra va riletta
                            if c == "matchup":
                                last["team_name"] = rec["team_name"] or ""
                    else:
                        rec[c] = last[c]
                if rec["team_name"]:
                    last["team_name"] = rec["team_name"]
                if not rec["player"] and "NOT YET SUBMITTED" in line_text.upper():
                    rec["status"] = "NOT YET SUBMITTED"
                if not rec["player"] and rec["status"] != "NOT YET SUBMITTED":
                    continue
                rows.append(rec)
    df = pd.DataFrame(rows, columns=COLS)
    if df.empty:
        return df
    df["team"] = df["team_name"].map(TEAM_NAMES)
    df["status"] = df["status"].str.strip()
    # "Cognome, Nome" -> "Nome Cognome"
    df["player_name"] = df["player"].map(lambda s: " ".join(reversed([p.strip() for p in s.split(",", 1)])) if "," in s else s)
    df["report"] = report_title
    return df
