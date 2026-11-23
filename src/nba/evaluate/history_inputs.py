"""Ricostruisce, per un giorno qualsiasi del passato, gli stessi ingressi che la pagina avrebbe avuto quel mattino.

Regola: per una partita del giorno d si usano solo partite giocate prima di d (risultati e statistiche) e
informazioni note prima della stagione (calendario, BPM della stagione precedente).

Differenze dichiarate rispetto alla pagina dal vivo:
- BPM della stagione in corso: la pagina usa il BPM di Basketball-Reference, che non esiste "alla data" per il
  passato. Qui il campo resta vuoto e il modello usa la propria stima dal box score (regressione BOX, già nel modello).
- Assenze: due versioni. "senza" = nessuna correzione per assenze (solo rating e riposo);
  "chi_ha_giocato" = assente chiunque del roster non sia entrato in campo in quella partita. La seconda sa con
  certezza chi gioca, cosa che prima della palla a due non si sa: è un limite superiore, ottimistico.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nba.config import path

PERGAME_HEADER = "Player,Team,G,MP,FGA,FTA,3P,TRB,AST,STL,BLK,TOV,PTS"
ADV_HEADER = "Player,Team,G,MP,USG,BPM"


def _fmt(x) -> str:
    x = float(x)
    return str(int(x)) if x.is_integer() else f"{x:.1f}"


class SeasonInputs:
    def __init__(self, season: int):
        self.season = season
        proc = path("processed")
        g = pd.read_parquet(proc / f"games_{season}.parquet")
        self.games = g.dropna(subset=["date", "hpts"]).sort_values(["date", "game_id"]).reset_index(drop=True)
        self.schedule = [f"{r.date},{r.away},{r.home}" for r in self.games.itertuples()]
        pg = pd.read_parquet(proc / f"player_games_{season}.parquet")
        pg = pg.merge(self.games[["game_id", "date"]], on="game_id", how="inner")
        pg["name"] = pg["name"].fillna(pg["player"].astype(str)).str.replace(",", "", regex=False)
        pg["trb"] = pg["oreb"] + pg["dreb"]
        self.pg = pg[pg["sec"] > 0].copy()
        self.prev = self._prev_lines(season - 1)

    @staticmethod
    def _prev_lines(s: int) -> list[str]:
        p = path("external") / "bref" / f"advanced_{s}.parquet"
        if not p.exists():
            return ["Player,Team,G,MP,BPM"]
        b = pd.read_parquet(p)
        b = b[b["Player"].notna() & (b["Player"] != "League Average")]
        multi = b["Team"].astype(str).str.contains("TM") | (b["Team"].astype(str) == "TOT")
        traded = set(b.loc[multi, "Player"])
        b = b[multi | ~b["Player"].isin(traded)]          # per chi ha cambiato squadra tengo solo la riga totale
        for c in ("G", "MP", "BPM"):
            b[c] = pd.to_numeric(b[c], errors="coerce")
        b = b.dropna(subset=["MP", "BPM"])
        b = b[b["MP"] >= 150].sort_values("MP", ascending=False)
        return ["Player,Team,G,MP,BPM"] + [f"{r.Player.replace(',', '')},{r.Team},{_fmt(r.G)},{_fmt(r.MP)},{r.BPM}"
                                           for r in b.itertuples()]

    def days(self) -> list[str]:
        return sorted(self.games["date"].unique())

    def raw_for_day(self, d: str) -> tuple[dict, pd.DataFrame]:
        """Ingressi del mattino del giorno d (stringa YYYY-MM-DD) e partite da pronosticare quel giorno."""
        past = self.games[self.games["date"] < d]
        today = self.games[self.games["date"] == d]
        results = [f"{r.date}|{r.away}|{int(r.apts)}|{r.home}|{int(r.hpts)}|" for r in past.itertuples()]
        sub = self.pg[self.pg["date"] < d]
        pergame, adv = [PERGAME_HEADER], [ADV_HEADER]
        roster = {}
        if len(sub):
            agg = sub.groupby(["team", "player"]).agg(name=("name", "last"), G=("game_id", "nunique"), sec=("sec", "sum"),
                                                     fga=("fga", "sum"), fta=("fta", "sum"), fg3=("fg3m", "sum"),
                                                     trb=("trb", "sum"), ast=("ast", "sum"), stl=("stl", "sum"),
                                                     blk=("blk", "sum"), tov=("tov", "sum"), pts=("pts", "sum")).reset_index()
            agg["MP"] = agg["sec"] / 60
            agg["mpg"] = (agg["MP"] / agg["G"]).round(1)
            for r in agg.itertuples():
                G = r.G
                if r.mpg >= 15.0:
                    pergame.append(f"{r.name},{r.team},{G},{r.mpg:.1f},{r.fga / G:.1f},{r.fta / G:.1f},{r.fg3 / G:.1f},"
                                   f"{r.trb / G:.1f},{r.ast / G:.1f},{r.stl / G:.1f},{r.blk / G:.1f},{r.tov / G:.1f},{r.pts / G:.1f}")
                if round(r.MP) >= 100:
                    adv.append(f"{r.name},{r.team},{G},{int(round(r.MP))},,")
                if r.mpg >= 15.0 or round(r.MP) >= 100:
                    roster.setdefault(r.team, []).append((r.player, r.name))
        # assenze "chi ha giocato": del roster di oggi, chi non è entrato in campo
        injuries = []
        played = set(zip(self.pg.loc[self.pg["game_id"].isin(today["game_id"]), "team"],
                         self.pg.loc[self.pg["game_id"].isin(today["game_id"]), "player"]))
        for t in set(today["home"]) | set(today["away"]):
            for pid, name in roster.get(t, []):
                if (t, pid) not in played:
                    injuries.append(f"{t}|{name}|Out||non ha giocato")
        raw = {"schedule": self.schedule, "results": results, "pergame": pergame, "advanced": adv,
               "prev": self.prev, "injuries": injuries, "extra": []}
        return raw, today
