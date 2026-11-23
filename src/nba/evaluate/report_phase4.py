"""Tabelle della fase 4: reports/fase4.md, reports/fase4.json e data/processed/phase4_predictions.parquet.

Stesso campione della fase 3: stagioni di sviluppo con injury report (2018-19 → 2024-25), partite con linea di chiusura.
La stagione di test 2025-26 non viene toccata.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from nba.config import cfg, path, season_label
from nba.evaluate.metrics import _boot_ci, attach_market, evaluate
from nba.evaluate.phase4 import EVAL, base_table, officials, report_games, total_table
from nba.models import context_model as CM

PHI = np.vectorize(lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2))))
ALL = list(range(2015, 2025))           # anche le stagioni prima del 2018, per avere lo storico degli errori
GROUPS_M = ["base", "squadre", "riposo", "viaggi", "altura", "fine_stagione"]
ESS = "Contesto essenziale: campo + riposo + fine stagione (scelto)"
LABEL = {"base": "vantaggio del campo (ricalibrato)", "squadre": "vantaggio del campo per squadra",
         "riposo": "riposo e calendario fitto", "viaggi": "viaggi e fusi orari", "altura": "altura (Denver, Utah)",
         "fine_stagione": "fine stagione (squadre senza obiettivi / già sicure)", "arbitri": "arbitri",
         "stagione": "momento della stagione", "altro": "altro"}


def _sd(pred: pd.DataFrame, y: pd.Series) -> pd.Series:
    """Deviazione standard dell'errore per stagione: RMSE delle 3 stagioni precedenti (solo passato)."""
    e = (y - pred["pred"]) ** 2
    out = {}
    for s in sorted(pred["season"].unique()):
        m = pred["season"].between(s - 3, s - 1)
        out[s] = float(np.sqrt(e[m].mean())) if m.sum() >= 500 else 13.0
    return pred["season"].map(out)


def _row(label, x, pred_col, y, mkt, ref_col=None, rng=None):
    ae = (y - x[pred_col]).abs()
    r = {"variante": label, "partite": int(len(x)), "MAE": float(ae.mean()),
         "RMSE": float(np.sqrt(((y - x[pred_col]) ** 2).mean()))}
    m, lo, hi = _boot_ci((ae - (y - mkt).abs()).to_numpy(), rng)
    r["vs_mercato"], r["vs_mercato_lo"], r["vs_mercato_hi"] = m, lo, hi
    if ref_col is not None:
        m, lo, hi = _boot_ci((ae - (y - x[ref_col]).abs()).to_numpy(), rng)
        r["vs_fase3"], r["vs_fase3_lo"], r["vs_fase3_hi"] = m, lo, hi
    return r


def margin_part(rng):
    df = base_table()
    df["y"] = df["hpts"] - df["apts"]
    df["base"] = df["margin_pred"]
    has = report_games()

    def run(groups):
        pr = CM.fit_predict(df, "margin", ALL, groups=groups)
        return pr, dict(getattr(CM.fit_predict, "last_coef", {}))

    variants = {"Fase 3: giocatori + injury report (nessun contesto)": None,
                "+ " + LABEL["base"]: {"base"},
                "Contesto completo": set(GROUPS_M)}
    for g in GROUPS_M[1:]:
        variants[f"Contesto completo senza {LABEL[g]}"] = set(GROUPS_M) - {g}
    variants[ESS] = {"base", "riposo", "fine_stagione"}
    preds, coefs = {}, {}
    for label, groups in variants.items():
        if groups is None:
            preds[label] = df[["game_id", "season"]].assign(pred=df["base"])
        else:
            preds[label], coefs[label] = run(groups)
    keep = df[df["game_id"].isin(has)][["game_id"]]
    x = attach_market(df.merge(keep, on="game_id")).dropna(subset=["close_spread_home"])
    x = x[x["season"].isin(EVAL)]
    for label, p in preds.items():
        x = x.merge(p[["game_id", "pred"]].rename(columns={"pred": label}), on="game_id", how="left")
    y = x["hpts"] - x["apts"]
    mkt = -x["close_spread_home"]
    ref = "Fase 3: giocatori + injury report (nessun contesto)"
    rows = [_row(label, x, label, y, mkt, None if label == ref else ref, rng) for label in preds]
    return df, preds, coefs, pd.DataFrame(rows), x, ref


