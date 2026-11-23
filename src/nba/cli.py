"""Comandi: nba ingest | qc | (backtest, predict, report nelle fasi successive)."""
from __future__ import annotations

import argparse
import sys
import time

from nba.config import all_seasons


def parse_season(s: str) -> int:
    """'2025-26' oppure '2025' -> 2025."""
    return int(str(s).split("-")[0])


def cmd_ingest(args):
    from nba.ingest.build import build
    from nba.ingest.pbp_download import fetch_all
    seasons = all_seasons() if args.all or not args.season else [parse_season(s) for s in args.season]
    fetch_all(seasons, kinds=["nbastatsv3", "nbastats", "cdnnba", "pbpstats", "matchups"])
    for s in seasons:
        t0 = time.time()
        r = build(s)
        from nba.ingest.external import attach
        r["espn"] = attach(s)          # punteggi, sedi e quote ESPN, se scaricati (data/external/espn)
        print(f"{s}: {r} ({time.time() - t0:.0f}s)", flush=True)


def cmd_qc(args):
    from nba.ingest.qc import run_qc
    run_qc()


def cmd_backtest(args):
    import json
    from nba.config import path
    from nba.evaluate import backtest_baseline
    seasons = parse_range(args.seasons)
    backtest_baseline.run(seasons)
    if args.retune:
        from nba.evaluate import tune_baseline
        out = tune_baseline.run()
        print("parametri ritarati:", out["scelti"])
    p = path("processed") / "baseline_retuned_params.json"
    if p.exists():
        backtest_baseline.run(seasons, opts=json.load(open(p)), name="baseline_retuned_predictions")
    cmd_report(args)


def cmd_report(args):
    fase = getattr(args, "fase", 2)
    if fase == 2:
        from nba.evaluate.report_baseline import write
        write()
    elif fase == 4:
        from nba.evaluate import report_phase4
        report_phase4.main()
    elif fase == 5:
        from nba.evaluate import components, report_phase5
        components.build()
        report_phase5.main(with_test=not getattr(args, "solo_sviluppo", False))
        print("scritto reports/fase5.html")
    print(f"scritto reports/{'baseline_fase2' if fase == 2 else f'fase{fase}'}.md")


def parse_range(s: str) -> list[int]:
    """'2014-2026' -> [2014..2026]; '2018,2025' -> [2018, 2025]."""
    out = []
    for part in str(s).split(","):
        if "-" in part and len(part.split("-")[1]) == 4:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part.strip():
            out.append(parse_season(part))
    return out


def cmd_fetch_remote(args):
    """Scaricamenti da siti esterni (da lanciare su GitHub Actions o sul tuo computer)."""
    seasons = parse_range(args.seasons)
    tasks = ["probe", "espn", "bref"] if args.task == "all" else [args.task]
    if args.task == "live-probe":
        from nba.ingest.remote import live_probe
        print("\n".join(live_probe.run()))
        return
    if args.task == "officials":
        from nba.ingest.remote import officials
        log = officials.run(seasons)
        from nba.config import path
        (path("external") / "fetch_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
        print("\n".join(log))
        return
    if args.task.startswith("injuries"):
        from nba.ingest.remote import injuries
        step = args.task.split("-", 1)[1] if "-" in args.task else "all"
        log = injuries.run(seasons, step)
        from nba.config import path
        (path("external") / "fetch_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
        print("\n".join(log))
        return
    log = []
    if "probe" in tasks:
        from nba.ingest.remote import probe
        probe.run()
        log.append("probe: data/external/probe.json")
    if "espn" in tasks:
        from nba.ingest.remote import espn
        log += espn.run(seasons, with_odds=not args.no_odds)
    if "bref" in tasks:
        from nba.ingest.remote import bref
        # anche la stagione prima della prima richiesta: serve come prior "stagione precedente"
        log += bref.run(list(range(min(seasons) - 1, max(seasons) + 1)))
    from nba.config import path
    (path("external") / "fetch_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


def main(argv=None):
    p = argparse.ArgumentParser(prog="nba")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("ingest", help="scarica e costruisce partite, stint e statistiche per giocatore")
    pi.add_argument("--season", nargs="*", help="es. 2025-26 (più stagioni separate da spazio)")
    pi.add_argument("--all", action="store_true", help="tutte le stagioni di sviluppo e test")
    pi.set_defaults(func=cmd_ingest)
    pq = sub.add_parser("qc", help="controlli di qualità sui dati elaborati")
    pq.set_defaults(func=cmd_qc)
    pr = sub.add_parser("fetch-remote", help="quote e calendario ESPN, BPM Basketball-Reference, prova delle fonti")
    pr.add_argument("--task", choices=["probe", "espn", "bref", "all", "injuries-index", "injuries-fetch", "injuries", "officials"],
                    default="all")
    pr.add_argument("--seasons", default="2014-2026", help="es. 2014-2026 oppure 2018,2025")
    pr.add_argument("--no-odds", action="store_true", help="solo calendario e risultati ESPN, senza quote")
    pr.set_defaults(func=cmd_fetch_remote)
    pb = sub.add_parser("backtest", help="backtest walk-forward (fase 2: baseline della pagina)")
    pb.add_argument("--model", default="baseline", choices=["baseline"])
    pb.add_argument("--retune", action="store_true", help="ritara il baseline sulle stagioni di sviluppo e rifà il backtest")
    pb.add_argument("--seasons", default="2014-2025")
    pb.set_defaults(func=cmd_backtest)
    prp = sub.add_parser("report", help="tabelle di confronto con il mercato (reports/)")
    prp.add_argument("--fase", type=int, default=5, choices=[2, 4, 5],
                     help="2: baseline della pagina; 4: contesto e totali; 5: ensemble e test (la fase 3 si rifà con evaluate.phase3)")
    prp.add_argument("--solo-sviluppo", action="store_true", help="fase 5: solo le stagioni di sviluppo, senza il test")
    prp.set_defaults(func=cmd_report)
    sp = sub.add_parser("predict", help="disponibile in fase 6")
    sp.set_defaults(func=lambda a: sys.exit("'predict' arriva in fase 6 (pipeline dal vivo)"))
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
