"""Il baseline Python deve dare gli stessi numeri del JavaScript della pagina (stessi ingressi)."""
import json
import re
import shutil
from pathlib import Path

import pytest

from nba.config import ROOT, path
from tests.equivalence.compare import max_diffs, run_js, run_python

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="serve Node.js")
TOL = 1e-9


def _check(raw, cases):
    d = max_diffs(run_js(raw, cases), run_python(raw, cases))
    assert d["mancanti"] == 0 and d["partite"] > 0
    for k in ("rating", "punti", "prob", "sd", "assenze", "valore_giocatori"):
        assert d[k] < TOL, (k, d[k])


def test_page_data():
    html = (ROOT / "recon" / "page" / "index.html")
    if not html.exists():
        pytest.skip("copia della pagina non presente")
    emb = json.loads(re.search(r"window\.NBA_EMBEDDED = (\{.*?\});?\s*</script>", html.read_text("utf-8"), re.S).group(1))
    raw = {k: emb[k] for k in ("schedule", "results", "extra", "pergame", "advanced", "injuries", "prev") if k in emb}
    sched = [s.split(",") for s in raw["schedule"]]
    cases = [{"today": t, "games": [[d, a, h] for d, a, h in sched if t <= d <= t[:8] + f"{int(t[8:]) + 2:02d}"]}
             for t in ("2026-10-25", "2026-11-12", "2026-11-18", "2026-11-25")]
    _check(raw, cases)


def test_historical_inputs():
    if not (path("processed") / "games_2023.parquet").exists():
        pytest.skip("dati elaborati non presenti")
    from nba.evaluate.history_inputs import SeasonInputs
    si = SeasonInputs(2023)
    for d in ("2023-10-30", "2024-01-15", "2024-04-10"):
        raw, today = si.raw_for_day(d)
        _check(raw, [{"today": d, "games": [[d, r.away, r.home] for r in today.itertuples()]}])
