"""Controlli di qualità sui dati elaborati della fase 1. Scrive reports/qc_fase1.md e reports/qc_fase1.json."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nba.config import all_seasons, path, season_label
from nba.ingest.build import events_for
from nba.ingest.games import build_games
from nba.ingest.pbp_download import raw_file
from nba.ingest.stints import build_season

EXPECTED_GAMES = {2019: 1059, 2020: 1080}   # 2019-20 interrotta dal Covid (con le partite nella "bolla"), 2020-21 da 72


def _market(s: int, gg: pd.DataFrame) -> dict:
    """Copertura e precisione della linea di chiusura (il riferimento da battere)."""
    p = path("processed") / f"lines_{s}.parquet"
    if not p.exists():
        return {}
    L = pd.read_parquet(p).merge(gg[["hpts", "apts"]], left_on="game_id", right_index=True)
    m = L["hpts"] - L["apts"]
    ok = L["close_spread_home"].notna()
    pm = L["p_home_mkt"]
    return {"quote_chiusura": float(ok.sum() / len(gg)), "quote_apertura": float(L["open_spread_home"].notna().sum() / len(gg)),
            "bookmaker_mediana": float(L["n_books"].median()),
            "mercato_MAE_scarto": round(float((m + L["close_spread_home"])[ok].abs().mean()), 2),
            "mercato_MAE_totale": round(float(((L["hpts"] + L["apts"]) - L["close_total"]).dropna().abs().mean()), 2),
            "mercato_Brier": round(float(((pm - (m > 0)) ** 2)[pm.notna()].mean()), 4)}


def load(kind: str, seasons) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(path("processed") / f"{kind}_{s}.parquet") for s in seasons], ignore_index=True)


def run_qc() -> dict:
    seasons = all_seasons()
    g = load("games", seasons)
    st = load("stints", seasons)
    pg = load("player_games", seasons)
    iss = load("lineup_issues", seasons)
    res = {"seasons": {}}
    rows = []
    for s in seasons:
        gs, ss, ps, is_ = g[g.season == s], st[st.season == s], pg[pg.season == s], iss[iss.season == s]
        exp_games = EXPECTED_GAMES.get(s, 1230)
        per_team = pd.concat([gs.home, gs.away]).value_counts()
        # minuti di squadra
        m = ps.groupby(["game_id", "team"])["sec"].sum().reset_index()
        m["exp"] = m["game_id"].map(gs.set_index("game_id")["periods"]).map(lambda p: 5 * (2880 + 300 * max(0, p - 4)))
        dmin = (m["sec"] - m["exp"]).abs() / 60
        # punti: stint e statistiche dei giocatori contro il punteggio finale
        gg = gs.set_index("game_id")
        sp = ss.groupby("game_id")[["hpts", "apts"]].sum().reindex(gg.index)
        stint_ok = (sp["hpts"] == gg["hpts"]) & (sp["apts"] == gg["apts"])
        ev_ok = (gg["h_ev"] == gg["hpts"]) & (gg["a_ev"] == gg["apts"])
        dur5 = ss.loc[(ss.hn == 5) & (ss.an == 5), "dur"].sum() / ss["dur"].sum()
        # stesso giocatore in due squadre nella stessa partita
        dup = ps.groupby(["game_id", "player"])["team"].nunique()
        margin = gg["hpts"] - gg["apts"]
        r = {
            "stagione": season_label(s), "fonte_eventi": gs["event_source"].iat[0],
            "partite": len(gs), "attese": exp_games,
            "partite_per_squadra": f"{per_team.min()}–{per_team.max()}",
            "date_mancanti": int(gs["date"].isna().sum()),
            "punteggio_fonti_concordi_2+": float((gg["score_agree"] >= 2).mean()),
            "punteggio_una_sola_fonte": int((gg["score_agree"] == 1).sum()),
            "punteggio_mancante": int(gg["hpts"].isna().sum()),
            "eventi_uguali_al_finale": float(ev_ok.mean()),
            "stint_uguali_al_finale": float(stint_ok.mean()),
            "minuti_squadra_entro_0.5": float((dmin <= 0.5).mean()),
            "tempo_5_contro_5": float(dur5),
            "periodi_con_quintetto_dedotto": int((is_["issue"] == "imputato").sum()),
            "periodi_quintetto_incompleto_o_eccesso": int(is_["issue"].str.startswith(("incompleto", "eccesso")).sum()),
            "sostituzioni_incoerenti": int(is_["issue"].isin(["esce_non_in_campo", "entra_gia_in_campo"]).sum()),
            "giocatore_in_due_squadre": int((dup > 1).sum()),
            "giocatori_senza_nome": int(ps.loc[ps["sec"] > 0, "name"].isna().sum()),
            "pbp_utilizzabile": float(gg["pbp_ok"].mean()),
            "espn_abbinate": float(gg["espn_id"].notna().mean()) if "espn_id" in gg else 0.0,
            "espn_uguale_finale": float(((gg.get("h_espn") == gg["hpts"]) & (gg.get("a_espn") == gg["apts"])).mean())
            if "h_espn" in gg else 0.0,
            **_market(s, gg),
            "punti_medi_squadra": round(float((gg["hpts"] + gg["apts"]).mean() / 2), 1),
            "vittorie_casa": round(float((margin > 0).mean()), 3),
            "dev_std_scarto": round(float(margin.std()), 2),
        }
        res["seasons"][s] = r
        rows.append(r)

    # Controllo incrociato: stessa stagione ricostruita da due fonti indipendenti (v2 e cdn)
    cross = []
    for s in [x for x in seasons if raw_file("nbastats", x).exists() and raw_file("cdnnba", x).exists()]:
        gs = build_games(s)
        ev2, _ = events_for(s, "v2")
        _, _, pg2 = build_season(ev2, gs)
        pc = pg[pg.season == s]
        j = pc.merge(pg2, on=["game_id", "team", "player"], suffixes=("", "_v2"), how="outer")
        d = (j["sec"].fillna(0) - j["sec_v2"].fillna(0)).abs() / 60
        c = {"stagione": season_label(s), "righe": len(j), "minuti_entro_1": float((d <= 1).mean()),
             "diff_minuti_media": float(d.mean())}
        for k in ["pts", "ast", "stl", "blk", "tov", "oreb", "dreb", "fga", "fta"]:
            c[f"{k}_uguali"] = float((j[k].fillna(0) == j[f"{k}_v2"].fillna(0)).mean())
        cross.append(c)
    res["cross"] = cross

    # nomi: stesso nome con id diversi (possibili duplicati da verificare)
    nm = pg.dropna(subset=["name"]).groupby("name")["player"].nunique()
    res["nomi_con_piu_id"] = nm[nm > 1].index.tolist()
    # peggiori partite per qualità del punteggio
    bad = g[(g["score_agree"] < 2)][["game_id", "season", "date", "home", "away", "hpts", "apts", "score_from"]]
    res["partite_una_fonte"] = bad.astype(str).to_dict("records")

    rep = path("reports")
    with open(rep / "qc_fase1.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    df = pd.DataFrame(rows)
    _write_md(df, pd.DataFrame(cross), res, rep / "qc_fase1.md")
    print(df.to_string())
    print(pd.DataFrame(cross).to_string())
    return res


def _pct(x):
    return f"{100 * x:.2f}%"


def _write_md(df: pd.DataFrame, cross: pd.DataFrame, res: dict, out):
    L = ["# Controlli di qualità — fase 1", ""]
    L.append("| Stagione | Fonte | Partite (attese) | Per squadra | Punteggio: ≥2 fonti concordi | Eventi = finale | "
             "Minuti squadra ok | Tempo 5 vs 5 | Quintetti dedotti | Quintetti incompleti | Sost. incoerenti | Punti/squadra | Casa vince | Dev. std scarto |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in df.iterrows():
        L.append(f"| {r['stagione']} | {r['fonte_eventi']} | {r['partite']} ({r['attese']}) | {r['partite_per_squadra']} | "
                 f"{_pct(r['punteggio_fonti_concordi_2+'])} | {_pct(r['eventi_uguali_al_finale'])} | "
                 f"{_pct(r['minuti_squadra_entro_0.5'])} | {_pct(r['tempo_5_contro_5'])} | {r['periodi_con_quintetto_dedotto']} | "
                 f"{r['periodi_quintetto_incompleto_o_eccesso']} | {r['sostituzioni_incoerenti']} | {r['punti_medi_squadra']} | "
                 f"{r['vittorie_casa']} | {r['dev_std_scarto']} |")
    if "quote_chiusura" in df:
        L += ["", "## ESPN: punteggi e quote", "",
              "| Stagione | Partite abbinate | Punteggio ESPN = finale | Play-by-play utilizzabile | Linea di chiusura | Linea d'apertura | Bookmaker (mediana) | Mercato: errore medio scarto | Mercato: errore medio totale | Mercato: Brier |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for _, r in df.iterrows():
            L.append(f"| {r['stagione']} | {_pct(r['espn_abbinate'])} | {_pct(r['espn_uguale_finale'])} | {_pct(r['pbp_utilizzabile'])} | "
                     f"{_pct(r['quote_chiusura'])} | {_pct(r['quote_apertura'])} | {r['bookmaker_mediana']:.0f} | "
                     f"{r['mercato_MAE_scarto']} | {r['mercato_MAE_totale']} | {r['mercato_Brier']} |")
    L += ["", "## Stessa stagione da due fonti indipendenti (NBA Stats v2 contro cdn.nba.com)", ""]
    if len(cross):
        cols = ["stagione", "righe", "minuti_entro_1", "pts_uguali", "ast_uguali", "oreb_uguali", "dreb_uguali", "tov_uguali", "stl_uguali", "blk_uguali"]
        L.append("| " + " | ".join(cols) + " |")
        L.append("|" + "---|" * len(cols))
        for _, r in cross.iterrows():
            L.append("| " + " | ".join(str(r[c]) if c in ("stagione", "righe") else _pct(r[c]) for c in cols) + " |")
    L += ["", f"Nomi con più id (da verificare: omonimi o duplicati): {', '.join(res['nomi_con_piu_id']) or 'nessuno'}", "",
          f"Partite con il punteggio confermato da una sola fonte: {len(res['partite_una_fonte'])}"]
    for b in res["partite_una_fonte"][:30]:
        L.append(f"- {b['game_id']} {b['date']} {b['away']}@{b['home']} {b['apts']}-{b['hpts']} (fonte: {b['score_from']})")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
