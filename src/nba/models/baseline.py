"""Baseline: riscrittura fedele in Python del modello v2 della pagina (baseline_model.js).

Stessi ingressi della pagina (testo: calendario, risultati, CSV giocatori, infortuni, BPM stagione precedente),
stessi calcoli, stessi parametri. Il test di equivalenza (tests/test_baseline_equivalence.py) confronta questo
codice con il JavaScript originale eseguito in Node sugli stessi dati.

Differenze volute rispetto al JS: nessuna nei calcoli. Non riproduco il backtest interno, i grafici e la
simulazione della stagione, che non servono a pronosticare le partite.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np

TEAMS = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM",
         "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]
TIDX = {c: i for i, c in enumerate(TEAMS)}
NT = 30
ALIAS = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX", "NO": "NOP", "NY": "NYK", "SA": "SAS", "GS": "GSW",
         "UTAH": "UTA", "WSH": "WAS"}

DEFAULTS = dict(lambda_=8.0, halfLife=30.0, Hprior=2.2, Hlambda=200.0, sigma=10.5, kVar=1.0, movCap=20.0, movK=0.5,
                b2b=1.0, restK=0.0, altK=0.0, injK=0.6, repl=-3.0, bpmPriorMin=300.0, prevW=700.0, rust=0.85,
                rosterK=1.25)
BOX = [-11.117, 1.042, 0.384, 0.877, 1.493, 1.098, -1.649, -0.859, -0.384, 0.474]
DAY0 = dt.date(2026, 10, 1)


def team(t) -> str:
    t = str(t or "").strip().upper()
    return ALIAS.get(t, t)


def day_idx(d: str) -> int:
    y, m, dd = (int(x) for x in str(d)[:10].split("-"))
    return (dt.date(y, m, dd) - DAY0).days


_COMB = re.compile(r"[̀-ͯ]")
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv)\b")


def norm_name(n) -> str:
    s = unicodedata.normalize("NFD", str(n or ""))
    s = _COMB.sub("", s).lower().replace("-", " ")
    s = re.sub(r"[^a-z ]", "", s)
    s = _SUFFIX.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def Phi(x: float) -> float:
    """Stessa approssimazione della normale cumulativa usata nella pagina (Abramowitz-Stegun)."""
    z = abs(x) / math.sqrt(2)
    t = 1 / (1 + 0.3275911 * z)
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * math.exp(-z * z)
    return (1 + y) / 2 if x >= 0 else (1 - y) / 2


def clamp(x, a, b):
    return max(a, min(b, x))


_NUM = re.compile(r"^\s*([+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?)")


def num(x):
    """Come parseFloat di JavaScript: numero iniziale della stringa, altrimenti None."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    m = _NUM.match(str(x))
    return float(m.group(1)) if m else None


@dataclass
class Player:
    name: str
    t: str
    key: str
    g: float = 0.0
    mpg: float = 0.0
    pts: float = 0.0
    trb: float = 0.0
    ast: float = 0.0
    fg3: float = 0.0
    stl: float = 0.0
    blk: float = 0.0
    tov: float = 0.0
    fga: float = 0.0
    fta: float = 0.0
    bpm: float | None = None
    mptot: float | None = None
    usg: float | None = None
    box: bool = True
    prev: dict | None = None
    prevOnly: bool = False
    inj: dict | None = None
    bpmS: float = 0.0
    bpmPrior: float = 0.0
    value: float = 0.0
    f: float = 1.0


@dataclass
class Game:
    d: str
    di: int
    a: str
    h: str
    played: bool = False
    as_: float | None = None
    hs: float | None = None
    ot: str = ""


@dataclass
class Data:
    games: list
    players: dict
    injuries: list
    gp: dict = field(default_factory=dict)
    ppg: dict = field(default_factory=dict)


def _csv_rows(rows):
    out, header = [], None
    for line in rows or []:
        parts = line.split(",")
        if header is None:
            if re.match(r"^player", parts[0], re.I):
                header = [h.strip() for h in parts]
                continue
        if header is not None:
            out.append({h: (parts[i] if i < len(parts) else None) for i, h in enumerate(header)})
    return out


