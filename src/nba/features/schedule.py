"""Calendario per squadra: giorni di riposo, back-to-back, 3 partite in 4 notti, distanza percorsa, fusi attraversati.

Usa solo date e sedi delle partite, note in anticipo (il calendario è pubblicato prima della stagione).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

from nba.config import ROOT


def arenas() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "external" / "arenas.csv")


BUBBLE = {"lat": 28.337, "lon": -81.556, "tz": "America/New_York"}   # Walt Disney World, luglio-agosto 2020
# Sedi neutre fuori dalle città NBA (dati ESPN: Messico, Europa, finali di Coppa a Las Vegas)
NEUTRAL_CITIES = {
    "Mexico City": (19.404, -99.097, "America/Mexico_City"), "Las Vegas": (36.103, -115.178, "America/Los_Angeles"),
    "London": (51.503, 0.003, "Europe/London"), "Paris": (48.838, 2.378, "Europe/Paris"),
    "Berlin": (52.507, 13.444, "Europe/Berlin"),
}


def arena_for(a: pd.DataFrame, team: str, season: int) -> pd.Series:
    r = a[(a.team == team) & (a.from_season <= season) & (a.to_season >= season)]
    return r.assign(span=r.to_season - r.from_season).sort_values("span").iloc[0]   # la sede più specifica


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2 - lon1)
    h = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(h))


def utc_offset_h(tz: str, date: str) -> float:
    d = pd.Timestamp(date).to_pydatetime().replace(hour=20, tzinfo=ZoneInfo(tz))
    return d.utcoffset().total_seconds() / 3600


def team_schedule(games: pd.DataFrame) -> pd.DataFrame:
    """Una riga per squadra e partita, con le variabili di calendario prima della partita."""
    a = arenas()
    rows = []
    for _, g in games.iterrows():
        host = arena_for(a, g["home"], g["season"])
        lat, lon, tz = host["lat"], host["lon"], host["tz"]
        neutral = bool(g.get("neutral")) if pd.notna(g.get("neutral", np.nan)) else False
        if g["season"] == 2019 and str(g["date"]) >= "2020-07-30":       # "bolla" di Orlando: campo neutro
            lat, lon, tz, neutral = BUBBLE["lat"], BUBBLE["lon"], BUBBLE["tz"], True
        elif neutral:
            city = g.get("venue_city")
            if city in NEUTRAL_CITIES:
                lat, lon, tz = NEUTRAL_CITIES[city]
            else:   # campo neutro in un'altra città NBA: uso l'arena di quella città
                m = a[a.city == city]
                if len(m):
                    lat, lon, tz = m.iloc[-1]["lat"], m.iloc[-1]["lon"], m.iloc[-1]["tz"]
        for side in ("home", "away"):
            rows.append({"game_id": g["game_id"], "season": g["season"], "date": g["date"], "team": g[side],
                         "opp": g["away" if side == "home" else "home"], "is_home": side == "home",
                         "neutral": neutral, "lat": lat, "lon": lon, "tz": tz})
    s = pd.DataFrame(rows).dropna(subset=["date"]).sort_values(["team", "date", "game_id"])
    s["d"] = pd.to_datetime(s["date"])
    s["utc_off"] = [utc_offset_h(tz, d) for tz, d in zip(s["tz"], s["date"])]
    grp = s.groupby(["season", "team"])
    s["rest_days"] = (s["d"] - grp["d"].shift(1)).dt.days - 1          # 0 = back-to-back
    s["b2b"] = s["rest_days"] == 0
    s["games_last4"] = grp["d"].transform(lambda x: x.apply(lambda d: ((x >= d - pd.Timedelta(days=3)) & (x <= d)).sum()))
    s["three_in_four"] = s["games_last4"] >= 3
    plat, plon = grp["lat"].shift(1), grp["lon"].shift(1)
    s["travel_km"] = np.where(plat.isna(), 0.0, haversine_km(plat, plon, s["lat"], s["lon"]))
    s["tz_shift_h"] = (s["utc_off"] - grp["utc_off"].shift(1)).fillna(0)
    s["first_game"] = plat.isna()
    return s.drop(columns=["d"])
