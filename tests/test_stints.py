"""Test della ricostruzione dei quintetti su una partita sintetica."""
import pandas as pd

from nba.ingest.stints import build_game


def ev(rows):
    df = pd.DataFrame(rows, columns=["period", "sec_left", "ord", "team", "player", "kind", "is3", "presence"])
    df["game_id"] = "0029900001"
    df["side"] = ""
    return df


def test_one_period_with_sub_and_silent_player():
    H = [1, 2, 3, 4, 5]
    A = [11, 12, 13, 14, 15]
    rows = [(1, 720, 0, "", 0, "PSTART", False, False)]
    k = 1
    for p in H:      # tutti i giocatori di casa compaiono
        rows.append((1, 700, k, "HHH", p, "FGX", False, True)); k += 1
    for p in A[:4]:  # il 15 non fa nulla: deve risultare titolare perché esce con una sostituzione
        rows.append((1, 690, k, "AAA", p, "DREB", False, True)); k += 1
    rows.append((1, 600, k, "HHH", 1, "FGM", True, True)); k += 1          # 3 punti casa
    rows.append((1, 500, k, "AAA", 15, "SUBOUT", False, False)); k += 1
    rows.append((1, 500, k, "AAA", 16, "SUBIN", False, False)); k += 1
    rows.append((1, 400, k, "AAA", 16, "FGM", False, True)); k += 1        # 2 punti trasferta
    rows.append((1, 0, k, "", 0, "PEND", False, False))
    stints, issues, pstats, psec = build_game(ev(rows), "0029900001", "HHH", "AAA")
    assert not issues
    assert len(stints) == 2
    assert stints[0]["away_ids"] == (11, 12, 13, 14, 15) and stints[1]["away_ids"] == (11, 12, 13, 14, 16)
    assert stints[0]["hpts"] == 3 and stints[1]["apts"] == 2
    assert psec[("AAA", 15)] == 220 and psec[("AAA", 16)] == 500 and psec[("HHH", 1)] == 720
    assert sum(v for (t, _), v in psec.items() if t == "AAA") == 5 * 720


def test_out_of_order_sub_does_not_create_extra_starter():
    # la fonte registra un tiro del 6 prima della sua entrata, allo stesso istante: non è un titolare
    rows = [(1, 720, 0, "", 0, "PSTART", False, False)]
    k = 1
    for p in [1, 2, 3, 4, 5]:
        rows.append((1, 710, k, "HHH", p, "FGX", False, True)); k += 1
    for p in [11, 12, 13, 14, 15]:
        rows.append((1, 705, k, "AAA", p, "DREB", False, True)); k += 1
    rows.append((1, 300, k, "HHH", 6, "FTM", False, True)); k += 1
    rows.append((1, 300, k, "HHH", 5, "SUBOUT", False, False)); k += 1
    rows.append((1, 300, k, "HHH", 6, "SUBIN", False, False)); k += 1
    rows.append((1, 0, k, "", 0, "PEND", False, False))
    stints, issues, _, psec = build_game(ev(rows), "0029900001", "HHH", "AAA")
    assert stints[0]["home_ids"] == (1, 2, 3, 4, 5)
    assert sum(v for (t, _), v in psec.items() if t == "HHH") == 5 * 720
