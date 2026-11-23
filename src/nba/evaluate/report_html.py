"""Report HTML della fase 5: un file unico, grafici SVG disegnati qui (nessuna libreria esterna)."""
from __future__ import annotations

import html
import math

import numpy as np

CSS = """
.viz-root{color-scheme:light;--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--good:#006300}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;--surface:#1a1a19;
--page:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--good:#0ca30c}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;--surface:#1a1a19;--page:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;
--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--good:#0ca30c}
*{box-sizing:border-box}body{margin:0}
.viz-root{background:var(--page);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;padding:32px 20px 64px}
.wrap{max-width:980px;margin:0 auto}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:40px 0 6px}h3{font-size:15px;margin:22px 0 6px}
p,li{color:var(--ink2);max-width:760px}.lead{font-size:16px;color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:20px 0}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.tile .k{font-size:13px;color:var(--ink2)}.tile .v{font-size:28px;font-weight:600;font-variant-numeric:tabular-nums}
.tile .s{font-size:13px;color:var(--muted)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;margin:12px 0}
.legend{display:flex;gap:18px;font-size:13px;color:var(--ink2);margin:0 0 6px}
.legend span{display:inline-flex;align-items:center;gap:6px}.key{display:inline-block;width:14px;height:2px}
.keybox{display:inline-block;width:10px;height:10px;border-radius:2px}
svg text{fill:var(--muted);font-size:12px;font-family:inherit}svg .lab{fill:var(--ink2)}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--grid);text-align:right;vertical-align:top}
th:first-child,td:first-child{text-align:left}td.l,th.l{text-align:left}th{color:var(--ink2);font-weight:600}
details summary{cursor:pointer;color:var(--ink2);font-size:13px;margin-top:8px}
.scroll{overflow-x:auto}
#tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--border);
border-radius:8px;padding:8px 10px;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.12);display:none;z-index:9;max-width:280px}
#tip b{font-size:14px}[data-tip]{cursor:default}[data-tip]:hover{opacity:.85}
.note{font-size:13px;color:var(--muted)}td.nw,th.nw{white-space:nowrap}td.w{min-width:320px}
"""

JS = """
(function(){const t=document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(el=>{
 el.addEventListener('pointermove',e=>{t.textContent='';
  el.getAttribute('data-tip').split('|').forEach((line,i)=>{const d=document.createElement('div');
   if(i===0){const b=document.createElement('b');b.textContent=line;d.appendChild(b)}else d.textContent=line;t.appendChild(d)});
  t.style.display='block';const x=Math.min(e.clientX+14,window.innerWidth-290);t.style.left=x+'px';t.style.top=(e.clientY+14)+'px'});
 el.addEventListener('pointerleave',()=>{t.style.display='none'});});})();
"""


def _n(v, d=2):
    return "—" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:.{d}f}".replace(".", ",")


def _e(s):
    return html.escape(str(s), quote=True)


