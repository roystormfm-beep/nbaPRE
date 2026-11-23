#!/usr/bin/env node
/*
 * Pronostici NBA 2026/27 — congelamento dei pronostici prima della palla a due.
 *
 * Esegue lo stesso modello della pagina (estratto da index.html) sui dati più recenti
 * e scrive, per ogni partita non ancora iniziata, il pronostico e la linea di mercato.
 *
 * Uso:
 *   node freeze.js --html index.html --dir data --now 2026-11-19T23:20:00Z --out out.json [--backfill]
 *
 * File nella cartella --dir (tutti testo, una riga per record; mancanti = si usa la copia nella pagina):
 *   games.txt     YYYY-MM-DD|AWAY|HOME|START_UTC        partite da congelare (data USA, ora d'inizio UTC ISO)   OBBLIGATORIO
 *   results.txt   YYYY-MM-DD|AWAY|PTS|HOME|PTS|OT        risultati dal database (nba/results)
 *   pergame.csv   Player,Team,G,MP,FGA,FTA,3P,TRB,AST,STL,BLK,TOV,PTS   (header + righe; bastano le squadre in campo)
 *   advanced.csv  Player,Team,G,MP,USG,BPM                              (header + righe; bastano le squadre in campo)
 *   injuries.txt  TEAM|Player|Status|YYYY-MM-DD|nota     (report completo o solo squadre in campo)
 *   extra.txt     YYYY-MM-DD|AWAY|HOME                   partite aggiunte al calendario (nba/extra)
 *   odds.txt      YYYY-MM-DD|AWAY|HOME|SPREAD_HOME|ML_AWAY|ML_HOME|TOTAL|FONTE
 *                 SPREAD_HOME = spread della squadra di casa (-7.5 se è favorita di 7,5; +3.5 se sfavorita)
 *
 * Uscita (--out): { month docs da scrivere con db_write merge, riepilogo, avvisi }.
 * Codici di uscita: 0 ok, 2 dati mancanti o incoerenti (vedi "errors").
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  if (i < 0) return def;
  const v = process.argv[i + 1];
  return v && !v.startsWith('--') ? v : true;
}
const HTML = arg('html', 'index.html');
const DIR = arg('dir', 'data');
const NOW = arg('now', new Date().toISOString());
const OUT = arg('out', 'out.json');
const BACKFILL = !!arg('backfill', false);
const SRC = arg('src', BACKFILL ? 'ricostruito' : 'auto');

const errors = [], warnings = [];
function readLines(f) {
  const p = path.join(DIR, f);
  if (!fs.existsSync(p)) return null;
  return fs.readFileSync(p, 'utf8').split(/\r?\n/).map(s => s.trim()).filter(s => s && !s.startsWith('#'));
}

/* ---------- 1. modello e dati incorporati dalla pagina ---------- */
const html = fs.readFileSync(HTML, 'utf8');
const em = html.match(/window\.NBA_EMBEDDED = (\{.*?\});?\s*<\/script>/s);
if (!em) { console.error('NBA_EMBEDDED non trovato in ' + HTML); process.exit(3); }
const EMB = JSON.parse(em[1]);
const ms = html.match(/<script>(\/\* Modello predittivo[\s\S]*?)<\/script>/);
if (!ms) { console.error('Script del modello non trovato in ' + HTML); process.exit(3); }
const sandbox = { module: { exports: {} }, console, Math, Date, Intl, Float64Array, Int32Array, Map, Set, Array, Object, JSON, String, Number, isFinite, parseFloat };
sandbox.globalThis = sandbox;
vm.runInNewContext(ms[1], sandbox);
const M = sandbox.module.exports;
if (!M || typeof M.build !== 'function') { console.error('Modello non caricato'); process.exit(3); }
const MODEL_VER = crypto.createHash('sha256').update(ms[1]).digest('hex').slice(0, 8);