def parse_data(raw: dict) -> Data:
    games, by_key = [], {}

    def add_game(d, a, h):
        a, h = team(a), team(h)
        if a not in TIDX or h not in TIDX or a == h:
            return None
        k = f"{d}|{a}|{h}"
        if k in by_key:
            return by_key[k]
        g = Game(d=d, di=day_idx(d), a=a, h=h)
        games.append(g)
        by_key[k] = g
        return g

    for s in raw.get("schedule") or []:
        p = s.split(",")
        if len(p) >= 3:
            add_game(p[0], p[1], p[2])
    for s in raw.get("extra") or []:
        p = re.split(r"[|,]", s)
        if len(p) >= 3:
            add_game(p[0], p[1], p[2])
    for s in raw.get("results") or []:
        p = re.split(r"[|,]", s)
        if len(p) < 5:
            continue
        d, a, as_, h, hs = p[0], team(p[1]), num(p[2]), team(p[3]), num(p[4])
        if as_ is None or hs is None:
            continue
        g = by_key.get(f"{d}|{a}|{h}")
        if g is None:
            di = day_idx(d)
            g = next((x for x in games if x.a == a and x.h == h and abs(x.di - di) <= 1 and not x.played), None)
        if g is None:
            g = add_game(d, a, h)
        if g is None:
            continue
        g.played, g.as_, g.hs, g.ot = True, as_, hs, (p[5] if len(p) > 5 else "").strip()
    games.sort(key=lambda x: (x.di, x.h))

    players = {c: [] for c in TEAMS}
    p_index: dict[str, Player] = {}
    for r in _csv_rows(raw.get("pergame")):
        t = team(r.get("Team"))
        if t not in TIDX:
            continue
        name = (r.get("Player") or "").strip()
        k = f"{t}|{norm_name(name)}"
        if k in p_index:
            continue
        p = Player(name=name, t=t, key=k, g=num(r.get("G")) or 0, mpg=num(r.get("MP")) or 0, pts=num(r.get("PTS")) or 0,
                   trb=num(r.get("TRB")) or 0, ast=num(r.get("AST")) or 0, fg3=num(r.get("3P")) or 0,
                   stl=num(r.get("STL")) or 0, blk=num(r.get("BLK")) or 0, tov=num(r.get("TOV")) or 0,
                   fga=num(r.get("FGA")) or 0, fta=num(r.get("FTA")) or 0, box=True)
        players[t].append(p)
        p_index[k] = p
    for r in _csv_rows(raw.get("advanced")):
        t = team(r.get("Team"))
        if t not in TIDX:
            continue
        name = (r.get("Player") or "").strip()
        k = f"{t}|{norm_name(name)}"
        p = p_index.get(k)
        if p is None:
            p = Player(name=name, t=t, key=k, g=num(r.get("G")) or 0, box=False)
            players[t].append(p)
            p_index[k] = p
        p.bpm, p.mptot, p.usg = num(r.get("BPM")), num(r.get("MP")), num(r.get("USG"))
        if not p.mpg and p.mptot and p.g:
            p.mpg = p.mptot / p.g

    prev = {}
    for r in _csv_rows(raw.get("prev")):
        k, mp, g, bpm = norm_name(r.get("Player")), num(r.get("MP")), num(r.get("G")), num(r.get("BPM"))
        if k and mp is not None and bpm is not None and k not in prev:
            prev[k] = {"mp": mp, "g": g or 1, "bpm": bpm}
    for p in p_index.values():
        q = prev.get(norm_name(p.name))
        if q:
            p.prev = q

    injuries = []
    for line in raw.get("injuries") or []:
        p = line.split("|")
        if len(p) < 3 or re.match(r"^team$", p[0], re.I):
            continue
        t = team(p[0])
        if t not in TIDX:
            continue
        ret = (p[3] if len(p) > 3 else "").strip()
        injuries.append({"t": t, "name": p[1].strip(), "key": f"{t}|{norm_name(p[1])}", "status": (p[2] or "").strip(),
                         "ret": ret, "retIdx": day_idx(ret) if re.match(r"^\d{4}-\d{2}-\d{2}$", ret) else None})
    for inj in injuries:
        p = p_index.get(inj["key"])
        if p is None:
            nn = inj["key"].split("|", 1)[1]
            p = next((q for q in p_index.values() if norm_name(q.name) == nn), None)
        if p is None:
            q = prev.get(inj["key"].split("|", 1)[1])
            if q and q["mp"] >= 150:
                p = Player(name=inj["name"], t=inj["t"], key=inj["key"], mpg=clamp(q["mp"] / q["g"], 10, 32), mptot=0,
                           box=False, prev=q, prevOnly=True)
                players[inj["t"]].append(p)
                p_index[inj["key"]] = p
        inj["player"] = p
        if p is not None:
            p.inj = inj
    return Data(games=games, players=players, injuries=injuries)