def _ticks(lo, hi, n=5):
    step = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(step))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= step), default=step)
    start = math.ceil(lo / step) * step
    out, v = [], start
    while v <= hi + 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def line_chart(xs_labels, series, y_title, w=900, h=300, ymin=None, ymax=None, fmt=2):
    """series: [(nome, var_colore, valori)]; una riga di hit per ogni x con tutti i valori."""
    L, R, T, B = 52, 80, 14, 46
    allv = [v for _, _, vals in series for v in vals if v is not None]
    lo = ymin if ymin is not None else min(allv)
    hi = ymax if ymax is not None else max(allv)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    n = len(xs_labels)
    X = lambda i: L + (w - L - R) * (i + 0.5) / n
    Y = lambda v: T + (h - T - B) * (1 - (v - lo) / (hi - lo))
    o = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{_e(y_title)}">']
    for tv in _ticks(lo, hi):
        o.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(tv):.1f}" y2="{Y(tv):.1f}" stroke="var(--grid)" stroke-width="1"/>'
                 f'<text x="{L-8}" y="{Y(tv)+4:.1f}" text-anchor="end">{_n(tv, 1)}</text>')
    o.append(f'<line x1="{L}" x2="{w-R}" y1="{h-B}" y2="{h-B}" stroke="var(--axis)"/>')
    every = max(1, n // 12)
    for i, lab in enumerate(xs_labels):
        if i % every == 0:
            o.append(f'<text x="{X(i):.1f}" y="{h-B+18}" text-anchor="middle">{_e(lab)}</text>')
    o.append(f'<text x="{L}" y="{h-6}" class="lab">{_e(y_title)}</text>')
    for name, col, vals in series:
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals) if v is not None)
        o.append(f'<polyline points="{pts}" fill="none" stroke="var({col})" stroke-width="2" stroke-linejoin="round"/>')
        for i, v in enumerate(vals):
            if v is not None:
                o.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4" fill="var({col})" stroke="var(--surface)" stroke-width="2"/>')
        last = max(i for i, v in enumerate(vals) if v is not None)
        o.append(f'<text x="{X(last)+10:.1f}" y="{Y(vals[last])+4:.1f}" class="lab" text-anchor="start">{_e(name)}</text>')
    for i, lab in enumerate(xs_labels):
        tip = "|".join([lab] + [f"{name}: {_n(vals[i], fmt)}" for name, _, vals in series if vals[i] is not None])
        x0 = L + (w - L - R) * i / n
        o.append(f'<rect x="{x0:.1f}" y="{T}" width="{(w-L-R)/n:.1f}" height="{h-T-B}" fill="transparent" data-tip="{_e(tip)}"/>')
    o.append("</svg>")
    return "".join(o)


def bar_chart(labels, vals, los, his, y_title, w=900, h=300, note_idx=None):
    """Barre verticali con intervallo di confidenza; un'unica serie (colore s1)."""
    L, R, T, B = 52, 16, 14, 46
    lo = min(0, min(los)) - 0.05
    hi = max(his) + 0.05
    n = len(labels)
    bw = (w - L - R) / n
    Y = lambda v: T + (h - T - B) * (1 - (v - lo) / (hi - lo))
    o = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{_e(y_title)}">']
    for tv in _ticks(lo, hi):
        o.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(tv):.1f}" y2="{Y(tv):.1f}" stroke="var(--grid)"/>'
                 f'<text x="{L-8}" y="{Y(tv)+4:.1f}" text-anchor="end">{_n(tv, 2)}</text>')
    o.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="var(--axis)"/>')
    for i, (lab, v, a, b) in enumerate(zip(labels, vals, los, his)):
        x = L + bw * i + bw * 0.22
        ww = bw * 0.56
        y0, y1 = sorted((Y(0), Y(v)))
        r = min(4, (y1 - y0) / 2)
        o.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{ww:.1f}" height="{max(y1-y0,1):.1f}" rx="{r:.1f}" fill="var(--s1)"/>')
        cx = x + ww / 2
        o.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{Y(a):.1f}" y2="{Y(b):.1f}" stroke="var(--ink2)" stroke-width="1.5"/>'
                 f'<line x1="{cx-5:.1f}" x2="{cx+5:.1f}" y1="{Y(a):.1f}" y2="{Y(a):.1f}" stroke="var(--ink2)" stroke-width="1.5"/>'
                 f'<line x1="{cx-5:.1f}" x2="{cx+5:.1f}" y1="{Y(b):.1f}" y2="{Y(b):.1f}" stroke="var(--ink2)" stroke-width="1.5"/>')
        o.append(f'<text x="{cx:.1f}" y="{h-B+18}" text-anchor="middle">{_e(lab)}</text>')
        if note_idx is not None and i == note_idx:
            o.append(f'<text x="{cx:.1f}" y="{h-B+34}" text-anchor="middle" class="lab">test</text>')
        o.append(f'<text x="{cx:.1f}" y="{Y(b)-6:.1f}" text-anchor="middle" class="lab">{_n(v, 2)}</text>')
        o.append(f'<rect x="{L+bw*i:.1f}" y="{T}" width="{bw:.1f}" height="{h-T-B}" fill="transparent" '
                 f'data-tip="{_e(f"{lab}|distacco: {_n(v, 3)} punti|IC 95%: {_n(a, 2)} ; {_n(b, 2)}")}"/>')
    o.append(f'<text x="{L}" y="{h-6}" class="lab">{_e(y_title)}</text></svg>')
    return "".join(o)


