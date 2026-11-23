"""Lettura dei PDF degli injury report ufficiali NBA (formato uguale dal 2019 a oggi).

Colonne: GameDate | GameTime | Matchup | Team | PlayerName | CurrentStatus | Reason.
- Nel PDF le parole non hanno spazi ("LosAngelesLakers", "PorterJr.,Michael"): squadre e nomi si confrontano
  senza spazi (vedi name_key).
- Data, ora, partita e squadra compaiono solo sulla prima riga del loro blocco: si riportano sulle righe sotto.
- Il motivo può andare a capo sopra e sotto la riga del giocatore: ogni frammento si attacca alla riga del
  giocatore più vicina in verticale.
- Le colonne si riconoscono dalla posizione delle intestazioni, pagina per pagina.
"""
from __future__ import annotations

import io
import re
import unicodedata

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
TEAM_NOSPACE = {k.replace(" ", "").lower(): v for k, v in TEAM_NAMES.items()}
# Formato 2018-19 → 2020-21: in più "Category" e "Previous Status"; dal 2021-22 solo le 7 colonne principali
HEADER_TOKENS = ["GameDate", "GameTime", "Matchup", "Team", "PlayerName", "CurrentStatus", "Reason", "Category", "PreviousStatus"]
COLS = ["game_date", "game_time", "matchup", "team_name", "player", "status", "reason", "category", "prev_status"]
NC = len(COLS)
STATUSES = {"out", "doubtful", "questionable", "probable", "available"}
_SUFFIX = re.compile(r"(jr|sr|iii|ii|iv)$")


def name_key(name: str) -> str:
    """Chiave di confronto dei nomi: minuscolo, senza accenti, spazi, punteggiatura e suffissi (Jr., III...)."""
    s = unicodedata.normalize("NFD", "" if name is None or name is pd.NA or (isinstance(name, float) and name != name) else str(name))
    s = re.sub(r"[̀-ͯ]", "", s).lower()
    s = re.sub(r"[^a-z]", "", s)
    return _SUFFIX.sub("", s)


PAIRS = {("Game", "Date"): "GameDate", ("Game", "Time"): "GameTime", ("Player", "Name"): "PlayerName",
         ("Current", "Status"): "CurrentStatus", ("Previous", "Status"): "PreviousStatus"}


def _header(words):
    """Inizio delle colonne dalla riga di intestazione (con o senza spazi: "Game Date" oppure "GameDate")."""
    m = [w for w in words if w["text"] == "Matchup"]
    if not m:
        return None, None
    hy = m[0]["top"]
    line = sorted([w for w in words if abs(w["top"] - hy) < 3], key=lambda w: w["x0"])
    bounds, i = [], 0
    while i < len(line):
        t = line[i]["text"]
        nxt = line[i + 1]["text"] if i + 1 < len(line) else None
        if (t, nxt) in PAIRS:
            bounds.append((line[i]["x0"], HEADER_TOKENS.index(PAIRS[(t, nxt)])))
            i += 2
            continue
        if t in HEADER_TOKENS:
            bounds.append((line[i]["x0"], HEADER_TOKENS.index(t)))
        i += 1
    if len(bounds) < 6:
        return None, None
    return sorted(bounds), max(w["top"] for w in line)


def _team_code(t: str):
    return TEAM_NOSPACE.get(re.sub(r"[^A-Za-z0-9]", "", t or "").lower())


def _lines(words, tol=2.5):
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    out, cur, y = [], [], None
    for w in words:
        if y is None or abs(w["top"] - y) <= tol:
            cur.append(w)
            if y is None:
                y = w["top"]
        else:
            out.append((y, cur))
            cur, y = [w], w["top"]
    if cur:
        out.append((y, cur))
    return out


def parse_pdf(content: bytes) -> pd.DataFrame:
    import pdfplumber
    rows, title = [], ""
    last = {c: "" for c in ("game_date", "game_time", "matchup", "team_name")}
    bounds = None
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue
            b_, hy_ = _header(words)
            if b_ is not None:
                bounds, hy = b_, hy_
            elif bounds is not None:
                # pagine successive senza intestazione: stesse colonne, salto solo il titolo in alto
                tl = [w["top"] for w in words if w["text"] in ("Injury", "Report:")]
                hy = (max(tl) + 5) if tl else -1
            else:
                continue
            t = re.search(r"Injury Report:\s*(\S+\s+\S+\s+[AP]M)", " ".join(w["text"] for w in words if w["top"] < hy))
            if t:
                title = t.group(1)
            anchors, loose = [], []
            for y, ln in _lines([w for w in words if w["top"] > hy + 2]):
                cells = [""] * NC
                for w in ln:
                    ci = 0
                    for x, idx in bounds:
                        if w["x0"] >= x - 3:
                            ci = idx
                    cells[ci] = (cells[ci] + " " + w["text"]).strip()
                txt = "".join(cells)
                if re.fullmatch(r"Page\d+of\d+", txt.replace(" ", "")):
                    continue
                if cells[4] or "NOTYETSUBMITTED" in txt.replace(" ", ""):
                    anchors.append([y, cells])
                else:
                    loose.append((y, cells))
            if not anchors:
                continue
            # frammenti (motivo a capo, o campi della partita su una riga a sé): alla riga di giocatore più vicina
            frag = {i: [] for i in range(len(anchors))}
            for y, cells in loose:
                i = min(range(len(anchors)), key=lambda k: abs(anchors[k][0] - y))
                frag[i].append((y, cells))
            for i, (y, cells) in enumerate(anchors):
                parts = sorted(frag[i] + [(y, cells)], key=lambda z: z[0])
                merged = [" ".join(p[1][c] for p in parts if p[1][c]).strip() for c in range(NC)]
                # nome e stato: quelli della riga del giocatore; dai frammenti solo se mancano
                for c in (4, 5):
                    if cells[c]:
                        merged[c] = cells[c]
                rec = dict(zip(COLS, merged))
                for c in ("game_date", "game_time", "matchup"):
                    if rec[c]:
                        last[c] = rec[c]
                        if c == "matchup":
                            last["team_name"] = ""
                    else:
                        rec[c] = last[c]
                if rec["team_name"]:
                    last["team_name"] = rec["team_name"]
                else:
                    rec["team_name"] = last["team_name"]
                if "NOTYETSUBMITTED" in "".join(merged).replace(" ", ""):
                    rec["player"], rec["status"] = "", "NOT YET SUBMITTED"
                rows.append(rec)
    df = pd.DataFrame(rows, columns=COLS)
    if df.empty:
        return df
    df["team"] = df["team_name"].map(_team_code)
    df["status"] = df["status"].str.strip()
    df["player_name"] = df["player"].map(lambda s: " ".join(reversed([p.strip() for p in s.split(",", 1)])) if "," in s else s)
    df["player_key"] = df["player_name"].map(name_key)
    df["game_time"] = df["game_time"].str.replace("(ET)", "", regex=False).str.strip()
    df["report"] = title
    # nel formato vecchio la categoria (es. "G League Team", "Injury/Illness") va davanti al motivo
    has_cat = df["category"].fillna("") != ""
    df.loc[has_cat, "reason"] = (df.loc[has_cat, "category"] + " - " + df.loc[has_cat, "reason"]).str.strip(" -")
    return df