def total_part(rng):
    df = total_table()
    has = report_games()
    refs = officials()
    preds = {"Fase 3: giocatori (punti dai minuti e dall'efficienza)": df[["game_id", "season"]].assign(pred=df["total_pred"]),
             "Squadre: ritmo × efficienza di squadra": df[["game_id", "season"]].assign(pred=df["total_team"]),
             "Combinato: ritmo di squadra × efficienza dei giocatori disponibili": df[["game_id", "season"]].assign(pred=df["base"])}
    preds["Combinato + correzione di livello (scelto)"] = CM.fit_predict(df, "total", ALL, groups={"base"})
    preds["+ contesto (riposo, viaggi, altura, momento della stagione)"] = CM.fit_predict(df, "total", ALL)
    preds["+ arbitri"] = CM.fit_predict(df, "total", ALL, refs=refs, groups={"base", "arbitri"})
    ref_coef = {k: v for k, v in CM.fit_predict.last_coef.items() if k.startswith("arbitro_")}
    keep = df[df["game_id"].isin(has)][["game_id"]]
    x = attach_market(df.merge(keep, on="game_id")).dropna(subset=["close_total"])
    x = x[x["season"].isin(EVAL)]
    for label, p in preds.items():
        x = x.merge(p[["game_id", "pred"]].rename(columns={"pred": label}), on="game_id", how="left")
    y = x["hpts"] + x["apts"]
    mkt = x["close_total"]
    ref = "Fase 3: giocatori (punti dai minuti e dall'efficienza)"
    rows = [_row(label, x, label, y, mkt, None if label == ref else ref, rng) for label in preds]
    ref_sd = float(np.std(list(ref_coef.values()))) if ref_coef else float("nan")
    return df, preds, pd.DataFrame(rows), ref_sd, len(ref_coef)