/* ---------- 2. dati freschi ---------- */
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
function etDate(iso) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(iso));
}
const games = (readLines('games.txt') || []).map((l, i) => {
  const p = l.split('|').map(s => s.trim());
  const g = { d: p[0], a: M.team(p[1]), h: M.team(p[2]), tip: p[3] || null };
  if (!DATE_RE.test(g.d) || !M.TEAMS[g.a] || !M.TEAMS[g.h] || g.a === g.h) { errors.push('games.txt riga ' + (i + 1) + ' non valida: ' + l); return null; }
  if (g.tip && isNaN(Date.parse(g.tip))) { errors.push('games.txt riga ' + (i + 1) + ': ora non valida ' + g.tip); return null; }
  if (g.tip && etDate(g.tip) !== g.d) warnings.push(g.a + '@' + g.h + ': la data ' + g.d + ' non corrisponde all\'ora d\'inizio (data USA ' + etDate(g.tip) + ')');
  return g;
}).filter(Boolean);
if (!games.length) errors.push('games.txt vuoto o mancante: nessuna partita da congelare');

const raw = JSON.parse(JSON.stringify(EMB));
const used = { results: 'pagina', pergame: 'pagina', advanced: 'pagina', injuries: 'pagina', extra: 'pagina' };

const res = readLines('results.txt');
if (res) {
  const map = new Map();
  raw.results.forEach(r => { const p = r.split('|'); map.set(p[0] + '|' + M.team(p[1]) + '|' + M.team(p[3]), r); });
  res.forEach((r, i) => {
    const p = r.split(/[|,]/).map(s => s.trim());
    if (p.length < 5 || !DATE_RE.test(p[0]) || !M.TEAMS[M.team(p[1])] || !M.TEAMS[M.team(p[3])] || !/^\d+$/.test(p[2]) || !/^\d+$/.test(p[4])) { errors.push('results.txt riga ' + (i + 1) + ' non valida: ' + r); return; }
    map.set(p[0] + '|' + M.team(p[1]) + '|' + M.team(p[3]), p.slice(0, 6).join('|'));
  });
  raw.results = [...map.values()];
  used.results = 'database (' + res.length + ' righe)';
}

const playing = new Set(); games.forEach(g => { playing.add(g.h); playing.add(g.a); });
function mergeCsv(kind, header) {
  const lines = readLines(kind + '.csv');
  if (!lines) { warnings.push(kind + '.csv mancante: uso la copia nella pagina (' + EMB.asOf[kind] + ')'); return; }
  const head = lines[0].split(',').map(s => s.trim()).join(',');
  if (head !== header) { errors.push(kind + '.csv: intestazione attesa "' + header + '", trovata "' + lines[0] + '"'); return; }
  const rows = lines.slice(1), teams = new Map();
  rows.forEach((r, i) => {
    const p = r.split(',');
    if (p.length !== header.split(',').length) { errors.push(kind + '.csv riga ' + (i + 2) + ': numero di colonne errato: ' + r); return; }
    const t = M.team(p[1]);
    if (!M.TEAMS[t]) { errors.push(kind + '.csv riga ' + (i + 2) + ': squadra non valida ' + p[1]); return; }
    for (let k = 2; k < p.length; k++) if (p[k].trim() !== '' && !isFinite(parseFloat(p[k]))) { errors.push(kind + '.csv riga ' + (i + 2) + ': valore non numerico "' + p[k] + '"'); return; }
    teams.set(t, (teams.get(t) || 0) + 1);
  });
  playing.forEach(t => { if ((teams.get(t) || 0) < 7) errors.push(kind + '.csv: solo ' + (teams.get(t) || 0) + ' giocatori per ' + t + ' (ne servono almeno 7)'); });
  // sostituisco solo le squadre presenti nel file; le altre restano quelle incorporate nella pagina
  const keep = EMB[kind].slice(1).filter(r => !teams.has(M.team(r.split(',')[1])));
  raw[kind] = [EMB[kind][0]].concat(keep, rows);
  used[kind] = 'database (' + teams.size + ' squadre)';
}
mergeCsv('pergame', 'Player,Team,G,MP,FGA,FTA,3P,TRB,AST,STL,BLK,TOV,PTS');
mergeCsv('advanced', 'Player,Team,G,MP,USG,BPM');

