"""Backtest walk-forward del baseline (modello v2 della pagina) su tutte le stagioni storiche.

Ogni giorno: ricostruisco gli ingressi del mattino (solo informazioni precedenti), ricalcolo il modello e
pronostico le partite del giorno. Due versioni delle assenze (vedi history_inputs).
"""
from __future__ import annotations

import time

import pandas as pd

from nba.config import path
from nba.evaluate.history_inputs import SeasonInputs
from nba.models import baseline as B


def run_season(season: int, opts: dict | None = None, with_reports: bool = False) -> pd.DataFrame:
    si = SeasonInputs(season)
    reports = None
    if with_reports:
        from nba.features.availability import pregame_reports
        reports = pregame_reports(season)
        if reports.empty:
            reports = None
    rows = []
    for d in si.days():
        raw, today = si.raw_for_day(d)
        ctx = B.build(raw, today=d, **(opts or {}))
        ctxr = None
        if reports is not None:
            rawr, _ = si.raw_for_day(d, reports=reports)
            ctxr = B.build(rawr, today=d, **(opts or {}))
        for r in today.itertuples():
            g = B.find_game(ctx, d, r.away, r.home)
            if g is None:
                continue
            variants = [("senza", ctx, True), ("chi_ha_giocato", ctx, False)]
            if ctxr is not None:
                variants.append(("injury_report", ctxr, False))
            for variant, cx, no_inj in variants:
                p = B.predict(cx, B.find_game(cx, d, r.away, r.home), no_inj=no_inj)
                rows.append({"game_id": r.game_id, "season": season, "date": d, "home": r.home, "away": r.away,
                             "variant": variant, "hp": p["hp"], "ap": p["ap"], "margin_pred": p["margin"],
                             "total_pred": p["total"], "sd": p["sd"], "p_home": p["pHome"],
                             "adj_home": p["adjH"]["delta"], "adj_away": p["adjA"]["delta"],
                             "hpts": r.hpts, "apts": r.apts})
    return pd.DataFrame(rows)


def _one(args):
    s, opts = args[0], args[1]
    return run_season(s, opts, with_reports=args[2] if len(args) > 2 else False)


def run(seasons: list[int], opts: dict | None = None, name: str = "baseline_predictions", workers: int = 2,
        with_reports: bool = False) -> pd.DataFrame:
    """Backtest di tutte le stagioni; opts = parametri diversi da quelli della pagina (es. versione ritarata)."""
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        out = list(ex.map(_one, [(s, opts, with_reports) for s in seasons]))
    res = pd.concat(out, ignore_index=True)
    res.to_parquet(path("processed") / f"{name}.parquet", index=False)
    print(f"  {len(seasons)} stagioni, {res['game_id'].nunique()} partite ({time.time() - t0:.0f}s)", flush=True)
    return res