# ---------- rating di squadra ----------
@dataclass
class Ratings:
    mu: float
    H: float
    O: dict
    D: dict
    net: dict
    n: int
    Ainv: np.ndarray
    s2: float
    netVar: dict


def fit_ratings(games: list, cutoff: int, P: dict) -> Ratings:
    n = 2 + 2 * NT
    A = np.zeros((n, n))
    b = np.zeros(n)
    played = [g for g in games if g.played and g.di < cutoff]
    rows, ys, ws = [], [], []
    for g in played:
        w = 0.5 ** ((cutoff - g.di) / P["halfLife"])
        h, a = TIDX[g.h], TIDX[g.a]
        hs, as_ = g.hs, g.as_
        if P["movCap"]:
            m = hs - as_
            am = abs(m)
            if am > P["movCap"]:
                nm = math.copysign(P["movCap"] + (am - P["movCap"]) * P["movK"], m)
                mid = (hs + as_) / 2
                hs, as_ = mid + nm / 2, mid - nm / 2
        rows.append(([0, 1, 2 + h, 2 + NT + a], [1, 0.5, 1, -1], hs, w))
        rows.append(([0, 1, 2 + a, 2 + NT + h], [1, -0.5, 1, -1], as_, w))
    for cols, vals, y, w in rows:
        v = np.array(vals, float)
        b[cols] += w * v * y
        A[np.ix_(cols, cols)] += w * np.outer(v, v)
    idx = np.arange(2, n)
    A[idx, idx] += P["lambda_"]
    if P.get("priorNet"):
        for i, c in enumerate(TEAMS):
            v = (P["priorNet"].get(c) or 0) / 2
            b[2 + i] += P["lambda_"] * v
            b[2 + NT + i] += P["lambda_"] * v
    A[1, 1] += P["Hlambda"]
    b[1] += P["Hlambda"] * P["Hprior"]
    A[0, 0] += 1e-3
    b[0] += 1e-3 * 113
    x = np.linalg.solve(A, b)
    Ainv = np.linalg.inv(A)
    O = {c: x[2 + i] for i, c in enumerate(TEAMS)}
    D = {c: x[2 + NT + i] for i, c in enumerate(TEAMS)}
    net = {c: O[c] + D[c] for c in TEAMS}
    mu, H = x[0], x[1]
    s2 = w2 = 0.0
    for g in played:
        w = 0.5 ** ((cutoff - g.di) / P["halfLife"])
        eh = g.hs - (mu + H / 2 + O[g.h] - D[g.a])
        ea = g.as_ - (mu - H / 2 + O[g.a] - D[g.h])
        s2 += w * (eh * eh + ea * ea)
        w2 += 2 * w
    s2 = s2 / w2 if w2 else 120.0
    netVar = {c: s2 * (Ainv[2 + i, 2 + i] + Ainv[2 + NT + i, 2 + NT + i] + 2 * Ainv[2 + i, 2 + NT + i])
              for i, c in enumerate(TEAMS)}
    return Ratings(mu=mu, H=H, O=O, D=D, net=net, n=len(played), Ainv=Ainv, s2=s2, netVar=netVar)


