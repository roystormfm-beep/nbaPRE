"""Lettore degli injury report: sui PDF di esempio (2018-2026) ogni stato letto deve corrispondere a una riga."""
import glob
import re

import pytest

from nba.config import ROOT
from nba.ingest.injury_pdf import name_key, parse_pdf

SAMPLES = sorted(glob.glob(str(ROOT / "data" / "external" / "injury" / "samples" / "*.pdf")))


@pytest.mark.skipif(not SAMPLES, reason="nessun PDF di esempio")
@pytest.mark.parametrize("f", SAMPLES)
def test_rows_match_statuses(f):
    import pdfplumber
    df = parse_pdf(open(f, "rb").read())
    d = df[df["player_name"] != ""]
    with pdfplumber.open(f) as pdf:
        raw = " ".join(p.extract_text() for p in pdf.pages)
    if "Previous Status" not in raw:          # nel formato vecchio il testo contiene anche lo stato precedente
        n = len(re.findall(r"\b(Out|Questionable|Doubtful|Probable|Available)\b", raw))
        assert len(d) == n
    assert d["team"].notna().all()
    assert (d["status"].str.split().str.len() == 1).all()
    assert d["matchup"].str.fullmatch(r"[A-Z]{2,3}@[A-Z]{2,3}").all()


def test_name_key():
    assert name_key("Michael PorterJr.") == name_key("Michael Porter Jr.") == "michaelporter"
    assert name_key("Nikola Jokić") == name_key("Nikola Jokic")
    assert name_key("Glenn Robinson III") == "glennrobinson"
