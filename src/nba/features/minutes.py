"""Proiezione dei minuti di ogni giocatore per una partita, con le sole informazioni note prima della palla a due.

1. Roster: chi ha già giocato per la squadra in stagione e non è passato ad altra squadra.
2. Minuti di base: media esponenziale dei minuti nelle ultime partite giocate (emivita `hl` partite).
3. Probabilità di giocare:
   - se il giocatore è nell'injury report: dal suo stato (Out, Doubtful, Questionable, Probable, Available),
     con tassi stimati sulle stagioni di sviluppo;
   - se non c'è: dalla partecipazione recente (quante delle ultime partite di squadra ha giocato).
4. Minuti attesi = probabilità × minuti di base, poi riscalati a 240 (i minuti dei mancanti si redistribuiscono
   in proporzione), con un tetto di 42 minuti a testa.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.ingest.injury_pdf import name_key

STATUS_P = {"out": 0.0, "doubtful": 0.08, "questionable": 0.55, "probable": 0.94, "available": 0.99}
DEFAULTS = dict(hl=4.0, recent_n=5, cap=42.0, unlisted_floor=0.0, total=240.0)


class MinutesProjector:
    def __init__(self, pg: pd.DataFrame, games: pd.DataFrame, P: dict | None = None, status_p: dict | None = None):
        """pg: righe giocatore-partita della stagione (con sec > 0); games: partite (game_id, date, home, away)."""
        self.P = {**DEFAULTS, **(P or {})}
        self.status_p = {**STATUS_P, **(status_p or {})}
        g = games[["game_id", "date", "home", "away"]].copy()
        g["date"] = pd.to_datetime(g["date"])
        self.games = g
        tg = pd.concat([g.rename(columns={"home": "team"})[["game_id", "date", "team"]],
                        g.rename(columns={"away": "team"})[["game_id", "date", "team"]]])
        self.team_games = tg.sort_values(["team", "date"])
        x = pg[pg["sec"] > 0].merge(g[["game_id", "date"]], on="game_id")
        x["min"] = x["sec"] / 60
        self.pg = x.sort_values(["player", "date"])
        self.names = pg.drop_duplicates("player").set_index("player")["name"].to_dict() if "name" in pg else {}
        self.key = {p: name_key(n) for p, n in self.names.items()}

    def project(self, game_id: str, team: str, date, injuries: pd.DataFrame | None = None) -> pd.DataFrame:
        """injuries: righe dell'injury report per questa squadra (colonne player_name, status), oppure None."""
        P = self.P
        date = pd.Timestamp(date)
        past = self.pg[self.pg["date"] < date]
        if past.empty:
            return pd.DataFrame(columns=["player", "min", "p", "base"])
        last_team = past.groupby("player")["team"].last()
        roster = last_team[last_team == team].index
        tgames = self.team_games[(self.team_games["team"] == team) & (self.team_games["date"] < date)]
        recent_ids = set(tgames["game_id"].tail(P["recent_n"]))
        n_recent = max(len(recent_ids), 1)
        rows = []
        mine = past[(past["team"] == team) & past["player"].isin(roster)]
        for pid, h in mine.groupby("player"):
            mins = h["min"].to_numpy()
            w = 0.5 ** (np.arange(len(mins))[::-1] / P["hl"])
            base = float((mins * w).sum() / w.sum())
            played_recent = len(recent_ids & set(h["game_id"]))
            rows.append({"player": pid, "base": base, "played_recent": played_recent, "games": len(mins)})
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=["player", "min", "p", "base"])
        # probabilità di giocare
        df["p"] = (df["played_recent"] / n_recent).clip(lower=P["unlisted_floor"])
        df["listed"] = ""
        if injuries is not None and len(injuries):
            st = {name_key(n): s for n, s in zip(injuries["player_name"], injuries["status"])}
            for i, pid in enumerate(df["player"]):
                s = st.get(self.key.get(pid, ""))
                if s:
                    df.loc[df.index[i], "listed"] = s
                    df.loc[df.index[i], "p"] = self.status_p.get(str(s).lower(), df["p"].iat[i])
        # chi non era nelle ultime partite ma non è in elenco: probabilmente fuori rotazione o appena rientrato
        df["min"] = df["p"] * df["base"]
        df["min"] = _rescale(df["min"].to_numpy(), P["total"], P["cap"])
        return df[["player", "min", "p", "base", "listed"]]


def _rescale(m: np.ndarray, total: float, cap: float) -> np.ndarray:
    m = m.astype(float).copy()
    if m.sum() <= 0:
        return m
    for _ in range(10):
        free = m < cap - 1e-9
        s_fixed = m[~free].sum()
        s_free = m[free].sum()
        if s_free <= 0:
            break
        m[free] *= (total - s_fixed) / s_free
        if (m <= cap + 1e-9).all():
            break
        m = np.minimum(m, cap)
    return m


def project_season(season: int, injuries: pd.DataFrame | None = None, P: dict | None = None,
                   status_p: dict | None = None) -> pd.DataFrame:
    """Minuti proiettati per tutte le partite della stagione. injuries: righe dell'injury report pre-partita
    (game_id, team, player_name, status), oppure None se non disponibile."""
    from nba.config import path
    pg = pd.read_parquet(path("processed") / f"player_games_{season}.parquet")
    g = pd.read_parquet(path("processed") / f"games_{season}.parquet").dropna(subset=["date"])
    mp = MinutesProjector(pg, g, P, status_p)
    inj = {k: v for k, v in injuries.groupby(["game_id", "team"])} if injuries is not None and len(injuries) else {}
    out = []
    for r in g.sort_values("date").itertuples():
        for t in (r.home, r.away):
            pr = mp.project(r.game_id, t, r.date, inj.get((r.game_id, t)))
            if len(pr):
                out.append(pr.assign(game_id=r.game_id, team=t))
    return pd.concat(out, ignore_index=True)
