"""Confronta il baseline Python con il JavaScript originale sugli stessi ingressi."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from nba.models import baseline as B

HERE = Path(__file__).resolve().parent


def run_python(raw: dict, cases: list) -> list:
    out = []
    for c in cases:
        ctx = B.build(raw, today=c["today"])
        preds = []
        for d, a, h in c["games"]:
            g = B.find_game(ctx, d, a, h)
            if g is None:
                preds.append({"d": d, "a": a, "h": h, "missing": True})
                continue
            p, q = B.predict(ctx, g), B.predict(ctx, g, no_inj=True)
            preds.append({"d": d, "a": a, "h": h, "hp": p["hp"], "ap": p["ap"], "sd": p["sd"], "p": p["pHome"],
                          "hpNo": q["hp"], "apNo": q["ap"], "pNo": q["pHome"], "dH": p["adjH"]["delta"], "dA": p["adjA"]["delta"]})
        players = {p.key: {"v": p.value, "f": p.f, "b": p.bpmS} for t in ctx.data.players for p in ctx.data.players[t]}
        out.append({"today": c["today"], "R": {"mu": ctx.R.mu, "H": ctx.R.H, "O": ctx.R.O, "D": ctx.R.D},
                    "preds": preds, "players": players})
    return out


def run_js(raw: dict, cases: list) -> list:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"raw": raw, "cases": cases}, f)
        name = f.name
    res = subprocess.run(["node", str(HERE / "run_js.js"), name], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def max_diffs(js: list, py: list) -> dict:
    d = {"rating": 0.0, "punti": 0.0, "prob": 0.0, "sd": 0.0, "assenze": 0.0, "valore_giocatori": 0.0,
         "partite": 0, "giocatori": 0, "mancanti": 0}
    for a, b in zip(js, py):
        assert a["today"] == b["today"]
        d["rating"] = max(d["rating"], abs(a["R"]["mu"] - b["R"]["mu"]), abs(a["R"]["H"] - b["R"]["H"]),
                          *(abs(a["R"]["O"][t] - b["R"]["O"][t]) for t in B.TEAMS),
                          *(abs(a["R"]["D"][t] - b["R"]["D"][t]) for t in B.TEAMS))
        for x, y in zip(a["preds"], b["preds"]):
            if x.get("missing") or y.get("missing"):
                d["mancanti"] += int(bool(x.get("missing")) != bool(y.get("missing")))
                continue
            d["partite"] += 1
            d["punti"] = max(d["punti"], abs(x["hp"] - y["hp"]), abs(x["ap"] - y["ap"]), abs(x["hpNo"] - y["hpNo"]), abs(x["apNo"] - y["apNo"]))
            d["prob"] = max(d["prob"], abs(x["p"] - y["p"]), abs(x["pNo"] - y["pNo"]))
            d["sd"] = max(d["sd"], abs(x["sd"] - y["sd"]))
            d["assenze"] = max(d["assenze"], abs(x["dH"] - y["dH"]), abs(x["dA"] - y["dA"]))
        keys = set(a["players"]) | set(b["players"])
        d["giocatori"] += len(keys)
        d["mancanti"] += len(set(a["players"]) ^ set(b["players"]))
        for k in set(a["players"]) & set(b["players"]):
            d["valore_giocatori"] = max(d["valore_giocatori"], abs(a["players"][k]["v"] - b["players"][k]["v"]))
    return d
