#!/usr/bin/env python3
"""Stampa le operazioni di predictions/pagina_sync.json per l'attività di Claude «Sincronizzazione NBA».

Uso: python3 ops_pagina.py s.json            -> riepilogo (generato, numero di operazioni, righe del log)
     python3 ops_pagina.py s.json N          -> operazione N (da 1) come JSON compatto: {"op","path","data"}
Le operazioni vanno copiate nel database della pagina nell'ordine dato, una alla volta.
"""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
ops = d.get("ops") or []
if len(sys.argv) < 3:
    print("generato", d.get("generato"))
    print("operazioni", len(ops))
    for i, o in enumerate(ops, 1):
        print(f"{i} {o['op']} {o['path']} {len(json.dumps(o['data'], ensure_ascii=False))} caratteri")
    for x in d.get("log") or []:
        print("log:", x)
else:
    print(json.dumps(ops[int(sys.argv[2]) - 1], ensure_ascii=False, separators=(",", ":")))