const inj = readLines('injuries.txt');
if (inj) {
  const rows = [], teams = new Set();
  inj.forEach((l, i) => {
    const p = l.split('|');
    if (/^team$/i.test(p[0])) return;
    const t = M.team(p[0]);
    if (p.length < 3 || !M.TEAMS[t]) { errors.push('injuries.txt riga ' + (i + 1) + ' non valida: ' + l); return; }
    if (p[3] && p[3].trim() && !DATE_RE.test(p[3].trim())) warnings.push('injuries.txt riga ' + (i + 1) + ': data di rientro non valida "' + p[3] + '"');
    rows.push(l); teams.add(t);
  });
  // se il file copre tutte le squadre lo uso così com'è; altrimenti sostituisco solo le squadre presenti
  if (teams.size >= 20) raw.injuries = rows;
  else raw.injuries = EMB.injuries.filter(r => { const t = M.team(r.split('|')[0]); return !playing.has(t) && !teams.has(t); }).concat(rows);
  if (teams.size < 20) playing.forEach(t => { if (!teams.has(t)) warnings.push('injuries.txt: nessuna riga per ' + t + ' (considero la squadra senza assenze)'); });
  used.injuries = 'file (' + rows.length + ' righe, ' + teams.size + ' squadre)';
} else warnings.push('injuries.txt mancante: uso il report incorporato nella pagina (' + EMB.asOf.injuries + ')');

const extra = readLines('extra.txt');
if (extra) { raw.extra = extra; used.extra = 'database (' + extra.length + ')'; }
// le partite da congelare che non sono nel calendario vengono aggiunte come "extra"
games.forEach(g => {
  const inSched = raw.schedule.some(s => { const p = s.split(','); return p[0] === g.d && M.team(p[1]) === g.a && M.team(p[2]) === g.h; })
    || (raw.extra || []).some(s => { const p = s.split(/[|,]/); return p[0] === g.d && M.team(p[1]) === g.a && M.team(p[2]) === g.h; });
  if (!inSched) { raw.extra = (raw.extra || []).concat([g.d + '|' + g.a + '|' + g.h]); warnings.push(g.a + '@' + g.h + ' del ' + g.d + ' non era nel calendario: aggiunta'); }
});

/* ---------- 3. quote ---------- */
function mlProb(ml) { ml = Number(ml); if (!isFinite(ml) || ml === 0) return null; return ml < 0 ? -ml / (-ml + 100) : 100 / (ml + 100); }
const odds = new Map();
(readLines('odds.txt') || []).forEach((l, i) => {
  const p = l.split('|').map(s => s.trim());
  const d = p[0], a = M.team(p[1]), h = M.team(p[2]);
  if (!DATE_RE.test(d) || !M.TEAMS[a] || !M.TEAMS[h]) { errors.push('odds.txt riga ' + (i + 1) + ' non valida: ' + l); return; }
  const num = s => (s == null || s === '' || /^n\/?a$/i.test(s)) ? null : (isFinite(parseFloat(String(s).replace(/^PK$/i, '0'))) ? parseFloat(String(s).replace(/^PK$/i, '0')) : NaN);
  const sp = num(p[3]), mla = num(p[4]), mlh = num(p[5]), tot = num(p[6]);
  if ([sp, mla, mlh, tot].some(v => Number.isNaN(v))) { errors.push('odds.txt riga ' + (i + 1) + ': numero non valido: ' + l); return; }
  const mk = { sp, mla, mlh, tot, src: p[7] || '' };
  const qa = mlProb(mla), qh = mlProb(mlh);
  if (qa != null && qh != null) {
    mk.ph = Math.round(qh / (qa + qh) * 1000) / 1000;
    if (qa + qh < 1 || qa + qh > 1.12) warnings.push('odds.txt riga ' + (i + 1) + ': margine del bookmaker anomalo (' + (qa + qh).toFixed(3) + ')');
    if (sp != null && Math.abs(sp) >= 2 && (sp < 0) !== (mk.ph > 0.5)) errors.push('odds.txt riga ' + (i + 1) + ': spread e moneyline indicano favorite diverse (segno dello spread invertito?): ' + l);
  }
  odds.set(d + '|' + a + '|' + h, mk);
});

