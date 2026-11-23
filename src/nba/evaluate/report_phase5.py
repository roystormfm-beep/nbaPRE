"""Fase 5: valutazione completa (sviluppo e test), con le scelte congelate in config.yaml.

  nba report --fase 5 --solo-sviluppo   numeri sulle stagioni di sviluppo (2018-19 → 2024-25)
  nba report --fase 5                   anche la stagione di test 2025-26 (una volta sola, a configurazione congelata)
Uscite: reports/fase5.json, reports/fase5.md, reports/fase5.html, data/processed/phase5_predictions.parquet.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nba.config import cfg, path, season_label
from nba.evaluate import errors as ERR
from nba.evaluate import market_aware as MA
from nba.evaluate.metrics import _boot_ci, _ece, _logloss, attach_market, evaluate
from nba.evaluate.phase5 import final
from nba.models import distribution as D

DEV = list(range(2018, 2025))
TEST = [2025]

MODELS_M = [("m_page_senza", "Baseline della pagina (v2), senza assenze"),
            ("m_base", "Baseline ritarato, con injury report"),
            ("m_elo", "Elo con margine di vittoria"),
            ("m_team", "Rating di squadra (ritmo ed efficienza)"),
            ("m_gbm", "LightGBM su squadra e contesto"),
            ("m_players_open", "Giocatori + minuti, senza injury report"),
            ("m_players_raw", "Giocatori + minuti, con injury report"),
            ("m_players", "… + contesto (riposo, fine stagione)"),
            ("m_final", "Ensemble finale")]
MODELS_T = [("t_base", "Baseline ritarato"), ("t_team", "Rating di squadra"), ("t_gbm", "LightGBM"),
            ("t_players_raw", "Solo giocatori (fase 3)"), ("t_final", "Finale: ritmo di squadra × giocatori disponibili")]
LABEL_W = {"m_players": "Giocatori + minuti + contesto", "m_team": "Rating di squadra", "m_base": "Baseline ritarato",
           "m_elo": "Elo", "m_gbm": "LightGBM", "costante": "costante"}


def assemble(max_season: int) -> pd.DataFrame:
    x = final(max_season)
    page = pd.read_parquet(path("processed") / "baseline_predictions.parquet")
    page = page[page["variant"] == "senza"][["game_id", "margin_pred"]].rename(columns={"margin_pred": "m_page_senza"})
    x = x.merge(page, on="game_id", how="left")
    x = attach_market(x)
    x["mese"] = pd.to_datetime(x["date"]).dt.to_period("M").astype(str)
    assemble.weights, assemble.fits = final.weights, final.fits
    return x


def sample(x: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    return x[x["season"].isin(seasons) & x["has_report"]].dropna(
        subset=["close_spread_home", "close_total", "p_home_mkt", "m_final"]).copy()


def compare(x: pd.DataFrame, models, target: str, rng) -> list[dict]:
    y = (x["hpts"] - x["apts"] if target == "margin" else x["hpts"] + x["apts"]).to_numpy(float)
    mkt = (-x["close_spread_home"] if target == "margin" else x["close_total"]).to_numpy(float)
    ref = (x["m_final"] if target == "margin" else x["t_final"]).to_numpy(float)
    rows = []
    for col, label in models:
        p = x[col].to_numpy(float)
        ok = np.isfinite(p)
        ae = np.abs(y - p)
        r = {"col": col, "modello": label, "partite": int(ok.sum()), "MAE": float(ae[ok].mean()),
             "RMSE": float(np.sqrt(((y - p)[ok] ** 2).mean()))}
        for k, other in (("vs_mercato", mkt), ("vs_finale", ref)):
            if k == "vs_finale" and col in ("m_final", "t_final"):
                continue
            m, lo, hi = _boot_ci((ae - np.abs(y - other))[ok], rng)
            r[k], r[k + "_lo"], r[k + "_hi"] = m, lo, hi
        rows.append(r)
    mae_m = float(np.abs(y - mkt).mean())
    rows.append({"col": "mercato", "modello": "Mercato (linea di chiusura)", "partite": len(y), "MAE": mae_m,
                 "RMSE": float(np.sqrt(((y - mkt) ** 2).mean()))})
    return rows


def calibration(x: pd.DataFrame, bins: int = 10) -> list[dict]:
    win = (x["hpts"] > x["apts"]).astype(float)
    out = []
    for name, col in (("modello", "p_home"), ("mercato", "p_home_mkt")):
        p = x[col].to_numpy(float)
        idx = np.clip((p * bins).astype(int), 0, bins - 1)
        for b in range(bins):
            m = idx == b
            if m.sum() >= 15:
                out.append({"serie": name, "fascia": b, "p_media": float(p[m].mean()), "vinte": float(win[m].mean()),
                            "partite": int(m.sum())})
    return out


def cover(x: pd.DataFrame) -> dict:
    """Probabilità di coprire lo spread di chiusura, dalla distribuzione dello scarto."""
    y = (x["hpts"] - x["apts"]).to_numpy(float)
    c = y + x["close_spread_home"].to_numpy(float)
    ok = c != 0
    pc = np.full(len(x), np.nan)
    u = np.full(len(x), np.nan)
    for s, F in assemble.fits.items():
        m = (x["season"] == s).to_numpy()
        if m.any():
            pc[m] = D.prob_above(F, x.loc[m, "m_final"], x.loc[m, "t_final"], -x.loc[m, "close_spread_home"])
            u[m] = 1 - D.prob_above(F, x.loc[m, "m_final"], x.loc[m, "t_final"], y[m])
    out = (c > 0).astype(float)
    return {"partite": int(ok.sum()), "LogLoss": float(_logloss(pc[ok], out[ok]).mean()), "LogLoss_moneta": float(np.log(2)),
            "Brier": float(((pc[ok] - out[ok]) ** 2).mean()), "ECE": float(_ece(pc[ok], out[ok])),
            "copertura50": float(((u > 0.25) & (u < 0.75)).mean()), "copertura80": float(((u > 0.1) & (u < 0.9)).mean()),
            "copertura95": float(((u > 0.025) & (u < 0.975)).mean())}


def distribution_choice(x_all: pd.DataFrame) -> list[dict]:
    """Confronto delle forme della distribuzione sulle sole stagioni di sviluppo (è qui che si è scelta)."""
    c = x_all[x_all["season"] <= max(DEV)].reset_index(drop=True)
    comp = pd.read_parquet(path("processed") / "components.parquet")
    early = comp[comp["season"] < 2018][["game_id", "season", "hpts", "apts", "m_players", "t_players"]].rename(
        columns={"m_players": "m_final", "t_players": "t_final"})
    base = pd.concat([early, c[["game_id", "season", "hpts", "apts", "m_final", "t_final"]]], ignore_index=True)
    c = base.merge(c[["game_id", "close_spread_home", "p_home_mkt"]], on="game_id", how="left")
    keep = set(sample(x_all, DEV)["game_id"])
    ev = c["game_id"].isin(keep).to_numpy()
    y = (c["hpts"] - c["apts"]).to_numpy(float)
    win = (y > 0).astype(float)
    rows = []
    D_ = cfg()["models"]["distribution"]
    for kind in D.KINDS:
        p, s, fits = D.walk_forward(c, "m_final", "t_final", list(range(2016, max(DEV) + 1)), kind, D_["hl_seasons"], D_["window"])
        u = np.full(len(c), np.nan)
        for se, F in fits.items():
            m = (c["season"] == se).to_numpy()
            u[m] = 1 - D.prob_above(F, c.loc[m, "m_final"], c.loc[m, "t_final"], y[m])
        pv = p.to_numpy()
        r = {"forma": kind, "LogLoss": float(_logloss(pv[ev], win[ev]).mean()), "Brier": float(((pv[ev] - win[ev]) ** 2).mean()),
             "ECE": float(_ece(pv[ev], win[ev])), "copertura80": float(((u[ev] > 0.1) & (u[ev] < 0.9)).mean()),
             "copertura95": float(((u[ev] > 0.025) & (u[ev] < 0.975)).mean())}
        F = fits[max(DEV)]
        r["sd_tipica"] = float(np.exp(F["c"][0]))
        r["effetto_totale"] = float(F["c"][1])
        r["effetto_differenza"] = float(F["c"][2])
        if kind == "t":
            r["gradi_liberta"] = F["df"]
        rows.append(r)
    return rows


def block(x: pd.DataFrame, rng, seed: int) -> dict:
    e = evaluate(x.assign(margin_pred=x["m_final"], total_pred=x["t_final"]), seed)
    for k in [k for k in e if k.startswith("CLV")]:
        e.pop(k)        # il CLV corretto (pronostico fatto all'apertura) è nella sezione sul mercato
    per_season = []
    for s, g in x.groupby("season"):
        r = evaluate(g.assign(margin_pred=g["m_final"], total_pred=g["t_final"]), seed)
        per_season.append({"stagione": season_label(int(s)), "partite": r["partite"],
                           "MAE": r["MAE_scarto_modello"], "MAE_mercato": r["MAE_scarto_mercato"],
                           "dMAE": r["dMAE"], "dMAE_lo": r["dMAE_lo"], "dMAE_hi": r["dMAE_hi"],
                           "MAE_totale": r["MAE_totale_modello"], "MAE_totale_mercato": r["MAE_totale_mercato"],
                           "Brier": r["Brier_modello"], "Brier_mercato": r["Brier_mercato"]})
    y = x["hpts"] - x["apts"]
    t = x["hpts"] + x["apts"]
    month = x.assign(e_mod=(y - x["m_final"]).abs(), e_mkt=(y + x["close_spread_home"]).abs(),
                     et_mod=(t - x["t_final"]).abs(), et_mkt=(t - x["close_total"]).abs()).groupby("mese").agg(
        partite=("game_id", "size"), MAE=("e_mod", "mean"), MAE_mercato=("e_mkt", "mean"),
        MAE_totale=("et_mod", "mean"), MAE_totale_mercato=("et_mkt", "mean")).reset_index()
    pts = {"MAE_punti_squadra": float(pd.concat([(x["hpts"] - x["hp"]).abs(), (x["apts"] - x["ap"]).abs()]).mean()),
           "MAE_punti_squadra_mercato": float(pd.concat([(x["hpts"] - (x["close_total"] - x["close_spread_home"]) / 2).abs(),
                                                         (x["apts"] - (x["close_total"] + x["close_spread_home"]) / 2).abs()]).mean())}
    big = (x["m_final"] + x["close_spread_home"]).abs() >= 3
    yb = y[big]
    dis = {"partite": int(big.sum()), "MAE_modello": float((yb - x.loc[big, "m_final"]).abs().mean()),
           "MAE_mercato": float((yb + x.loc[big, "close_spread_home"]).abs().mean())}
    return {"metriche": e, "per_stagione": per_season, "per_mese": month.to_dict("records"),
            "scarto": compare(x, MODELS_M, "margin", rng), "totale": compare(x, MODELS_T, "total", rng),
            "calibrazione": calibration(x), "copertura": cover(x), "punti": pts, "disaccordo_3": dis}


def build(with_test: bool) -> dict:
    seed = cfg()["seed"]
    max_season = max(TEST) if with_test else max(DEV)
    x = assemble(max_season)
    x.to_parquet(path("processed") / ("phase5_predictions.parquet" if with_test else "phase5_predictions_dev.parquet"),
                 index=False)
    rng = np.random.default_rng(seed)
    R = {"config": cfg()["models"], "sviluppo": block(sample(x, DEV), rng, seed),
         "pesi": {season_label(s): {LABEL_W.get(k, k): float(v) for k, v in w.items()} for s, w in assemble.weights.items()},
         "distribuzione": distribution_choice(x)}
    comp = pd.read_parquet(path("processed") / "components.parquet")
    mx = comp[comp["season"] <= max_season].merge(x[["game_id", "m_final"]], on="game_id", how="left")
    mx["m_open_info"] = mx["m_players_open"] + (mx["m_players"] - mx["m_players_raw"])
    tab, _ = MA.run(mx, [2016, 2023, 2024], rng)
    R["mercato_sviluppo"] = tab.to_dict("records")
    if with_test:
        xt = sample(x, TEST)
        R["test"] = block(xt, rng, seed)
        tab, _ = MA.run(mx, TEST, rng)
        R["mercato_test"] = tab.to_dict("records")
        w = ERR.worst(xt, 2025, 50)
        R["peggiori"] = w.to_dict("records")
        R["peggiori_motivi"] = ERR.reason_summary(w)
        allw = ERR.worst(xt, 2025, len(xt))
        R["motivi_tutte"] = ERR.reason_summary(allw)
        R["errore_aggiustato_tiro"] = {
            "MAE": float((allw["errore"]).abs().mean()),
            "MAE_senza_fortuna_al_tiro": float((allw["errore"] - allw["tiro3"] - allw["liberi"]).abs().mean())}
    return R


def _n(v, d=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    return f"{v:.{d}f}".replace(".", ",")


def _ci(r, k, d=2):
    if k not in r or r[k] is None or not np.isfinite(r[k]):
        return "—"
    return f"{r[k]:+.{d}f} [{r[k + '_lo']:+.{d}f}; {r[k + '_hi']:+.{d}f}]".replace(".", ",")


def write_md(R: dict) -> str:
    L = ["# Fase 5 — Ensemble, calibrazione, backtest completo", ""]

    def section(title, B):
        F = B["metriche"]
        L.extend([f"## {title}", "", f"Partite: {F['partite']}.", "",
                  "| Metrica | Modello | Mercato | Differenza [IC 95%] |", "|---|---:|---:|---:|",
                  f"| MAE scarto | {_n(F['MAE_scarto_modello'], 3)} | {_n(F['MAE_scarto_mercato'], 3)} | {_ci(F, 'dMAE', 3)} |",
                  f"| RMSE scarto | {_n(F['RMSE_scarto_modello'], 3)} | {_n(F['RMSE_scarto_mercato'], 3)} | |",
                  f"| MAE totale | {_n(F['MAE_totale_modello'], 3)} | {_n(F['MAE_totale_mercato'], 3)} | |",
                  f"| MAE punti per squadra | {_n(B['punti']['MAE_punti_squadra'], 3)} | {_n(B['punti']['MAE_punti_squadra_mercato'], 3)} | |",
                  f"| Brier | {_n(F['Brier_modello'], 4)} | {_n(F['Brier_mercato'], 4)} | {_ci(F, 'dBrier', 4)} |",
                  f"| Log loss | {_n(F['LogLoss_modello'], 4)} | {_n(F['LogLoss_mercato'], 4)} | {_ci(F, 'dLogLoss', 4)} |",
                  f"| ECE | {_n(F['ECE_modello'], 4)} | {_n(F['ECE_mercato'], 4)} | |",
                  f"| Vincitori indovinati | {_n(100 * F['vincitori_modello'], 1)}% | {_n(100 * F['vincitori_mercato'], 1)}% | |",
                  f"| Contro lo spread di chiusura | {F['ATS_vinte']}-{F['ATS_perse']} ({_n(100 * F['ATS_pct'], 1)}% [{_n(100 * F['ATS_lo'], 1)}; {_n(100 * F['ATS_hi'], 1)}]) | | |",
                  f"| ROI a -110 | {_n(100 * F['ROI'], 1)}% [{_n(100 * F['ROI_lo'], 1)}; {_n(100 * F['ROI_hi'], 1)}] | | |", ""])
        C = B["copertura"]
        L.extend([f"Probabilità di coprire lo spread di chiusura: log loss {_n(C['LogLoss'], 4)} (moneta: {_n(C['LogLoss_moneta'], 4)}), "
                  f"ECE {_n(C['ECE'], 3)}. Intervalli dello scarto: 50% → {_n(100 * C['copertura50'], 1)}%, 80% → {_n(100 * C['copertura80'], 1)}%, "
                  f"95% → {_n(100 * C['copertura95'], 1)}% delle partite.", "",
                  f"Partite in cui modello e mercato differiscono di almeno 3 punti: {B['disaccordo_3']['partite']}; "
                  f"errore medio modello {_n(B['disaccordo_3']['MAE_modello'])}, mercato {_n(B['disaccordo_3']['MAE_mercato'])}.", "",
                  "### Componenti e ablation (scarto)", "", "| Modello | MAE | vs mercato | vs ensemble finale |", "|---|---:|---:|---:|"])
        for r in B["scarto"]:
            L.append(f"| {r['modello']} | {_n(r['MAE'], 3)} | {_ci(r, 'vs_mercato', 3)} | {_ci(r, 'vs_finale', 3)} |")
        L.extend(["", "### Totale", "", "| Modello | MAE | vs mercato | vs finale |", "|---|---:|---:|---:|"])
        for r in B["totale"]:
            L.append(f"| {r['modello']} | {_n(r['MAE'], 3)} | {_ci(r, 'vs_mercato', 3)} | {_ci(r, 'vs_finale', 3)} |")
        L.extend(["", "### Per stagione", "", "| Stagione | Partite | MAE | mercato | differenza [IC 95%] | MAE totale | mercato | Brier | mercato |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
        for r in B["per_stagione"]:
            L.append(f"| {r['stagione']} | {r['partite']} | {_n(r['MAE'])} | {_n(r['MAE_mercato'])} | {_ci(r, 'dMAE')} | "
                     f"{_n(r['MAE_totale'])} | {_n(r['MAE_totale_mercato'])} | {_n(r['Brier'], 4)} | {_n(r['Brier_mercato'], 4)} |")
        L.extend(["", "### Per mese", "", "| Mese | Partite | MAE | mercato | MAE totale | mercato |", "|---|---:|---:|---:|---:|---:|"])
        for r in B["per_mese"]:
            if r["partite"] >= 30:
                L.append(f"| {r['mese']} | {r['partite']} | {_n(r['MAE'])} | {_n(r['MAE_mercato'])} | {_n(r['MAE_totale'])} | {_n(r['MAE_totale_mercato'])} |")
        L.append("")

    if "test" in R:
        section("Test 2025-26 (mai usato per scelte o tarature)", R["test"])
    section("Sviluppo 2018-19 → 2024-25", R["sviluppo"])
    L.extend(["## Pesi dell'ensemble (stimati sulle stagioni precedenti)", "",
              "| Stagione | " + " | ".join(LABEL_W[k] for k in ["m_players", "m_base", "m_team", "m_elo", "m_gbm", "costante"]) + " |",
              "|---|" + "---:|" * 6])
    for s, w in R["pesi"].items():
        L.append(f"| {s} | " + " | ".join(_n(w.get(LABEL_W[k], 0.0)) for k in ["m_players", "m_base", "m_team", "m_elo", "m_gbm", "costante"]) + " |")
    L.extend(["", "## Forma della distribuzione dello scarto (sviluppo)", "",
              "| Forma | Log loss | Brier | ECE | copertura 80% | copertura 95% | effetto del totale | effetto della differenza |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for r in R["distribuzione"]:
        L.append(f"| {r['forma']} | {_n(r['LogLoss'], 4)} | {_n(r['Brier'], 4)} | {_n(r['ECE'], 4)} | {_n(100 * r['copertura80'], 1)}% | "
                 f"{_n(100 * r['copertura95'], 1)}% | {_n(r['effetto_totale'], 2)} | {_n(r['effetto_differenza'], 3)} |")
    for key, title in (("mercato_sviluppo", "Modello consapevole del mercato — sviluppo (2016-17, 2023-24, 2024-25)"),
                       ("mercato_test", "Modello consapevole del mercato — test 2025-26")):
        if key not in R:
            continue
        L.extend(["", f"## {title}", "",
                  "| Informazione | Partite | Correlazione col movimento | Errore sul movimento (apertura → modello) | Direzione giusta | CLV medio | CLV con disaccordo ≥ 3 |",
                  "|---|---:|---:|---:|---:|---:|---:|"])
        for r in R[key]:
            L.append(f"| {r['informazione']} | {r['partite']} | {_n(r['corr'])} | {_n(r['MAE_movimento_naive'])} → {_n(r['MAE_movimento_modello'])} | "
                     f"{_n(100 * r['direzione'], 1)}% [{_n(100 * r['direzione_lo'], 1)}; {_n(100 * r['direzione_hi'], 1)}] su {r['direzione_partite']} | "
                     f"{_ci(r, 'CLV')} | {_ci(r, 'CLV_forte')} su {r['CLV_forte_partite']} |")
    if "peggiori" in R:
        L.extend(["", "## Le 50 partite peggiori del test (ensemble)", "",
                  "Motivi: " + ", ".join(f"{k} {v}" for k, v in R["peggiori_motivi"].items()), "",
                  "| Data | Partita | Risultato | Scarto | Pronostico | Mercato | Errore | Motivi |", "|---|---|---|---:|---:|---:|---:|---|"])
        for r in R["peggiori"]:
            mkt = "" if r["mercato"] is None else f"{r['mercato']:+.1f}"
            L.append(f"| {r['data']} | {r['partita']} | {r['risultato']} | {r['scarto_vero']:+d} | {r['pronostico']:+.1f} | "
                     f"{mkt} | {r['errore']:+.1f} | {r['motivi']} |")
    return "\n".join(L) + "\n"


def main(with_test: bool) -> dict:
    R = build(with_test)
    name = "fase5" if with_test else "fase5_sviluppo"
    (path("reports") / f"{name}.json").write_text(json.dumps(R, indent=1, default=float, ensure_ascii=False))
    (path("reports") / f"{name}.md").write_text(write_md(R))
    if with_test:
        from nba.evaluate.report_html import write_html
        (path("reports") / "fase5.html").write_text(write_html(R))
    return R
