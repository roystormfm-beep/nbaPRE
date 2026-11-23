"""Rating dei giocatori per possesso (RAPM) dagli stint del play-by-play.

Per ogni stint (tratto di gioco con gli stessi 10 giocatori) ci sono due osservazioni:
  punti per 100 possessi della squadra di casa  = mu + h/2 + somma O(casa) - somma D(trasferta) [+ squadra]
  punti per 100 possessi della squadra ospite   = mu - h/2 + somma O(trasferta) - somma D(casa) [+ squadra]
pesate per i possessi dello stint e per quanto è recente. Regressione ridge con un prior per ogni giocatore
(dal BPM offensivo/difensivo della stagione precedente), così chi ha giocato poco resta vicino al prior.

Correzione per la fortuna al tiro (opzionale): i tiri da tre segnati vengono sostituiti dai tentativi per la
percentuale da tre della squadra nel periodo di stima, i liberi segnati dai tentati per la sua percentuale ai liberi.
Così uno stint con 5/6 da tre non viene premiato come se fosse merito dei difensori avversari.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp

from nba.config import path

# Valori scelti sulle stagioni di sviluppo 2017-18, 2019-20, 2021-22, 2023-24 (vedi REPORT, fase 3).
# luck=False: la correzione per la fortuna al tiro in questa forma peggiorava i pronostici.
DEFAULTS = dict(lam=3000.0, half_life=180.0, window_days=800, luck=False, lam_team=6000.0, team_effect=True,
                rookie_o=-1.5, rookie_d=-0.5, prior_shrink_min=500.0, prior_scale=0.6, lam_h=1e4, box_w=1000.0)


def load_stints(seasons: list[int]) -> pd.DataFrame:
    parts = []
    for s in seasons:
        p = path("processed") / f"stints_{s}.parquet"
        if not p.exists():
            continue
        st = pd.read_parquet(p)
        g = pd.read_parquet(path("processed") / f"games_{s}.parquet", columns=["game_id", "date", "home", "away", "pbp_ok"])
        st = st.merge(g, on="game_id")
        st = st[st["pbp_ok"] & (st["hn"] == 5) & (st["an"] == 5)]
        parts.append(st)
    st = pd.concat(parts, ignore_index=True)
    st["date"] = pd.to_datetime(st["date"])
    for side in ("h", "a"):
        st[f"{side}poss"] = st[f"{side}fga"] - st[f"{side}oreb"] + st[f"{side}tov"] + 0.44 * st[f"{side}fta"]
    st["poss"] = ((st["hposs"] + st["aposs"]) / 2).clip(lower=0)
    return st[st["poss"] > 0].reset_index(drop=True)


def prev_box_prior(season: int) -> pd.DataFrame:
    """Prior per giocatore dal BPM offensivo/difensivo della stagione precedente (Basketball-Reference)."""
    p = path("external") / "bref" / f"advanced_{season - 1}.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["name_key", "obpm", "dbpm", "mp"])
    b = pd.read_parquet(p)
    from nba.config import fix_text
    b["Player"] = b["Player"].map(fix_text)
    multi = b["Team"].astype(str).str.contains("TM") | (b["Team"].astype(str) == "TOT")
    traded = set(b.loc[multi, "Player"])
    b = b[multi | ~b["Player"].isin(traded)].copy()
    for c in ("OBPM", "DBPM", "MP"):
        b[c] = pd.to_numeric(b[c], errors="coerce")
    b = b.dropna(subset=["OBPM", "DBPM", "MP"])
    from nba.models.baseline import norm_name
    b["name_key"] = b["Player"].map(norm_name)
    return b.drop_duplicates("name_key")[["name_key", "OBPM", "DBPM", "MP"]].rename(
        columns={"OBPM": "obpm", "DBPM": "dbpm", "MP": "mp"})


@dataclass
class RapmFit:
    players: np.ndarray          # id giocatore per indice
    O: np.ndarray
    D: np.ndarray
    O0: np.ndarray               # prior usato
    D0: np.ndarray
    poss: np.ndarray             # possessi (pesati) nel periodo di stima
    mu: float
    h: float
    team_o: dict
    team_d: dict
    pace: float                  # possessi medi per 48 minuti nel periodo

    def table(self) -> pd.DataFrame:
        return pd.DataFrame({"player": self.players, "O": self.O, "D": self.D, "net": self.O + self.D,
                             "O0": self.O0, "D0": self.D0, "poss": self.poss})


def fit(st: pd.DataFrame, cutoff: pd.Timestamp, priors: dict[int, tuple[float, float]], P: dict | None = None,
        season: int | None = None) -> RapmFit:
    """Stima con gli stint giocati prima di cutoff (esclusa la data cutoff)."""
    P = {**DEFAULTS, **(P or {})}
    w_start = cutoff - pd.Timedelta(days=P["window_days"])
    d = st[(st["date"] < cutoff) & (st["date"] >= w_start)]
    age = (cutoff - d["date"]).dt.days.to_numpy(float)
    decay = 0.5 ** (age / P["half_life"])
    poss = d["poss"].to_numpy(float)
    hp, ap = d["hpts"].to_numpy(float), d["apts"].to_numpy(float)
    if P["luck"] and len(d):
        # percentuali di squadra nel periodo di stima (ogni squadra-stagione)
        key_h = d["home"] + "_" + d["season"].astype(str)
        key_a = d["away"] + "_" + d["season"].astype(str)
        tot = pd.DataFrame({
            "k": pd.concat([key_h, key_a]).to_numpy(),
            "fg3a": np.r_[d["hfg3a"], d["afg3a"]], "fg3m": np.r_[d["hfg3m"], d["afg3m"]],
            "fta": np.r_[d["hfta"], d["afta"]], "ftm": np.r_[d["hftm"], d["aftm"]]}).groupby("k").sum()
        lg3 = tot["fg3m"].sum() / max(tot["fg3a"].sum(), 1)
        lgft = tot["ftm"].sum() / max(tot["fta"].sum(), 1)
        p3 = ((tot["fg3m"] + 200 * lg3) / (tot["fg3a"] + 200))       # percentuale di squadra, prudente
        pft = ((tot["ftm"] + 100 * lgft) / (tot["fta"] + 100))
        hp = hp - 3 * d["hfg3m"].to_numpy() + 3 * d["hfg3a"].to_numpy() * key_h.map(p3).to_numpy() \
            - d["hftm"].to_numpy() + d["hfta"].to_numpy() * key_h.map(pft).to_numpy()
        ap = ap - 3 * d["afg3m"].to_numpy() + 3 * d["afg3a"].to_numpy() * key_a.map(p3).to_numpy() \
            - d["aftm"].to_numpy() + d["afta"].to_numpy() * key_a.map(pft).to_numpy()
    hcols = d[["h1", "h2", "h3", "h4", "h5"]].to_numpy()
    acols = d[["a1", "a2", "a3", "a4", "a5"]].to_numpy()
    ids = np.unique(np.r_[hcols.ravel(), acols.ravel(), np.array(list(priors.keys()), dtype=np.int64)])
    pos = {int(p): i for i, p in enumerate(ids)}
    NP = len(ids)
    teams = sorted(set(d["home"]) | set(d["away"])) if P["team_effect"] else []
    tpos = {t: i for i, t in enumerate(teams)}
    NTm = len(teams)
    # colonne: O[0:NP], D[NP:2NP], h, team_o[...], team_d[...]
    n_cols = 2 * NP + 1 + 2 * NTm
    n = len(d)
    hi = np.vectorize(pos.get)(hcols) if n else np.zeros((0, 5), int)
    ai = np.vectorize(pos.get)(acols) if n else np.zeros((0, 5), int)
    rows = np.repeat(np.arange(2 * n), 11 + (2 if NTm else 0))
    # osservazione 1 (casa in attacco): O casa +1, D trasferta -1, h +0.5
    c1 = [hi, NP + ai, np.full((n, 1), 2 * NP)]
    c2 = [ai, NP + hi, np.full((n, 1), 2 * NP)]
    v1 = [np.ones((n, 5)), -np.ones((n, 5)), np.full((n, 1), 0.5)]
    v2 = [np.ones((n, 5)), -np.ones((n, 5)), np.full((n, 1), -0.5)]
    if NTm:
        th = np.array([tpos[t] for t in d["home"]]).reshape(-1, 1)
        ta = np.array([tpos[t] for t in d["away"]]).reshape(-1, 1)
        c1 += [2 * NP + 1 + th, 2 * NP + 1 + NTm + ta]
        c2 += [2 * NP + 1 + ta, 2 * NP + 1 + NTm + th]
        v1 += [np.ones((n, 1)), -np.ones((n, 1))]
        v2 += [np.ones((n, 1)), -np.ones((n, 1))]
    cols = np.vstack([np.hstack(c1), np.hstack(c2)]).ravel()
    vals = np.vstack([np.hstack(v1), np.hstack(v2)]).ravel().astype(float)
    X = sp.csr_matrix((vals, (rows, cols)), shape=(2 * n, n_cols))
    y = np.r_[100 * hp / np.maximum(poss, 1e-9), 100 * ap / np.maximum(poss, 1e-9)]
    w = np.r_[poss * decay, poss * decay]
    mu = float(np.average(y, weights=w)) if n else 112.0
    # prior
    O0, D0 = np.full(NP, P["rookie_o"]), np.full(NP, P["rookie_d"])
    for p_, (o, dd) in priors.items():
        i = pos.get(int(p_))
        if i is not None:
            O0[i], D0[i] = o, dd
    beta0 = np.r_[O0, D0, 0.0, np.zeros(2 * NTm)]
    lam = np.r_[np.full(2 * NP, P["lam"]), P["lam_h"], np.full(2 * NTm, P["lam_team"])]
    if n:
        r = y - mu - X @ beta0
        XtW = X.T.multiply(w)
        A = (XtW @ X).toarray()
        b = XtW @ r
    else:
        A, b = np.zeros((n_cols, n_cols)), np.zeros(n_cols)
    A[np.diag_indices_from(A)] += lam
    # vantaggio campo: prior 2.5 punti per 100 possessi verso cui tirare (in unità del parametro h)
    b[2 * NP] += P["lam_h"] * 2.5
    beta = beta0 + np.linalg.solve(A, b)
    team_o = {t: beta[2 * NP + 1 + i] for t, i in tpos.items()}
    team_d = {t: beta[2 * NP + 1 + NTm + i] for t, i in tpos.items()}
    # possessi giocati da ciascun giocatore nel periodo (pesati), utili per diagnosi
    pw = np.zeros(NP)
    if n:
        np.add.at(pw, hi.ravel(), np.repeat(poss * decay, 5))
        np.add.at(pw, ai.ravel(), np.repeat(poss * decay, 5))
    dur = d["dur"].to_numpy(float)
    pace = float(48 * 60 * poss.sum() / max(dur.sum(), 1)) if n else 100.0
    return RapmFit(players=ids, O=beta[:NP], D=beta[NP:2 * NP], O0=O0, D0=D0, poss=pw, mu=mu, h=float(beta[2 * NP]),
                   team_o=team_o, team_d=team_d, pace=pace)
