#!/usr/bin/env python3
"""Prepara la copia di predictions/pagina_sync.json nel database della pagina (attività «Sincronizzazione NBA»).

Uso:
  python3 ops_pagina.py s.json                      riepilogo: generato, operazioni, log del workflow
  python3 ops_pagina.py s.json --batch LIST OUT     scrive i dati di ogni operazione in OUT/N.json e stampa l'elenco
                                                    "writes" per ArtifactData action "batch". LIST = file di testo con il
                                                    risultato di ArtifactData list sulla collezione nba (serve per le
                                                    versioni dei documenti esistenti, da passare come if_version)
"merge" diventa "update" (fonde i campi, le partite già presenti restano); su un documento che non esiste
ancora diventa "set". nba/meta resta l'ultima operazione.
"""
import json
import os
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
ops = d.get("ops") or []
if "--batch" not in sys.argv:
    print("generato", d.get("generato"))
    print("operazioni", len(ops))
    for i, o in enumerate(ops, 1):
        print(f"{i} {o['op']} {o['path']} {len(json.dumps(o['data'], ensure_ascii=False))} caratteri")
    for x in d.get("log") or []:
        print("log:", x)
    sys.exit(0)

k = sys.argv.index("--batch")
listing, out = sys.argv[k + 1], sys.argv[k + 2]
os.makedirs(out, exist_ok=True)
# versioni dei documenti esistenti, dal testo del risultato di ArtifactData list (righe come
#   - "advanced"  14390 bytes  version 7  "/tmp/...")
import re
versions = {m.group(1): int(m.group(2)) for m in re.finditer(r'"([A-Za-z0-9_.:@+~-]+)"\s+\d+\s+bytes\s+version\s+(\d+)', open(listing, encoding="utf-8").read())}
writes = []
for i, o in enumerate(ops, 1):
    coll, doc = o["path"].rsplit("/", 1)
    fp = os.path.abspath(os.path.join(out, f"{i}.json"))
    json.dump(o["data"], open(fp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    exists = doc in versions
    w = {"op": ("update" if o["op"] == "merge" and exists else "set"), "collection": coll, "doc_id": doc, "file_path": fp}
    if exists:
        w["if_version"] = versions[doc]
    writes.append(w)
if not versions:
    print("ATTENZIONE: nessuna versione letta da " + listing + ": tutte le scritture sono set senza if_version", file=sys.stderr)
print(json.dumps(writes, ensure_ascii=False))