def margin_var(R: Ratings, h: str, a: str) -> float:
    idx = [1, 2 + TIDX[h], 2 + NT + TIDX[h], 2 + TIDX[a], 2 + NT + TIDX[a]]
    v = np.array([1, 1, 1, -1, -1], float)
    return float(R.s2 * v @ R.Ainv[np.ix_(idx, idx)] @ v)


# ---------- giocatori e assenze ----------
def prepare_players(data: Data, P: dict):
    gp = {c: 0 for c in TEAMS}
    ppg = {c: 0.0 for c in TEAMS}
    for g in data.games:
        if g.played:
            gp[g.h] += 1
            gp[g.a] += 1
            ppg[g.h] += g.hs
            ppg[g.a] += g.as_
    for c in TEAMS:
        ppg[c] = ppg[c] / gp[c] if gp[c] else 113.0
    for t in TEAMS:
        for p in data.players[t]:
            bpm_box = None
            if p.box and p.mpg > 0:
                f = lambda v: v * 36 / p.mpg  # noqa: E731
                xs = [1, f(p.pts), f(p.trb), f(p.ast), f(p.stl), f(p.blk), f(p.tov), f(p.fga), f(p.fta), f(p.fg3)]
                bpm_box = sum(v * BOX[i] for i, v in enumerate(xs))
            raw = p.bpm if p.bpm is not None else (bpm_box if bpm_box is not None else -2)
            mp = 0 if p.prevOnly else (p.mptot if p.mptot is not None else p.g * p.mpg)
            pts_prior = clamp(-3 + 0.18 * p.pts, -3, 4) if p.pts else -2
            prior, W = pts_prior, P["bpmPriorMin"]
            if p.prev and p.prev["mp"] >= 150:
                prior = (p.prev["bpm"] * p.prev["mp"] + -1.5 * 500) / (p.prev["mp"] + 500)
                W = max(P["prevW"] * min(1, p.prev["mp"] / 1500), P["bpmPriorMin"])
            p.bpmPrior = prior
            p.bpmS = (raw * mp + prior * W) / (mp + W)
            p.value = max(0.0, (p.bpmS - P["repl"]) * p.mpg / 48) * (P["rust"] if p.prevOnly else 1)
            p.f = 0.0 if p.prevOnly else (clamp(p.g / gp[t], 0, 1) if gp[t] else 1.0)
    data.gp, data.ppg = gp, ppg


def roster_prior(data: Data) -> dict:
    out = {}
    for t in TEAMS:
        s = m = 0.0
        for p in data.players[t]:
            if p.prevOnly or not p.mpg:
                continue
            w = p.mpg * (1 if p.f is None else p.f)
            b = ((p.prev["bpm"] * p.prev["mp"] + -1.5 * 500) / (p.prev["mp"] + 500)
                 if p.prev and p.prev["mp"] >= 150 else -2)
            s += b * w
            m += w
        out[t] = s * (240 / m) / 48 if m else 0.0
    avg = sum(out.values()) / NT
    return {c: out[c] - avg for c in TEAMS}


def availability(p: Player, di: int) -> float:
    inj = p.inj
    if not inj:
        return 1.0
    st, r = inj["status"].lower(), inj["retIdx"]
    if "out" in st or "fuori" in st or "susp" in st:
        if r is None:
            return 0.0
        return 0.0 if di < r else (0.5 if di == r else 1.0)
    if "doubt" in st:
        return 0.25 if r is None or di <= r else 1.0
    if "day" in st or "quest" in st or "dubbio" in st:
        return 0.5 if r is None or di <= r else 1.0
    if "prob" in st:
        return 0.85 if r is None or di <= r else 1.0
    return 1.0


