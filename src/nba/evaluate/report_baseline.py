"""Tabelle della fase 2 (baseline contro mercato): reports/baseline_fase2.md e .json."""
from __future__ import annotations

import json

import pandas as pd

from nba.config import path, season_label
from nba.evaluate.metrics import attach_market, table

VARIANTS = {"senza": "senza assenze", "chi_ha_giocato": "assenze \"chi ha giocato\" (ottimistico)"}


def _f(x, d=2):
    return "—" if pd.isna(x) else f"{x:.{d}f}".replace(".", ",")


MAIN = {"ATS": "ATS_pct", "CLV": "CLV_punti"}


def _ci(r, k, d=2, pct=False):
    m, lo, hi = r[MAIN.get(k, k)], r[k + "_lo"], r[k + "_hi"]
    if pct:
        return f"{_f(100 * m, 1)}% [{_f(100 * lo, 1)}; {_f(100 * hi, 1)}]"
    return f"{_f(m, d)} [{_f(lo, d)}; {_f(hi, d)}]"


def summary_table(p: pd.DataFrame, label: str) -> tuple[list[str], pd.DataFrame]:
    p = p.copy()
    p["periodo"] = p["season"].map(lambda s: "test 2025-26" if s == 2025 else "sviluppo 2014-15 → 2024-25")
    t = table(p, ["variant", "periodo"])
    L = [f"### {label}", "",
         "| Assenze | Periodo | Partite | Errore medio scarto: modello / mercato | Differenza [IC 95%] | Brier: modello / mercato | Differenza [IC 95%] | Log loss: modello / mercato | Calibrazione (ECE): modello / mercato | Vincitori: modello / mercato | Errore medio totale: modello / mercato | Contro lo spread (IC 95%) | ROI a -110 (IC 95%) | CLV in punti (IC 95%) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in t.sort_values(["variant", "periodo"], ascending=[False, True]).iterrows():
        L.append(f"| {VARIANTS[r['variant']]} | {r['periodo']} | {r['partite']} | {_f(r['MAE_scarto_modello'])} / {_f(r['MAE_scarto_mercato'])} | "
                 f"{_ci(r, 'dMAE')} | {_f(r['Brier_modello'], 4)} / {_f(r['Brier_mercato'], 4)} | {_ci(r, 'dBrier', 4)} | "
                 f"{_f(r['LogLoss_modello'], 4)} / {_f(r['LogLoss_mercato'], 4)} | {_f(r['ECE_modello'], 3)} / {_f(r['ECE_mercato'], 3)} | "
                 f"{_f(100 * r['vincitori_modello'], 1)}% / {_f(100 * r['vincitori_mercato'], 1)}% | "
                 f"{_f(r['MAE_totale_modello'])} / {_f(r['MAE_totale_mercato'])} | {_ci(r, 'ATS', pct=True)} | {_ci(r, 'ROI', pct=True)} | "
                 f"{_ci(r, 'CLV') if pd.notna(r.get('CLV_punti')) else '—'} |")
    return L, t


def season_table(p: pd.DataFrame) -> list[str]:
    t = table(p, ["variant", "season"])
    L = ["| Stagione | Partite | Mercato: errore medio | Modello senza assenze | Differenza [IC 95%] | Modello \"chi ha giocato\" | Differenza [IC 95%] |",
         "|---|---|---|---|---|---|---|"]
    for s in sorted(t["season"].unique()):
        a = t[(t.season == s) & (t.variant == "senza")].iloc[0]
        b = t[(t.season == s) & (t.variant == "chi_ha_giocato")].iloc[0]
        L.append(f"| {season_label(s)} | {a['partite']} | {_f(a['MAE_scarto_mercato'])} | {_f(a['MAE_scarto_modello'])} | {_ci(a, 'dMAE')} | "
                 f"{_f(b['MAE_scarto_modello'])} | {_ci(b, 'dMAE')} |")
    return L


def write(extra: dict | None = None) -> dict:
    proc = path("processed")
    res = {}
    L = ["# Fase 2 — baseline contro mercato", "",
         "Intervalli di confidenza al 95% da bootstrap appaiato sulle partite (2.000 ricampionamenti).",
         "Differenza = modello − mercato: positiva vuol dire che il mercato è più preciso.",
         "CLV: lato scelto dal modello confrontandosi con la linea d'apertura; punti guadagnati rispetto alla chiusura "
         "(solo stagioni con apertura: 2014-15 → 2016-17 e 2023-24 → 2025-26).", ""]
    p = attach_market(pd.read_parquet(proc / "baseline_predictions.parquet"))
    lines, t = summary_table(p, "Modello v2 della pagina, parametri attuali")
    L += lines + ["", "### Per stagione (errore medio sullo scarto)", ""] + season_table(p)
    res["pagina"] = t.to_dict("records")
    rt = proc / "baseline_retuned_predictions.parquet"
    if rt.exists():
        q = attach_market(pd.read_parquet(rt))
        lines, t2 = summary_table(q, "Modello v2 ritarato sulle sole stagioni di sviluppo")
        L += ["", *lines]
        res["ritarato"] = t2.to_dict("records")
    if extra:
        L += ["", "### Altre note", "", *[f"- {k}: {v}" for k, v in extra.items()]]
    (path("reports") / "baseline_fase2.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with open(path("reports") / "baseline_fase2.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    return res