def build() -> dict:
    seed = cfg()["seed"]
    rng = np.random.default_rng(seed)
    dfm, pm, coefs, tab_m, xm, ref_m = margin_part(rng)
    dft, pt, tab_t, ref_sd, n_refs = total_part(rng)

    # modello finale della fase 4
    FIN_M, FIN_T = ESS, "Combinato + correzione di livello (scelto)"
    M = pm[FIN_M].rename(columns={"pred": "margin_pred"})
    T = pt[FIN_T][["game_id", "pred"]].rename(columns={"pred": "total_pred"})
    out = dfm[["game_id", "date", "home", "away", "hpts", "apts", "margin_pred"]].rename(columns={"margin_pred": "margin_fase3"})
    out = out.merge(M, on="game_id").merge(T, on="game_id")
    y = out["hpts"] - out["apts"]
    out["sd"] = _sd(out.rename(columns={"margin_pred": "pred"}), y)
    out["p_home"] = PHI(out["margin_pred"] / out["sd"])
    out["hp"] = (out["total_pred"] + out["margin_pred"]) / 2
    out["ap"] = (out["total_pred"] - out["margin_pred"]) / 2
    out.to_parquet(path("processed") / "phase4_predictions.parquet", index=False)

    has = report_games()
    ev = attach_market(out[out["game_id"].isin(has) & out["season"].isin(EVAL)]).dropna(subset=["close_spread_home", "p_home_mkt"])
    overall = evaluate(ev, seed)
    per_season = []
    for s, g in ev.groupby("season"):
        r = evaluate(g, seed)
        per_season.append({"stagione": season_label(s), "partite": r["partite"],
                           "MAE_scarto": r["MAE_scarto_modello"], "MAE_scarto_mercato": r["MAE_scarto_mercato"],
                           "MAE_totale": r["MAE_totale_modello"], "MAE_totale_mercato": r["MAE_totale_mercato"],
                           "Brier": r["Brier_modello"], "Brier_mercato": r["Brier_mercato"]})
    # punti per squadra (casa e ospiti) contro i punti impliciti nel mercato
    evt = ev.dropna(subset=["close_total"])
    mh = (evt["close_total"] - evt["close_spread_home"]) / 2
    ma = (evt["close_total"] + evt["close_spread_home"]) / 2
    pts = {"MAE_punti_squadra": float(pd.concat([(evt["hpts"] - evt["hp"]).abs(), (evt["apts"] - evt["ap"]).abs()]).mean()),
           "MAE_punti_squadra_mercato": float(pd.concat([(evt["hpts"] - mh).abs(), (evt["apts"] - ma).abs()]).mean())}
    # Brier anche per la fase 3 (stessa deviazione standard calcolata sul suo storico)
    f3 = out.rename(columns={"margin_fase3": "pred"})
    sd3 = _sd(f3, y)
    out["p_fase3"] = PHI(out["margin_fase3"] / sd3)
    e3 = ev.merge(out[["game_id", "p_fase3"]], on="game_id")
    win = (e3["hpts"] > e3["apts"]).astype(float)
    m, lo, hi = _boot_ci(((e3["p_home"] - win) ** 2 - (e3["p_fase3"] - win) ** 2).to_numpy(), rng)
    brier_vs_f3 = {"Brier_fase3": float(((e3["p_fase3"] - win) ** 2).mean()), "dBrier_vs_fase3": m,
                   "dBrier_vs_fase3_lo": lo, "dBrier_vs_fase3_hi": hi}
    coef = coefs.get(FIN_M, {})
    return {"margine": tab_m.to_dict("records"), "totale": tab_t.to_dict("records"), "finale": overall,
            "per_stagione": per_season, "punti": pts, "brier_fase3": brier_vs_f3,
            "coefficienti_2024_25": {k: v for k, v in coef.items() if not k.startswith("casa_")},
            "vantaggio_campo_squadre_2024_25": {k[5:]: v for k, v in coef.items() if k.startswith("casa_")},
            "arbitri": {"numero": n_refs, "dev_std_effetti": ref_sd}}


def _f(v, d=2):
    return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{d}f}"


def _ci(r, k, d=2):
    if k not in r or r[k] is None or not np.isfinite(r[k]):
        return "—"
    return f"{r[k]:+.{d}f} [{r[k + '_lo']:+.{d}f}; {r[k + '_hi']:+.{d}f}]"