def team_adj(data: Data, t: str, di: int, P: dict) -> dict:
    delta, out = 0.0, []
    for p in data.players[t]:
        if not p.value:
            continue
        if p.inj:
            av = availability(p, di)
            contrib = P["injK"] * p.value * (av - p.f)
            if av < 1 and p.value >= 0.4 and not p.prevOnly:
                out.append({"name": p.name, "av": av, "impact": -P["injK"] * p.value * (1 - av)})
        else:
            contrib = 0.6 * P["injK"] * p.value * (1 - p.f) if p.f < 0.8 else 0.0
        delta += contrib
    out.sort(key=lambda o: o["impact"])
    return {"delta": clamp(delta, -14, 10), "out": out}


# ---------- contesto e pronostico ----------
@dataclass
class Context:
    P: dict
    data: Data
    today_idx: int
    rest: dict
    R: Ratings
    adj_cache: dict = field(default_factory=dict)


def build(raw: dict, today: str | None = None, **opts) -> Context:
    return build_from_data(parse_data(raw), today, **opts)


def build_from_data(data: Data, today: str | None = None, **opts) -> Context:
    """Come build, partendo da dati già letti (utile per provare più parametri sugli stessi ingressi)."""
    P = dict(DEFAULTS)
    P.update(opts)
    prepare_players(data, P)
    if P["rosterK"]:
        rp = roster_prior(data)
        P["priorNet"] = {c: P["rosterK"] * rp[c] for c in TEAMS}
    if today:
        today_idx = day_idx(today)
    else:
        today_idx = max((g.di for g in data.games if g.played), default=0) + 1
    last, rest = {}, {}
    for g in sorted(data.games, key=lambda x: x.di):
        for t in (g.h, g.a):
            l_ = last.get(t)
            rest[f"{t}@{g.di}"] = 9 if l_ is None else g.di - l_
            last[t] = g.di
    R = fit_ratings(data.games, today_idx, P)
    return Context(P=P, data=data, today_idx=today_idx, rest=rest, R=R)


def _rest_val(P, r):
    return -P["b2b"] if r <= 1 else (P["restK"] if r >= 3 else 0.0)


def sched_adj(ctx: Context, g: Game) -> dict:
    rH = ctx.rest.get(f"{g.h}@{g.di}") or 2
    rA = ctx.rest.get(f"{g.a}@{g.di}") or 2
    m = _rest_val(ctx.P, rH) - _rest_val(ctx.P, rA) + (ctx.P["altK"] if g.h in ("DEN", "UTA") else 0)
    return {"m": m, "b2bH": rH <= 1, "b2bA": rA <= 1}


def adj_for(ctx: Context, t: str, di: int) -> dict:
    k = f"{t}@{di}"
    if k not in ctx.adj_cache:
        ctx.adj_cache[k] = team_adj(ctx.data, t, di, ctx.P)
    return ctx.adj_cache[k]


def predict(ctx: Context, g: Game, no_inj: bool = False) -> dict:
    R, P = ctx.R, ctx.P
    zero = {"delta": 0.0, "out": []}
    ah = zero if no_inj else adj_for(ctx, g.h, g.di)
    aa = zero if no_inj else adj_for(ctx, g.a, g.di)
    sa = sched_adj(ctx, g)
    rH = ah["delta"] + sa["m"] / 2
    rA = aa["delta"] - sa["m"] / 2
    hp = R.mu + R.H / 2 + R.O[g.h] - R.D[g.a] + rH / 2 - rA / 2
    ap = R.mu - R.H / 2 + R.O[g.a] - R.D[g.h] + rA / 2 - rH / 2
    margin = hp - ap
    sd = math.sqrt(P["sigma"] ** 2 + P["kVar"] * margin_var(R, g.h, g.a))
    return {"hp": hp, "ap": ap, "margin": margin, "sd": sd, "total": hp + ap, "pHome": Phi(margin / sd),
            "adjH": ah, "adjA": aa, "b2bH": sa["b2bH"], "b2bA": sa["b2bA"]}


def find_game(ctx: Context, d: str, a: str, h: str) -> Game | None:
    return next((x for x in ctx.data.games if x.d == d and x.a == team(a) and x.h == team(h)), None)
