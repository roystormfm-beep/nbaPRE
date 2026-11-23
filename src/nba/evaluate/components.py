"""Tabella dei componenti dell'ensemble, una riga per partita, stagioni 2014-15 → 2025-26.

Ogni colonna è un pronostico fatto solo con informazioni precedenti alla partita:
  m_players / t_players  modello giocatori + minuti (injury report dal 2018-19) + contesto (fase 4)
  m_players_open         modello giocatori senza injury report (per il confronto con la linea d'apertura)
  m_team / t_team        ritmo ed efficienza di squadra sui risultati recenti (fase 4)
  m_base / t_base        baseline della pagina ritarato (con injury report dal 2018-19, senza prima)
  m_elo                  Elo con margine di vittoria
  m_gbm / t_gbm          LightGBM su feature di squadra e di contesto (dal 2016-17)
Il 2025-26 (test) viene costruito con le stesse regole, ma nessuna scelta qui dipende dai suoi risultati.
"""
from __future__ import annotations

import pandas as pd

from nba.config import cfg, path
from nba.models import context_model as CM
from nba.models import elo as ELO
from nba.models.team_ratings import game_table, predict_games

SEASONS = list(range(2014, 2026))
COLS = ["game_id", "season", "date", "home", "away", "hpts", "apts", "margin_pred", "total_pred", "pm_mu", "pm_pace",
        "eff_sum", "eff_diff"]


def _player_base() -> pd.DataFrame:
    proc = path("processed")
    parts = [pd.read_parquet(proc / "player_model_noreport_2014_2017.parquet")[COLS].assign(has_report=False),
             pd.read_parquet(proc / "player_model_report_predictions.parquet")[COLS].assign(has_report=True)]
    t = proc / "player_model_report_test_2025.parquet"
    if t.exists():
        parts.append(pd.read_parquet(t)[COLS].assign(has_report=True))
    base = pd.concat(parts, ignore_index=True)
    # il 2018-19 ha l'injury report solo da metà dicembre
    has = set()
    for s in range(2018, 2026):
        f = path("external") / "injury" / f"needed_{s}.csv"
        if f.exists():
            has |= set(pd.read_csv(f, dtype={"game_id": str})["game_id"].str.zfill(10))
    base["has_report"] = base["has_report"] & base["game_id"].isin(has)
    ctx = pd.read_parquet(proc / "context.parquet").drop(columns=["season", "date", "home", "away"])
    return base.merge(ctx, on="game_id", how="inner")


def team_ratings() -> pd.DataFrame:
    f = path("processed") / "team_ratings_predictions.parquet"
    tr = pd.read_parquet(f)
    missing = [s for s in SEASONS if s not in set(tr["season"])]
    if missing:
        g = game_table(SEASONS)
        tr = pd.concat([tr, predict_games(g, missing, cfg()["models"]["team_ratings"])], ignore_index=True)
        tr.to_parquet(f, index=False)
    return tr


def baseline() -> pd.DataFrame:
    proc = path("processed")
    b = pd.read_parquet(proc / "baseline_retuned_predictions.parquet")
    pre = b[(b["variant"] == "senza") & (b["season"] < 2018)]
    rep = pd.read_parquet(proc / "baseline_report_predictions.parquet")
    parts = [pre, rep[rep["variant"] == "injury_report"]]
    t = proc / "baseline_report_test_2025.parquet"
    if t.exists():
        tt = pd.read_parquet(t)
        parts.append(tt[tt["variant"] == "injury_report"])
    x = pd.concat(parts, ignore_index=True)
    return x[["game_id", "margin_pred", "total_pred"]].rename(columns={"margin_pred": "m_base", "total_pred": "t_base"})


def players_open() -> pd.DataFrame:
    proc = path("processed")
    a = pd.read_parquet(proc / "player_model_predictions.parquet")
    a = a[a["minuti"] == "proiettati_senza_report"]
    parts = [a]
    t = proc / "player_model_noreport_test_2025.parquet"
    if t.exists():
        parts.append(pd.read_parquet(t))
    x = pd.concat(parts, ignore_index=True)
    return x[["game_id", "margin_pred"]].rename(columns={"margin_pred": "m_players_open"})


def build() -> pd.DataFrame:
    M = cfg()["models"]
    df = _player_base()
    tr = team_ratings()
    df = df.merge(tr.drop(columns=["season"]), on="game_id", how="left")
    seasons = sorted(df["season"].unique())
    # scarto: modello giocatori + contesto essenziale (seconda fase ridge sulle stagioni precedenti)
    dm = df.assign(y=(df["hpts"] - df["apts"]).astype(float), base=df["margin_pred"])
    pm = CM.fit_predict(dm, "margin", [s for s in seasons if s > 2014], groups=set(M["context_margin_groups"]))
    # totale: ritmo di squadra × efficienza dei giocatori disponibili + correzione di livello
    dt = df.assign(y=(df["hpts"] + df["apts"]).astype(float),
                   base=df["pace_pred"] * (2 * df["lg_eff"] + (df["eff_sum"] - 2 * df["pm_mu"])) / 100)
    pt = CM.fit_predict(dt, "total", [s for s in seasons if s > 2014], groups=set(M["context_total_groups"]))
    out = df.merge(pm[["game_id", "pred"]].rename(columns={"pred": "m_players"}), on="game_id")
    out = out.merge(pt[["game_id", "pred"]].rename(columns={"pred": "t_players"}), on="game_id")
    out = out.rename(columns={"margin_team": "m_team", "total_team": "t_team", "margin_pred": "m_players_raw",
                              "total_pred": "t_players_raw"})
    out = out.merge(baseline(), on="game_id", how="left").merge(players_open(), on="game_id", how="left")
    e = ELO.run(ELO.games(SEASONS), M["elo"])
    out = out.merge(e[["game_id", "elo_diff", "margin_elo", "p_elo"]].rename(columns={"margin_elo": "m_elo"}),
                    on="game_id", how="left")
    # gradient boosting sulle feature di squadra e di contesto (si allena dalle stagioni precedenti)
    from nba.models import gbm
    later = [s for s in seasons if s >= 2017]
    for target, col in (("margin", "m_gbm"), ("total", "t_gbm")):
        p = gbm.fit_predict(out, target, later, M.get("gbm"))
        out = out.merge(p[["game_id", "pred"]].rename(columns={"pred": col}), on="game_id", how="left")
    out.to_parquet(path("processed") / "components.parquet", index=False)
    return out


if __name__ == "__main__":
    x = build()
    print(x.groupby("season").agg(partite=("game_id", "size"), report=("has_report", "sum"),
                                  base=("m_base", lambda s: s.notna().sum()), open=("m_players_open", lambda s: s.notna().sum())))