def write(R: dict) -> str:
    L = ["# Fase 4 — Contesto e totali", "",
         "Campione: stagioni di sviluppo con injury report pre-partita (2018-19 → 2024-25), partite con linea di chiusura.",
         "Ogni correzione è stimata solo sulle stagioni precedenti a quella pronosticata. Stagione di test 2025-26 non toccata.",
         "Tra parentesi: intervallo di confidenza al 95% (bootstrap appaiato). Negativo = errore più basso.", "",
         "## Scarto (casa − ospiti)", "",
         "| Variante | Partite | MAE | RMSE | vs fase 3 | vs mercato |", "|---|---:|---:|---:|---:|---:|"]
    for r in R["margine"]:
        L.append(f"| {r['variante']} | {r['partite']} | {_f(r['MAE'], 3)} | {_f(r['RMSE'], 3)} | {_ci(r, 'vs_fase3', 3)} | {_ci(r, 'vs_mercato', 3)} |")
    L += ["", "## Totale punti", "", "| Variante | Partite | MAE | RMSE | vs fase 3 | vs mercato |", "|---|---:|---:|---:|---:|---:|"]
    for r in R["totale"]:
        L.append(f"| {r['variante']} | {r['partite']} | {_f(r['MAE'], 3)} | {_f(r['RMSE'], 3)} | {_ci(r, 'vs_fase3', 3)} | {_ci(r, 'vs_mercato', 3)} |")
    a = R["arbitri"]
    L += ["", f"Arbitri: {a['numero']} arbitri stimati; effetti molto piccoli (deviazione standard {_f(a['dev_std_effetti'])} punti sul totale).", ""]
    F = R["finale"]
    L += ["## Modello finale della fase 4 (scarto: contesto essenziale; totale: combinato + livello)", "",
          "| Metrica | Modello | Mercato | Differenza [IC 95%] |", "|---|---:|---:|---:|",
          f"| MAE scarto | {_f(F['MAE_scarto_modello'], 3)} | {_f(F['MAE_scarto_mercato'], 3)} | {_ci(F, 'dMAE', 3)} |",
          f"| MAE totale | {_f(F['MAE_totale_modello'], 3)} | {_f(F['MAE_totale_mercato'], 3)} | |",
          f"| MAE punti per squadra | {_f(R['punti']['MAE_punti_squadra'], 3)} | {_f(R['punti']['MAE_punti_squadra_mercato'], 3)} | |",
          f"| Brier (vittoria casa) | {_f(F['Brier_modello'], 4)} | {_f(F['Brier_mercato'], 4)} | {_ci(F, 'dBrier', 4)} |",
          f"| Log loss | {_f(F['LogLoss_modello'], 4)} | {_f(F['LogLoss_mercato'], 4)} | {_ci(F, 'dLogLoss', 4)} |",
          f"| Calibrazione (ECE) | {_f(F['ECE_modello'], 4)} | {_f(F['ECE_mercato'], 4)} | |",
          f"| Vincitori indovinati | {_f(100 * F['vincitori_modello'], 1)}% | {_f(100 * F['vincitori_mercato'], 1)}% | |", "",
          f"Brier fase 3 sullo stesso campione: {_f(R['brier_fase3']['Brier_fase3'], 4)}; "
          f"fase 4 − fase 3: {_ci(R['brier_fase3'], 'dBrier_vs_fase3', 4)}.", "",
          "## Per stagione (modello finale)", "",
          "| Stagione | Partite | MAE scarto | mercato | MAE totale | mercato | Brier | mercato |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in R["per_stagione"]:
        L.append(f"| {r['stagione']} | {r['partite']} | {_f(r['MAE_scarto'])} | {_f(r['MAE_scarto_mercato'])} | "
                 f"{_f(r['MAE_totale'])} | {_f(r['MAE_totale_mercato'])} | {_f(r['Brier'], 4)} | {_f(r['Brier_mercato'], 4)} |")
    L += ["", "## Effetti stimati (modello usato per il 2024-25, allenato fino al 2023-24)", "",
          "Punti di scarto per la squadra di casa quando la condizione vale per lei (al netto di quanto già visto dal modello giocatori).", "",
          "| Variabile | Effetto |", "|---|---:|"]
    for k, v in R["coefficienti_2024_25"].items():
        L.append(f"| {k} | {v:+.2f} |")
    hca = R["vantaggio_campo_squadre_2024_25"]
    if hca:
        top = sorted(hca.items(), key=lambda kv: -kv[1])
        L += ["", "Vantaggio del campo per squadra (scostamento dalla media): " +
              ", ".join(f"{t} {v:+.2f}" for t, v in top[:3]) + " … " + ", ".join(f"{t} {v:+.2f}" for t, v in top[-3:])]
    return "\n".join(L) + "\n"


def main() -> dict:
    R = build()
    (path("reports") / "fase4.json").write_text(json.dumps(R, indent=1, default=float))
    (path("reports") / "fase4.md").write_text(write(R))
    return R


if __name__ == "__main__":
    main()
    print((path("reports") / "fase4.md").read_text())
