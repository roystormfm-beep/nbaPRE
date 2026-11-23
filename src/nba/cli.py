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
    pr.add_argument("--task", choices=["probe", "espn", "bref", "all"], default="all")
    pr.add_argument("--seasons", default="2014-2026", help="es. 2014-2026 oppure 2018,2025")
    pr.add_argument("--no-odds", action="store_true", help="solo calendario e risultati ESPN, senza quote")
    pr.set_defaults(func=cmd_fetch_remote)
    for name in ("backtest", "predict", "report"):
        sp = sub.add_parser(name, help="disponibile nelle fasi successive")
        sp.set_defaults(func=lambda a, n=name: sys.exit(f"'{n}' arriva nelle fasi successive"))
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