if (errors.length) { finish(2, []); }

/* ---------- 4. calcolo ---------- */
const byDate = new Map();
games.forEach(g => { if (!byDate.has(g.d)) byDate.set(g.d, []); byDate.get(g.d).push(g); });
const now = Date.parse(NOW);
const rows = [];
for (const [d, list] of byDate) {
  const ctx = M.build(raw, { today: d });
  for (const tg of list) {
    if (!BACKFILL && tg.tip && Date.parse(tg.tip) <= now) { warnings.push(tg.a + '@' + tg.h + ' è già iniziata (' + tg.tip + '): non la congelo'); continue; }
    const g = ctx.data.games.find(x => x.d === d && x.a === tg.a && x.h === tg.h);
    if (!g) { errors.push('Partita ' + tg.a + '@' + tg.h + ' del ' + d + ' non trovata nel calendario del modello'); continue; }
    const pr = M.predict(ctx, g);
    const r1 = v => Math.round(v * 10) / 10;
    const outs = adj => adj.out.slice(0, 4).map(o => o.name + (o.av > 0 ? ' (in dubbio)' : '') + ' ' + r1(o.impact)).join('; ');
    const row = {
      d, a: g.a, h: g.h, tip: tg.tip || null, t: NOW, src: SRC, mv: MODEL_VER,
      ap: r1(pr.ap), hp: r1(pr.hp), m: r1(pr.margin), p: Math.round(pr.pHome * 1000) / 1000, sd: r1(pr.sd),
      b2b: (pr.b2bA ? 'A' : '') + (pr.b2bH ? 'H' : ''), outA: outs(pr.adjA), outH: outs(pr.adjH),
      injAsOf: used.injuries
    };
    const mk = odds.get(d + '|' + g.a + '|' + g.h);
    if (mk) { mk.at = NOW; row.mk = mk; } else warnings.push('Nessuna quota per ' + g.a + '@' + g.h + ' del ' + d);
    rows.push(row);
  }
}
finish(errors.length ? 2 : 0, rows);

function finish(code, rows) {
  const docs = {};
  rows.forEach(r => {
    const doc = 'nba/predlog-' + r.d.slice(0, 7);
    (docs[doc] = docs[doc] || { g: {} }).g[r.d + '_' + r.a + '_' + r.h] = r;
  });
  const summary = rows.map(r => {
    const fav = r.p >= 0.5 ? r.h : r.a, pf = Math.max(r.p, 1 - r.p);
    const mk = r.mk ? ' | mercato ' + (r.mk.sp != null ? r.h + ' ' + (r.mk.sp > 0 ? '+' : '') + r.mk.sp : 'spread n.d.') + (r.mk.ph != null ? ', ' + (r.mk.ph >= 0.5 ? r.h : r.a) + ' ' + Math.round(Math.max(r.mk.ph, 1 - r.mk.ph) * 100) + '%' : '') : ' | mercato n.d.';
    return r.d + ' ' + r.a + '@' + r.h + ': ' + r.a + ' ' + r.ap + ' - ' + r.hp + ' ' + r.h + ' | ' + fav + ' ' + Math.round(pf * 100) + '%' + mk;
  });
  const out = { ok: code === 0, modelVersion: MODEL_VER, now: NOW, used, errors, warnings, summary, docs };
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log(JSON.stringify({ ok: out.ok, modelVersion: MODEL_VER, used, errors, warnings, summary }, null, 1));
  process.exit(code);
}