def hbar_chart(labels, vals, x_title, w=900, fmt=2, ref=None, ref_label=None, dots=False):
    """Righe orizzontali, un'unica serie. Barre che partono da zero; con dots=True punti su un asse non da zero
    (per confrontare errori vicini tra loro). ref = linea di riferimento verticale (es. mercato)."""
    row = 30
    L, R, T, B = 300, 70, 26 if ref is not None else 8, 40
    h = T + B + row * len(labels)
    if dots:
        lo = min(min(vals), ref if ref is not None else min(vals)) - 0.1
        hi = max(max(vals), ref if ref is not None else max(vals)) + 0.1
    else:
        lo, hi = 0.0, max(vals) * 1.08
    X = lambda v: L + (w - L - R) * (v - lo) / (hi - lo)
    o = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{_e(x_title)}">']
    for tv in _ticks(lo, hi, 6):
        o.append(f'<line x1="{X(tv):.1f}" x2="{X(tv):.1f}" y1="{T}" y2="{h-B}" stroke="var(--grid)"/>'
                 f'<text x="{X(tv):.1f}" y="{h-B+16}" text-anchor="middle">{_n(tv, 1)}</text>')
    if ref is not None:
        o.append(f'<line x1="{X(ref):.1f}" x2="{X(ref):.1f}" y1="{T-6}" y2="{h-B}" stroke="var(--s2)" stroke-width="2" stroke-dasharray="4 3"/>'
                 f'<text x="{X(ref):.1f}" y="{T-10}" text-anchor="middle" style="fill:var(--ink2)">{_e(ref_label)} {_n(ref, 2)}</text>')
    for i, (lab, v) in enumerate(zip(labels, vals)):
        y = T + row * i + 6
        cy = y + (row - 12) / 2
        o.append(f'<text x="{L-10}" y="{y+13}" text-anchor="end" class="lab">{_e(lab)}</text>')
        if dots:
            o.append(f'<line x1="{L}" x2="{w-R}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="var(--grid)" stroke-dasharray="2 3"/>'
                     f'<circle cx="{X(v):.1f}" cy="{cy:.1f}" r="5" fill="var(--s1)" stroke="var(--surface)" stroke-width="2"/>')
        elif v > 0:
            o.append(f'<rect x="{X(0):.1f}" y="{y}" width="{X(v)-X(0):.1f}" height="{row-12}" rx="4" fill="var(--s1)"/>')
        o.append(f'<text x="{X(v)+9:.1f}" y="{y+13}" class="lab">{_n(v, fmt)}</text>')
        o.append(f'<rect x="0" y="{y-6}" width="{w}" height="{row}" fill="transparent" data-tip="{_e(f"{_n(v, 3)}|{lab}")}"/>')
    o.append(f'<text x="{L}" y="{h-4}" class="lab">{_e(x_title)}</text></svg>')
    return "".join(o)


