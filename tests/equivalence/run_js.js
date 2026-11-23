#!/usr/bin/env node
/* Esegue il modello JavaScript originale (baseline_model.js) su un ingresso JSON e stampa i risultati.
 * Ingresso: { raw: {...dati della pagina...}, cases: [{ today: 'YYYY-MM-DD', games: [[d, a, h], ...] }] }
 * Uscita:   [{ today, R: {mu, H, O, D}, preds: [{d, a, h, hp, ap, sd, p, hpNo, apNo, pNo, dH, dA}], players: {...} }]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const M = require(path.join(__dirname, '..', '..', 'baseline_model.js'));
const inp = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = [];
for (const c of inp.cases) {
  const ctx = M.build(inp.raw, { today: c.today });
  const R = ctx.R;
  const preds = [];
  for (const [d, a, h] of c.games) {
    const g = ctx.data.games.find(x => x.d === d && x.a === M.team(a) && x.h === M.team(h));
    if (!g) { preds.push({ d, a, h, missing: true }); continue; }
    const p = M.predict(ctx, g), q = M.predict(ctx, g, null, { noInj: true });
    preds.push({ d, a, h, hp: p.hp, ap: p.ap, sd: p.sd, p: p.pHome, hpNo: q.hp, apNo: q.ap, pNo: q.pHome,
                 dH: p.adjH.delta, dA: p.adjA.delta });
  }
  const players = {};
  for (const t of Object.keys(ctx.data.players)) for (const p of ctx.data.players[t]) players[p.key] = { v: p.value, f: p.f, b: p.bpmS };
  out.push({ today: c.today, R: { mu: R.mu, H: R.H, O: R.O, D: R.D }, preds, players });
}
process.stdout.write(JSON.stringify(out));
