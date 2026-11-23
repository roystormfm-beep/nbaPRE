"""Richieste HTTP prudenti: intestazioni da browser, ritentativi con attesa crescente, parallelismo limitato."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0 Safari/537.36")
_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"})


def get(url: str, *, tries: int = 4, timeout: float = 30, pause: float = 0.0, headers: dict | None = None,
        ok404: bool = True) -> requests.Response | None:
    """GET con ritentativi. Restituisce None per 404 (se ok404) o dopo l'ultimo errore."""
    for k in range(tries):
        try:
            r = _session.get(url, timeout=timeout, headers=headers)
            if r.status_code == 404 and ok404:
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** k * 2)
                continue
            r.raise_for_status()
            if pause:
                time.sleep(pause)
            return r
        except requests.RequestException:
            time.sleep(2 ** k)
    return None


def get_json(url: str, **kw):
    r = get(url, **kw)
    if r is None:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def pmap(fn, items, workers: int = 4):
    """Applica fn agli elementi in parallelo (pochi thread, per non sovraccaricare il sito)."""
    out = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, it): it for it in items}
        for i, f in enumerate(as_completed(futs)):
            out[futs[f]] = f.result()
            if (i + 1) % 500 == 0:
                print(f"    {i + 1}/{len(items)}", flush=True)
    return out