def calib_chart(cal, w=460, h=380):
    L, R, T, B = 52, 16, 14, 46
    X = lambda v: L + (w - L - R) * v
    Y = lambda v: T + (h - T - B) * (1 - v)
    o = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Curva di calibrazione">']
    for tv in (0, .2, .4, .6, .8, 1):
        o.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(tv):.1f}" y2="{Y(tv):.1f}" stroke="var(--grid)"/>'
                 f'<text x="{L-8}" y="{Y(tv)+4:.1f}" text-anchor="end">{int(tv*100)}%</text>'
                 f'<text x="{X(tv):.1f}" y="{h-B+18}" text-anchor="middle">{int(tv*100)}%</text>')
    o.append(f'<line x1="{X(0)}" y1="{Y(0)}" x2="{X(1)}" y2="{Y(1)}" stroke="var(--axis)" stroke-dasharray="4 4"/>')
    for name, col in (("modello", "--s1"), ("mercato", "--s2")):
        pts = [c for c in cal if c["serie"] == name]
        o.append('<polyline points="' + " ".join(f"{X(c['p_media']):.1f},{Y(c['vinte']):.1f}" for c in pts) +
                 f'" fill="none" stroke="var({col})" stroke-width="2"/>')
        for c in pts:
            tip = f"{_n(100*c['vinte'],0)}% vinte|{name}: probabilità media {_n(100*c['p_media'],0)}%|{c['partite']} partite"
            o.append(f'<circle cx="{X(c["p_media"]):.1f}" cy="{Y(c["vinte"]):.1f}" r="4.5" fill="var({col})" stroke="var(--surface)" stroke-width="2"/>'
                     f'<circle cx="{X(c["p_media"]):.1f}" cy="{Y(c["vinte"]):.1f}" r="12" fill="transparent" data-tip="{_e(tip)}"/>')
    o.append(f'<text x="{L}" y="{h-6}" class="lab">probabilità di vittoria della squadra di casa → quota di partite vinte</text></svg>')
    return "".join(o)


