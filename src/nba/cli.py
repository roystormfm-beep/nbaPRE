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
        print(f"{s}: {r} ({time.time() - t0:.0f}s)", flush=True)


def cmd_qc(args):
    from nba.ingest.qc import run_qc
    run_qc()


def main(argv=None):
    p = argparse.ArgumentParser(prog="nba")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("ingest", help="scarica e costruisce partite, stint e statistiche per giocatore")
    pi.add_argument("--season", nargs="*", help="es. 2025-26 (più stagioni separate da spazio)")
    pi.add_argument("--all", action="store_true", help="tutte le stagioni di sviluppo e test")
    pi.set_defaults(func=cmd_ingest)
    pq = sub.add_parser("qc", help="controlli di qualità sui dati elaborati")
    pq.set_defaults(func=cmd_qc)
    for name in ("backtest", "predict", "report"):
        sp = sub.add_parser(name, help="disponibile nelle fasi successive")
        sp.set_defaults(func=lambda a, n=name: sys.exit(f"'{n}' arriva nelle fasi successive"))
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
