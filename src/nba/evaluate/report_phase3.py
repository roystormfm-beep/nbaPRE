"""Tabelle della fase 3: reports/fase3.md e reports/fase3.json.

Stesse partite per tutti i modelli: stagioni di sviluppo con injury report (2018-19 → 2024-25), partite con linea.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from nba.config import cfg, path, season_label
from nba.evaluate.metrics import _boot_ci, attach_market

PHI = np.vectorize(lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2))))


def assemble(seasons: list[int]) -> pd.DataFrame:
    proc = path("processed")
    pm = pd.read_parquet(proc / "player_model_report_predictions.parquet")
    pm = pm[pm["season"].isin(seasons)][["game_id", "season", "date", "home", "away", "hpts", "apts", "margin_pred", "total_pred"]]
    pm = pm.rename(columns={"margin_pred": "giocatori_report", "total_pred": "tot_giocatori"})
    old = pd.read_parquet(proc / "player_model_predictions.parquet")
    for mn, col in (("proiettati_senza_report", "giocatori_senza_report"), ("veri", "giocatori_minuti_veri")):
        o = old[old["minuti"] == mn][["game_id", "margin_pred"]].rename(columns={"margin_pred": col})
        pm = pm.merge(o, on="game_id", how="left")
    b = pd.read_parquet(proc / "baseline_report_predictions.parquet")
    bp = b.pivot_table(index="game_id", columns="variant", values="margin_pred")
    bp.columns = [f"baseline_{c}" for c in bp.columns]
    bt = b[b["variant"] == "injury_report"][["game_id", "total_pred", "sd"]].rename(columns={"total_pred": "tot_baseline", "sd": "sd_baseline"})
    x = pm.merge(bp.reset_index(), on="game_id").merge(bt, on="game_id")
    x["miscela_report"] = (x["giocatori_report"] + x["baseline_injury_report"]) / 2
    # solo partite con un injury report pre-partita disponibile (l'archivio del 2018-19 parte da metà dicembre)
    has = set()
    for s in seasons:
        f = path("external") / "injury" / f"needed_{s}.csv"
        if f.exists():
            has |= set(pd.read_csv(f, dtype={"game_id": str})["game_id"].str.zfill(10))
    x = x[x["game_id"].isin(has)]
    x = attach_market(x).dropna(subset=["close_spread_home", "p_home_mkt"])
    return x


MODELS = [("baseline_senza", "Baseline senza assenze"),
          ("baseline_injury_report", "Baseline con injury report"),
          ("giocatori_senza_report", "Giocatori + minuti, senza injury report"),
          ("giocatori_report", "Giocatori + minuti con injury report"),
          ("miscela_report", "Miscela 50/50 (giocatori + baseline, injury report)"),
          ("baseline_chi_ha_giocato", "Baseline che sa chi gioca (ottimistico)"),
          ("giocatori_minuti_veri", "Giocatori con i minuti giocati davvero (ottimistico)")]


def _sd_by_season(x: pd.DataFrame, col: str) -> dict:
    """Deviazione standard per le probabilità: errore quadratico medio sulle stagioni precedenti (minimo 2)."""
    out = {}
    for s in sorted(x["season"].unique()):
        prev = x[x["season"] < s]
        if len(prev) < 500:
            prev = x[x["season"] == s].iloc[:0]
        e = (prev["hpts"] - prev["apts"] - prev[col]) if len(prev) else pd.Series([13.0])
        out[s] = float(np.sqrt((e ** 2).mean())) if len(prev) else 13.0
    return out


def summary(x: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(cfg()["seed"])
    y = (x["hpts"] - x["apts"]).to_numpy(float)
    win = (y > 0).astype(float)
    mkt = -x["close_spread_home"].to_numpy(float)
    ae_mkt = np.abs(y - mkt)
    br_mkt = (x["p_home_mkt"].to_numpy(float) - win) ** 2
    rows = []
    for col, label in MODELS:
        if col not in x:
            continue
        pred = x[col].to_numpy(float)
        ok = np.isfinite(pred)
        sd = x["season"].map(_sd_by_season(x, col)).to_numpy(float)
        p = PHI(pred / sd)
        ae = np.abs(y - pred)
        br = (p - win) ** 2
        d, lo, hi = _boot_ci((ae - ae_mkt)[ok], rng)
        db, blo, bhi = _boot_ci((br - br_mkt)[ok], rng)
        rows.append({"modello": label, "colonna": col, "partite": int(ok.sum()), "MAE": ae[ok].mean(),
                     "dMAE": d, "dMAE_lo": lo, "dMAE_hi": hi, "RMSE": np.sqrt(((y - pred)[ok] ** 2).mean()),
                     "Brier": br[ok].mean(), "dBrier": db, "dBrier_lo": blo, "dBrier_hi": bhi})
    rows.append({"modello": "Mercato (linea di chiusura)", "colonna": "mercato", "partite": len(x), "MAE": ae_mkt.mean(),
                 "RMSE": np.sqrt(((y - mkt) ** 2).mean()), "Brier": br_mkt.mean()})
    return pd.DataFrame(rows)


def per_season(x: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for s, g in x.groupby("season"):
        y = g["hpts"] - g["apts"]
        r = {"stagione": season_label(s), "partite": len(g), "mercato": (y + g["close_spread_home"]).abs().mean()}
        for col, _ in MODELS[:5]:
            r[col] = (y - g[col]).abs().mean()
        rows.append(r)
    return pd.DataFrame(rows)


def write(seasons: list[int], extra: dict | None = None) -> dict:
    x = assemble(seasons)
    s, ps = summary(x), per_season(x)
    tot = {"mercato": float(((x["hpts"] + x["apts"]) - x["close_total"]).abs().mean()),
           "baseline": float(((x["hpts"] + x["apts"]) - x["tot_baseline"]).abs().mean()),
           "giocatori": float(((x["hpts"] + x["apts"]) - x["tot_giocatori"]).abs().mean())}
    res = {"sintesi": s.to_dict("records"), "per_stagione": ps.to_dict("records"), "totali_MAE": tot, **(extra or {})}
    with open(path("reports") / "fase3.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    f2 = lambda v, d=2: "—" if pd.isna(v) else f"{v:.{d}f}".replace(".", ",")  # noqa: E731
    L = ["# Fase 3 — giocatori, minuti, disponibilità", "",
         f"Stagioni {season_label(min(seasons))} → {season_label(max(seasons))}, {len(x)} partite con injury report e linea.", "",
         "| Modello | Errore medio scarto | Differenza dal mercato [IC 95%] | RMSE | Brier | Differenza Brier [IC 95%] |",
         "|---|---|---|---|---|---|"]
    for _, r in s.iterrows():
        L.append(f"| {r['modello']} | {f2(r['MAE'])} | {f2(r.get('dMAE'))} [{f2(r.get('dMAE_lo'))}; {f2(r.get('dMAE_hi'))}] | "
                 f"{f2(r['RMSE'])} | {f2(r['Brier'], 4)} | {f2(r.get('dBrier'), 4)} [{f2(r.get('dBrier_lo'), 4)}; {f2(r.get('dBrier_hi'), 4)}] |")
    L += ["", "| Stagione | Partite | Mercato | Baseline senza | Baseline report | Giocatori senza report | Giocatori report | Miscela |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in ps.iterrows():
        L.append(f"| {r['stagione']} | {r['partite']} | {f2(r['mercato'])} | {f2(r['baseline_senza'])} | {f2(r['baseline_injury_report'])} | "
                 f"{f2(r['giocatori_senza_report'])} | {f2(r['giocatori_report'])} | {f2(r['miscela_report'])} |")
    L += ["", f"Errore medio sul totale: mercato {f2(tot['mercato'])}, baseline {f2(tot['baseline'])}, giocatori {f2(tot['giocatori'])}."]
    (path("reports") / "fase3.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return res