def table(headers, rows, left_cols=1, wrap_last=False):
    n = len(headers)

    def cls(i):
        c = []
        if i < left_cols or (wrap_last and i == n - 1):
            c.append("l")
        c.append("w" if (wrap_last and i == n - 1) else "nw" if wrap_last else "")
        return " ".join(x for x in c if x)
    th = "".join(f'<th class="{cls(i)}">{_e(h)}</th>' for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f'<td class="{cls(i)}">{_e(c)}</td>' for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _ci(r, k, d=2):
    if k not in r or r[k] is None or not math.isfinite(r[k]):
        return "—"
    return f"{r[k]:+.{d}f} [{r[k+'_lo']:+.{d}f}; {r[k+'_hi']:+.{d}f}]".replace(".", ",")


def write_html(R: dict) -> str:
    T, S = R["test"], R["sviluppo"]
    F = T["metriche"]
    page = next(r for r in T["scarto"] if r["col"] == "m_page_senza")
    tiles = [("Errore medio sullo scarto", _n(F["MAE_scarto_modello"]), f"mercato {_n(F['MAE_scarto_mercato'])}"),
             ("Distacco dal mercato", "+" + _n(F["dMAE"], 2), f"punti di errore in più del mercato (IC 95% {_n(F['dMAE_lo'])} ; {_n(F['dMAE_hi'])})"),
             ("Meglio del modello della pagina", _n(page["vs_finale"], 2), f"punti di errore in meno a partita (IC 95% {_n(page['vs_finale_lo'])} ; {_n(page['vs_finale_hi'])})"),
             ("Errore medio sul totale", _n(F["MAE_totale_modello"]), f"mercato {_n(F['MAE_totale_mercato'])}")]
    o = [f'<!DOCTYPE html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>Modello NBA — backtest della fase 5</title><style>{CSS}</style></head><body><div class="viz-root"><div class="wrap">',
         '<h1>Modello NBA — backtest completo (fase 5)</h1>',
         '<p class="lead">Ogni pronostico usa solo informazioni note prima della palla a due. Scelte e tarature sono state fatte sulle '
         'stagioni 2014-15 → 2024-25; la stagione 2025-26 è stata usata una volta sola, a configurazione congelata. '
         'Il riferimento è la linea di chiusura dei bookmaker. Pronostici a scopo informativo, non consigli di scommessa.</p>',
         '<h2>Stagione di test 2025-26</h2><div class="tiles">']
    for k, v, s in tiles:
        o.append(f'<div class="tile"><div class="k">{_e(k)}</div><div class="v">{_e(v)}</div><div class="s">{_e(s)}</div></div>')
    o.append("</div>")
    o.append(f'<p>Il distacco dal mercato è in punti a partita: positivo significa che il mercato sbaglia meno. '
             f'{F["partite"]} partite con injury report e linea di chiusura.</p>')

    # distacco per stagione
    ps = S["per_stagione"] + T["per_stagione"]
    o.append('<h2>Distacco dal mercato, stagione per stagione</h2>'
             '<p>Errore medio del modello meno errore medio della linea di chiusura, con intervallo di confidenza al 95%. '
             'Il modello resta dietro al mercato in tutte le stagioni, di circa un decimo e mezzo di punto.</p><div class="card">')
    o.append(bar_chart([r["stagione"] for r in ps], [r["dMAE"] for r in ps], [r["dMAE_lo"] for r in ps], [r["dMAE_hi"] for r in ps],
                       "punti di errore in più rispetto al mercato", note_idx=len(ps) - 1))
    o.append("<details><summary>Tabella</summary>" + table(
        ["Stagione", "Partite", "Errore modello", "Errore mercato", "Distacco [IC 95%]", "Totale modello", "Totale mercato"],
        [[r["stagione"], r["partite"], _n(r["MAE"]), _n(r["MAE_mercato"]), _ci(r, "dMAE"), _n(r["MAE_totale"]), _n(r["MAE_totale_mercato"])] for r in ps])
             + "</details></div>")

    # per mese (test)
    pm = [r for r in T["per_mese"] if r["partite"] >= 30]
    o.append('<h2>Errore medio per mese (2025-26)</h2><div class="card"><div class="legend">'
             '<span><i class="key" style="background:var(--s1)"></i>Modello</span><span><i class="key" style="background:var(--s2)"></i>Mercato</span></div>')
    o.append(line_chart([r["mese"] for r in pm], [("Modello", "--s1", [r["MAE"] for r in pm]), ("Mercato", "--s2", [r["MAE_mercato"] for r in pm])],
                        "errore medio sullo scarto (punti)"))
    o.append("<details><summary>Tabella</summary>" + table(["Mese", "Partite", "Modello", "Mercato", "Totale modello", "Totale mercato"],
             [[r["mese"], r["partite"], _n(r["MAE"]), _n(r["MAE_mercato"]), _n(r["MAE_totale"]), _n(r["MAE_totale_mercato"])] for r in pm]) + "</details></div>")

    # calibrazione
    o.append('<h2>Calibrazione delle probabilità (2025-26)</h2><p>Se il modello dice 70%, la squadra di casa dovrebbe vincere 7 volte su 10: '
             'i punti dovrebbero stare sulla diagonale tratteggiata. Fasce di 10 punti percentuali con almeno 15 partite.</p>'
             '<div class="card" style="max-width:520px"><div class="legend"><span><i class="key" style="background:var(--s1)"></i>Modello</span>'
             '<span><i class="key" style="background:var(--s2)"></i>Mercato</span></div>')
    o.append(calib_chart(T["calibrazione"]))
    o.append(f'<p class="note">ECE (scarto medio dalla diagonale): modello {_n(F["ECE_modello"], 3)}, mercato {_n(F["ECE_mercato"], 3)}. '
             f'Brier: {_n(F["Brier_modello"], 4)} contro {_n(F["Brier_mercato"], 4)}.</p></div>')

    # componenti
    comp = [r for r in T["scarto"] if r["col"] != "mercato"]
    comp = sorted(comp, key=lambda r: r["MAE"])
    mk = next(r for r in T["scarto"] if r["col"] == "mercato")["MAE"]
    o.append('<h2>Importanza delle componenti</h2><p>Errore medio sullo scarto di ogni componente da solo e delle versioni '
             'intermedie del modello, sulla stagione di test. La linea tratteggiata è il mercato.</p><div class="card">')
    o.append(hbar_chart([r["modello"] for r in comp], [r["MAE"] for r in comp], "errore medio sullo scarto (punti), 2025-26",
                        ref=mk, ref_label="mercato", dots=True))
    o.append("<details><summary>Tabella con intervalli di confidenza</summary>" + table(
        ["Modello", "Errore medio", "vs mercato [IC 95%]", "vs ensemble finale [IC 95%]"],
        [[r["modello"], _n(r["MAE"], 3), _ci(r, "vs_mercato", 3), _ci(r, "vs_finale", 3)] for r in comp]) + "</details></div>")
    W = R["pesi"].get("2025-26", {})
    wl = [(k, v) for k, v in W.items() if k != "costante"]
    wl.sort(key=lambda kv: -kv[1])
    o.append('<h3>Pesi dell\'ensemble per il 2025-26 (stimati sulle stagioni 2018-19 → 2024-25)</h3><div class="card">')
    o.append(hbar_chart([k for k, _ in wl], [v for _, v in wl], "peso nella media", fmt=2))
    o.append('<p class="note">Elo e rating di squadra prendono peso zero: tutto quello che sanno è già nel modello giocatori e nel baseline.</p></div>')

    # totali
    o.append('<h2>Totale dei punti (2025-26)</h2>' + '<div class="card">' + table(
        ["Modello", "Errore medio", "vs mercato [IC 95%]", "vs finale [IC 95%]"],
        [[r["modello"], _n(r["MAE"], 3), _ci(r, "vs_mercato", 3), _ci(r, "vs_finale", 3)] for r in T["totale"]]) + "</div>")

    # mercato
    o.append('<h2>Il modello e il movimento della linea</h2><p>Modello separato da quello puro: parte dalla linea d\'apertura e '
             'prova a prevedere dove andrà la chiusura. CLV = punti di cui la linea si è poi mossa a favore del lato scelto all\'apertura.</p><div class="card">')
    rows = []
    for key, lab in (("mercato_sviluppo", "sviluppo"), ("mercato_test", "test 2025-26")):
        for r in R.get(key, []):
            rows.append([f"{lab}: {r['informazione']}", r["partite"], _n(r["corr"]), f"{_n(100*r['direzione'],1)}% su {r['direzione_partite']}",
                         _ci(r, "CLV"), f"{_ci(r, 'CLV_forte')} su {r['CLV_forte_partite']}"])
    o.append(table(["Informazione", "Partite", "Correlazione col movimento", "Direzione giusta", "CLV medio [IC 95%]", "CLV con disaccordo ≥ 3"], rows) + "</div>")

    # peggiori
    o.append('<h2>Le 50 partite peggiori del test</h2><p>Motivi calcolati a partita finita. TIRO3 e LIBERI: punti in più o in meno '
             'rispetto alla media della lega; ASSENZA: giocatori attesi in campo che non hanno giocato; RIENTRO: giocatori non attesi che hanno giocato '
             'almeno 20 minuti; SENSO_UNICO: scarto di 25 o più; MERCATO: il mercato la vedeva diversamente ed era più vicino.</p><div class="card">')
    o.append(table(["Data", "Partita", "Risultato", "Scarto", "Pronostico", "Mercato", "Errore", "Motivi"],
                   [[r["data"], r["partita"], r["risultato"], f"{r['scarto_vero']:+d}", f"{r['pronostico']:+.1f}",
                     "" if r["mercato"] is None else f"{r['mercato']:+.1f}", f"{r['errore']:+.1f}", r["motivi"]] for r in R["peggiori"]],
                   left_cols=3, wrap_last=True) + "</div>")
    o.append(f'<div id="tip" role="tooltip"></div></div></div><script>{JS}</script></body></html>')
    return "".join(o)
