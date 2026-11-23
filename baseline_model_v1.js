/* Modello predittivo NBA 2026/27 — funziona nel browser e in Node. */
(function (root) {
  'use strict';

  const TEAMS = {
    ATL: { n: 'Atlanta Hawks', s: 'Hawks', c: 'E' }, BOS: { n: 'Boston Celtics', s: 'Celtics', c: 'E' },
    BKN: { n: 'Brooklyn Nets', s: 'Nets', c: 'E' }, CHA: { n: 'Charlotte Hornets', s: 'Hornets', c: 'E' },
    CHI: { n: 'Chicago Bulls', s: 'Bulls', c: 'E' }, CLE: { n: 'Cleveland Cavaliers', s: 'Cavaliers', c: 'E' },
    DAL: { n: 'Dallas Mavericks', s: 'Mavericks', c: 'W' }, DEN: { n: 'Denver Nuggets', s: 'Nuggets', c: 'W' },
    DET: { n: 'Detroit Pistons', s: 'Pistons', c: 'E' }, GSW: { n: 'Golden State Warriors', s: 'Warriors', c: 'W' },
    HOU: { n: 'Houston Rockets', s: 'Rockets', c: 'W' }, IND: { n: 'Indiana Pacers', s: 'Pacers', c: 'E' },
    LAC: { n: 'LA Clippers', s: 'Clippers', c: 'W' }, LAL: { n: 'Los Angeles Lakers', s: 'Lakers', c: 'W' },
    MEM: { n: 'Memphis Grizzlies', s: 'Grizzlies', c: 'W' }, MIA: { n: 'Miami Heat', s: 'Heat', c: 'E' },
    MIL: { n: 'Milwaukee Bucks', s: 'Bucks', c: 'E' }, MIN: { n: 'Minnesota Timberwolves', s: 'Timberwolves', c: 'W' },
    NOP: { n: 'New Orleans Pelicans', s: 'Pelicans', c: 'W' }, NYK: { n: 'New York Knicks', s: 'Knicks', c: 'E' },
    OKC: { n: 'Oklahoma City Thunder', s: 'Thunder', c: 'W' }, ORL: { n: 'Orlando Magic', s: 'Magic', c: 'E' },
    PHI: { n: 'Philadelphia 76ers', s: '76ers', c: 'E' }, PHX: { n: 'Phoenix Suns', s: 'Suns', c: 'W' },
    POR: { n: 'Portland Trail Blazers', s: 'Blazers', c: 'W' }, SAC: { n: 'Sacramento Kings', s: 'Kings', c: 'W' },
    SAS: { n: 'San Antonio Spurs', s: 'Spurs', c: 'W' }, TOR: { n: 'Toronto Raptors', s: 'Raptors', c: 'E' },
    UTA: { n: 'Utah Jazz', s: 'Jazz', c: 'W' }, WAS: { n: 'Washington Wizards', s: 'Wizards', c: 'E' }
  };
  const CODES = Object.keys(TEAMS);
  const TIDX = {}; CODES.forEach((c, i) => { TIDX[c] = i; });
  const ALIAS = { BRK: 'BKN', CHO: 'CHA', PHO: 'PHX', NO: 'NOP', NY: 'NYK', SA: 'SAS', GS: 'GSW', UTAH: 'UTA', WSH: 'WAS' };
  const NT = 30;

  const DEFAULTS = {
    lambda: 2,          // ridge sui rating offensivi/difensivi (partite fittizie a media lega)
    halfLife: 60,       // giorni: peso dimezzato per le partite più vecchie
    Hprior: 2.2,        // vantaggio campo a priori
    Hlambda: 40,        // forza del prior sul vantaggio campo
    sigma: 11.5,        // rumore di una singola partita (dev. std. dello scarto, punti)
    kVar: 1,            // peso dell'incertezza a posteriori dei rating
    movCap: 15,         // scarti oltre questa soglia contano a metà (garbage time)
    movK: 0.5,
    b2b: 1.0,           // penalità back-to-back (punti)
    injK: 0.8,          // smorzamento dell'effetto assenze
    repl: -2.0,         // BPM di un sostituto
    bpmPriorMin: 300,   // minuti fittizi con cui il BPM viene riportato verso il prior
    drift: 1.5,         // deriva della forza delle squadre da qui ad aprile (punti, simulazioni)
    sims: 2000
  };
  // Stima del BPM da medie per 36 minuti (regressione sui giocatori 2026/27, R² 0,89)
  const BOX = [-11.117, 1.042, 0.384, 0.877, 1.493, 1.098, -1.649, -0.859, -0.384, 0.474];

  function team(t) { t = String(t || '').trim().toUpperCase(); return ALIAS[t] || t; }
  const DAY0 = Date.UTC(2026, 9, 1);
  const BT_START = '2026-10-28';
  function dayIdx(d) { const p = String(d).slice(0, 10).split('-').map(Number); return Math.round((Date.UTC(p[0], p[1] - 1, p[2]) - DAY0) / 864e5); }
  function idxDate(i) { return new Date(DAY0 + i * 864e5).toISOString().slice(0, 10); }
  function normName(n) {
    return String(n || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
      .replace(/-/g, ' ').replace(/[^a-z ]/g, '').replace(/\b(jr|sr|ii|iii|iv)\b/g, '').replace(/\s+/g, ' ').trim();
  }
  function Phi(x) {
    const z = Math.abs(x) / Math.SQRT2, t = 1 / (1 + 0.3275911 * z);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-z * z);
    return x >= 0 ? (1 + y) / 2 : (1 - y) / 2;
  }
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function num(x) { const v = parseFloat(x); return isFinite(v) ? v : null; }

  /* ---------- Parsing dei dati ---------- */
  function parseData(raw) {
    const games = [], byKey = new Map();
    function addGame(d, a, h) {
      a = team(a); h = team(h);
      if (!TEAMS[a] || !TEAMS[h] || a === h) return null;
      const key = d + '|' + a + '|' + h;
      if (byKey.has(key)) return byKey.get(key);
      const g = { d, di: dayIdx(d), a, h, played: false, as: null, hs: null, ot: '' };
      games.push(g); byKey.set(key, g); return g;
    }
    (raw.schedule || []).forEach(s => { const p = s.split(','); if (p.length >= 3) addGame(p[0], p[1], p[2]); });
    (raw.extra || []).forEach(s => { const p = s.split(/[|,]/); if (p.length >= 3) addGame(p[0], p[1], p[2]); });
    let resultsMatched = 0;
    (raw.results || []).forEach(s => {
      const p = s.split(/[|,]/); if (p.length < 5) return;
      const d = p[0], a = team(p[1]), as = num(p[2]), h = team(p[3]), hs = num(p[4]);
      if (as == null || hs == null) return;
      let g = byKey.get(d + '|' + a + '|' + h);
      if (!g) { // tollera date sfasate di un giorno (UTC vs orario USA)
        const di = dayIdx(d);
        g = games.find(x => x.a === a && x.h === h && Math.abs(x.di - di) <= 1 && !x.played) || null;
      }
      if (!g) g = addGame(d, a, h);
      if (!g) return;
      g.played = true; g.as = as; g.hs = hs; g.ot = (p[5] || '').trim(); resultsMatched++;
    });
    games.sort((x, y) => x.di - y.di || x.h.localeCompare(y.h));

    // Giocatori
    const players = {}; CODES.forEach(c => { players[c] = []; });
    const pIndex = new Map();
    function csvRows(rows) {
      if (!rows || !rows.length) return [];
      const out = []; let header = null;
      rows.forEach(line => {
        const parts = line.split(',');
        if (!header) { if (/^player/i.test(parts[0])) { header = parts.map(h => h.trim()); return; } header = null; }
        if (header) { const o = {}; header.forEach((h, i) => { o[h] = parts[i]; }); out.push(o); }
      });
      return out;
    }
    csvRows(raw.pergame).forEach(r => {
      const t = team(r.Team); if (!TEAMS[t]) return;
      const name = (r.Player || '').trim(); const k = t + '|' + normName(name);
      if (pIndex.has(k)) return;
      const p = {
        name, t, key: k, g: num(r.G) || 0, mpg: num(r.MP) || 0, pts: num(r.PTS) || 0, trb: num(r.TRB) || 0,
        ast: num(r.AST) || 0, fg3: num(r['3P']) || 0, stl: num(r.STL) || 0, blk: num(r.BLK) || 0,
        tov: num(r.TOV) || 0, fga: num(r.FGA) || 0, fta: num(r.FTA) || 0, bpm: null, mptot: null, usg: null, box: true
      };
      players[t].push(p); pIndex.set(k, p);
    });
    csvRows(raw.advanced).forEach(r => {
      const t = team(r.Team); if (!TEAMS[t]) return;
      const name = (r.Player || '').trim(); const k = t + '|' + normName(name);
      let p = pIndex.get(k);
      if (!p) {
        p = { name, t, key: k, g: num(r.G) || 0, mpg: 0, pts: 0, trb: 0, ast: 0, fg3: 0, stl: 0, blk: 0, tov: 0, fga: 0, fta: 0, bpm: null, mptot: null, usg: null, box: false };
        players[t].push(p); pIndex.set(k, p);
      }
      p.bpm = num(r.BPM); p.mptot = num(r.MP); p.usg = num(r.USG);
      if (!p.mpg && p.mptot && p.g) p.mpg = p.mptot / p.g;
    });

    // Infortuni
    const injuries = [];
    (raw.injuries || []).forEach(line => {
      const p = line.split('|'); if (p.length < 3 || /^team$/i.test(p[0])) return;
      const t = team(p[0]); if (!TEAMS[t]) return;
      const ret = (p[3] || '').trim();
      injuries.push({ t, name: p[1].trim(), key: t + '|' + normName(p[1]), status: (p[2] || '').trim(), ret, retIdx: /^\d{4}-\d{2}-\d{2}$/.test(ret) ? dayIdx(ret) : null, note: (p[4] || '').trim() });
    });
    injuries.forEach(inj => {
      let p = pIndex.get(inj.key);
      if (!p) { const nn = inj.key.split('|')[1]; for (const q of pIndex.values()) { if (normName(q.name) === nn) { p = q; break; } } }
      inj.player = p || null; if (p) p.inj = inj;
    });
    return { games, players, injuries, resultsMatched };
  }

  /* ---------- Algebra ---------- */
  function solve(A, b, n) {
    const M = new Float64Array(A), x = new Float64Array(b);
    for (let c = 0; c < n; c++) {
      let piv = c, best = Math.abs(M[c * n + c]);
      for (let r = c + 1; r < n; r++) { const v = Math.abs(M[r * n + c]); if (v > best) { best = v; piv = r; } }
      if (piv !== c) { for (let k = 0; k < n; k++) { const t = M[c * n + k]; M[c * n + k] = M[piv * n + k]; M[piv * n + k] = t; } const t = x[c]; x[c] = x[piv]; x[piv] = t; }
      const d = M[c * n + c] || 1e-12;
      for (let r = c + 1; r < n; r++) {
        const f = M[r * n + c] / d; if (!f) continue;
        for (let k = c; k < n; k++) M[r * n + k] -= f * M[c * n + k];
        x[r] -= f * x[c];
      }
    }
    for (let r = n - 1; r >= 0; r--) {
      let s = x[r]; for (let k = r + 1; k < n; k++) s -= M[r * n + k] * x[k];
      x[r] = s / (M[r * n + r] || 1e-12);
    }
    return x;
  }

  function invert(A, n) {
    const M = new Float64Array(A), I = new Float64Array(n * n);
    for (let i = 0; i < n; i++) I[i * n + i] = 1;
    for (let c = 0; c < n; c++) {
      let piv = c, best = Math.abs(M[c * n + c]);
      for (let r = c + 1; r < n; r++) { const v = Math.abs(M[r * n + c]); if (v > best) { best = v; piv = r; } }
      if (piv !== c) for (let k = 0; k < n; k++) { let t = M[c * n + k]; M[c * n + k] = M[piv * n + k]; M[piv * n + k] = t; t = I[c * n + k]; I[c * n + k] = I[piv * n + k]; I[piv * n + k] = t; }
      const d = M[c * n + c] || 1e-12;
      for (let k = 0; k < n; k++) { M[c * n + k] /= d; I[c * n + k] /= d; }
      for (let r = 0; r < n; r++) {
        if (r === c) continue; const f = M[r * n + c]; if (!f) continue;
        for (let k = 0; k < n; k++) { M[r * n + k] -= f * M[c * n + k]; I[r * n + k] -= f * I[c * n + k]; }
      }
    }
    return I;
  }

  /* ---------- Rating di squadra: ridge su punti fatti/subiti ---------- */
  function fitRatings(games, cutoff, P) {
    const n = 2 + 2 * NT, A = new Float64Array(n * n), b = new Float64Array(n);
    let cnt = 0, sw = 0, sumPts = 0;
    function add(cols, vals, y, w) {
      for (let i = 0; i < cols.length; i++) {
        const ci = cols[i], vi = vals[i]; b[ci] += w * vi * y;
        for (let j = 0; j < cols.length; j++) A[ci * n + cols[j]] += w * vi * vals[j];
      }
    }
    for (const g of games) {
      if (!g.played || g.di >= cutoff) continue;
      const w = Math.pow(0.5, (cutoff - g.di) / P.halfLife), h = TIDX[g.h], a = TIDX[g.a];
      let hs = g.hs, as = g.as;
      if (P.movCap) { const m = hs - as, am = Math.abs(m); if (am > P.movCap) { const nm = Math.sign(m) * (P.movCap + (am - P.movCap) * P.movK), mid = (hs + as) / 2; hs = mid + nm / 2; as = mid - nm / 2; } }
      add([0, 1, 2 + h, 2 + NT + a], [1, 0.5, 1, -1], hs, w);
      add([0, 1, 2 + a, 2 + NT + h], [1, -0.5, 1, -1], as, w);
      cnt++; sw += 2 * w; sumPts += w * (g.hs + g.as);
    }
    for (let i = 2; i < n; i++) A[i * n + i] += P.lambda;
    if (P.priorNet) CODES.forEach((c, i) => { const v = (P.priorNet[c] || 0) / 2; b[2 + i] += P.lambda * v; b[2 + NT + i] += P.lambda * v; });
    A[n + 1] += P.Hlambda; b[1] += P.Hlambda * P.Hprior;
    A[0] += 1e-3; b[0] += 1e-3 * 113;
    const x = solve(A, b, n);
    const R = { mu: x[0], H: x[1], O: {}, D: {}, net: {}, n: cnt, Ainv: invert(A, n), nn: n };
    CODES.forEach((c, i) => { R.O[c] = x[2 + i]; R.D[c] = x[2 + NT + i]; R.net[c] = x[2 + i] + x[2 + NT + i]; });
    // scarto residuo
    let se = 0, sww = 0;
    for (const g of games) {
      if (!g.played || g.di >= cutoff) continue;
      const w = Math.pow(0.5, (cutoff - g.di) / P.halfLife);
      const m = R.H + R.net[g.h] - R.net[g.a];
      se += w * Math.pow((g.hs - g.as) - m, 2); sww += w;
    }
    R.resSd = sww ? Math.sqrt(se / sww) : P.sigma;
    // varianza a posteriori (in "unità di punteggio di squadra al quadrato") di net e scarto
    let s2 = 0, w2 = 0;
    for (const g of games) {
      if (!g.played || g.di >= cutoff) continue;
      const w = Math.pow(0.5, (cutoff - g.di) / P.halfLife);
      const eh = g.hs - (R.mu + R.H / 2 + R.O[g.h] - R.D[g.a]), ea = g.as - (R.mu - R.H / 2 + R.O[g.a] - R.D[g.h]);
      s2 += w * (eh * eh + ea * ea); w2 += 2 * w;
    }
    R.s2 = w2 ? s2 / w2 : 120;
    R.netVar = {};
    CODES.forEach((c, i) => { const o = 2 + i, d = 2 + NT + i, Ai = R.Ainv; R.netVar[c] = R.s2 * (Ai[o * n + o] + Ai[d * n + d] + 2 * Ai[o * n + d]); });
    return R;
  }

  // varianza a posteriori dello scarto atteso casa-trasferta
  function marginVar(R, h, a) {
    const n = R.nn, Ai = R.Ainv, idx = [1, 2 + TIDX[h], 2 + NT + TIDX[h], 2 + TIDX[a], 2 + NT + TIDX[a]], v = [1, 1, 1, -1, -1];
    let s = 0; for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++) s += v[i] * v[j] * Ai[idx[i] * n + idx[j]];
    return R.s2 * s;
  }

  /* ---------- Valore dei giocatori e assenze ---------- */
  function preparePlayers(data, P) {
    const gp = {}; CODES.forEach(c => { gp[c] = 0; });
    const ppg = {}; CODES.forEach(c => { ppg[c] = 0; });
    data.games.forEach(g => { if (g.played) { gp[g.h]++; gp[g.a]++; ppg[g.h] += g.hs; ppg[g.a] += g.as; } });
    CODES.forEach(c => { ppg[c] = gp[c] ? ppg[c] / gp[c] : 113; });
    CODES.forEach(t => {
      data.players[t].forEach(p => {
        let bpmBox = null;
        if (p.box && p.mpg > 0) {
          const f = v => v * 36 / p.mpg;
          const x = [1, f(p.pts), f(p.trb), f(p.ast), f(p.stl), f(p.blk), f(p.tov), f(p.fga), f(p.fta), f(p.fg3)];
          bpmBox = x.reduce((s, v, i) => s + v * BOX[i], 0);
        }
        const raw = p.bpm != null ? p.bpm : (bpmBox != null ? bpmBox : -2);
        const mp = p.mptot != null ? p.mptot : p.g * p.mpg;
        const prior = p.pts ? clamp(-3 + 0.18 * p.pts, -3, 4) : -2;
        p.bpmS = (raw * mp + prior * P.bpmPriorMin) / (mp + P.bpmPriorMin);
        p.value = Math.max(0, (p.bpmS - P.repl) * p.mpg / 48);
        p.f = gp[t] ? clamp(p.g / gp[t], 0, 1) : 1;
      });
    });
    data.gp = gp; data.ppg = ppg;
  }

  function availability(p, di) {
    const inj = p.inj; if (!inj) return 1;
    const st = inj.status.toLowerCase(), r = inj.retIdx;
    if (st.indexOf('out') >= 0 || st.indexOf('fuori') >= 0 || st.indexOf('susp') >= 0) {
      if (r == null) return 0;
      return di < r ? 0 : (di === r ? 0.5 : 1);
    }
    if (st.indexOf('doubt') >= 0) return r == null || di <= r ? 0.25 : 1;
    if (st.indexOf('day') >= 0 || st.indexOf('quest') >= 0 || st.indexOf('dubbio') >= 0) return r == null || di <= r ? 0.5 : 1;
    if (st.indexOf('prob') >= 0) return r == null || di <= r ? 0.85 : 1;
    return 1;
  }

  // Correzione del rating per chi c'è e chi manca in una certa data
  function teamAdj(data, t, di, P) {
    let delta = 0; const out = [], back = [];
    data.players[t].forEach(p => {
      if (!p.value) return;
      let contrib;
      if (p.inj) {
        const av = availability(p, di);
        contrib = P.injK * p.value * (av - p.f);
        if (av < 1 && p.value >= 0.4) out.push({ name: p.name, av, impact: -P.injK * p.value * (1 - av), status: p.inj.status, ret: p.inj.ret });
        else if (av >= 1 && p.f < 0.75 && contrib >= 0.5) back.push({ name: p.name, impact: contrib });
      } else {
        // non in infermeria: chi ha saltato partite in passato ora è disponibile (effetto parziale)
        contrib = p.f < 0.8 ? 0.6 * P.injK * p.value * (1 - p.f) : 0;
        if (contrib >= 0.8) back.push({ name: p.name, impact: contrib });
      }
      delta += contrib;
    });
    out.sort((x, y) => x.impact - y.impact); back.sort((x, y) => y.impact - x.impact);
    return { delta: clamp(delta, -14, 10), out, back };
  }

  /* ---------- Contesto completo ---------- */
  function build(raw, opts) {
    const P = Object.assign({}, DEFAULTS, opts || {});
    const data = parseData(raw);
    preparePlayers(data, P);
    const todayIdx = opts && opts.today ? dayIdx(opts.today) : (function () {
      const last = data.games.filter(g => g.played).reduce((m, g) => Math.max(m, g.di), 0); return last + 1;
    })();
    const playedDays = new Set();
    data.games.forEach(g => { playedDays.add(g.h + '@' + g.di); playedDays.add(g.a + '@' + g.di); });
    const ctx = { P, data, todayIdx, playedDays };
    // backtest e calibrazione
    ctx.bt = backtest(ctx);
    ctx.R = fitRatings(data.games, todayIdx, P);
    ctx.Rweek = fitRatings(data.games, todayIdx - 7, P);
    ctx.adjCache = new Map();
    return ctx;
  }

  function adjFor(ctx, t, di) {
    const k = t + '@' + di; let v = ctx.adjCache.get(k);
    if (!v) { v = teamAdj(ctx.data, t, di, ctx.P); ctx.adjCache.set(k, v); }
    return v;
  }

  function predict(ctx, g, R, opt) {
    R = R || ctx.R; const P = ctx.P;
    const useInj = !(opt && opt.noInj);
    const ah = useInj ? adjFor(ctx, g.h, g.di) : { delta: 0, out: [], back: [] };
    const aa = useInj ? adjFor(ctx, g.a, g.di) : { delta: 0, out: [], back: [] };
    const b2bH = ctx.playedDays.has(g.h + '@' + (g.di - 1)), b2bA = ctx.playedDays.has(g.a + '@' + (g.di - 1));
    const rH = ah.delta - (b2bH ? P.b2b : 0), rA = aa.delta - (b2bA ? P.b2b : 0);
    const hp = R.mu + R.H / 2 + R.O[g.h] - R.D[g.a] + rH / 2 - rA / 2;
    const ap = R.mu - R.H / 2 + R.O[g.a] - R.D[g.h] + rA / 2 - rH / 2;
    const margin = hp - ap;
    const sd = Math.sqrt(P.sigma * P.sigma + P.kVar * marginVar(R, g.h, g.a));
    return { hp, ap, margin, sd, total: hp + ap, pHome: Phi(margin / sd), adjH: ah, adjA: aa, b2bH, b2bA };
  }

  /* ---------- Backtest walk-forward (solo rating, senza assenze) ---------- */
  function backtest(ctx) {
    const P = ctx.P, games = ctx.data.games;
    const days = [...new Set(games.filter(g => g.played).map(g => g.di))].sort((a, b) => a - b);
    const start = dayIdx(BT_START);
    const rows = [], trend = {}; CODES.forEach(c => { trend[c] = []; });
    for (const d of days) {
      if (d < start) continue;
      const R = fitRatings(games, d, P);
      CODES.forEach(c => trend[c].push({ di: d, net: R.net[c] }));
      // record prima della giornata, per il confronto "vince chi ha il record migliore"
      const rec = {}; CODES.forEach(c => { rec[c] = [0, 0]; });
      games.forEach(g => { if (g.played && g.di < d) { const w = g.hs > g.as; rec[g.h][0] += w; rec[g.h][1]++; rec[g.a][0] += !w; rec[g.a][1]++; } });
      games.filter(g => g.played && g.di === d).forEach(g => {
        const b2bH = ctx.playedDays.has(g.h + '@' + (d - 1)), b2bA = ctx.playedDays.has(g.a + '@' + (d - 1));
        const rH = -(b2bH ? P.b2b : 0), rA = -(b2bA ? P.b2b : 0);
        const hp = R.mu + R.H / 2 + R.O[g.h] - R.D[g.a] + rH / 2 - rA / 2;
        const ap = R.mu - R.H / 2 + R.O[g.a] - R.D[g.h] + rA / 2 - rH / 2;
        const sd = Math.sqrt(P.sigma * P.sigma + P.kVar * marginVar(R, g.h, g.a));
        const pctH = rec[g.h][1] ? rec[g.h][0] / rec[g.h][1] : 0.5, pctA = rec[g.a][1] ? rec[g.a][0] / rec[g.a][1] : 0.5;
        rows.push({ g, hp, ap, m: hp - ap, sd, p: Phi((hp - ap) / sd), real: g.hs - g.as, tot: g.hs + g.as, recPick: pctH >= pctA ? 1 : 0 });
      });
    }
    const T = M_today(ctx), Rn = fitRatings(games, T, P);
    CODES.forEach(c => { const a = trend[c]; if (!a.length || a[a.length - 1].di !== T) a.push({ di: T, net: Rn.net[c] }); });
    if (!rows.length) return { n: 0, rows, trend };
    let acc = 0, brier = 0, ll = 0, maeM = 0, maeT = 0, fav = 0, favN = 0, homeW = 0, recOk = 0, cover = 0;
    const bins = [[0.5, 0.6], [0.6, 0.7], [0.7, 0.8], [0.8, 1.01]].map(b => ({ lo: b[0], hi: b[1], n: 0, sumP: 0, wins: 0 }));
    rows.forEach(r => {
      const p = r.p, win = r.real > 0 ? 1 : 0, pf = Math.max(p, 1 - p), favWon = (p >= 0.5) === (win === 1);
      if (favWon) acc++;
      brier += Math.pow(p - win, 2); ll -= Math.log(clamp(win ? p : 1 - p, 0.01, 0.99));
      maeM += Math.abs(r.m - r.real); maeT += Math.abs(r.hp + r.ap - r.tot);
      if (pf >= 0.65) { favN++; if (favWon) fav++; }
      if (win) homeW++;
      if (r.recPick === win) recOk++;
      if (Math.abs(r.real - r.m) <= 1.2816 * r.sd) cover++;
      const b = bins.find(b => pf >= b.lo && pf < b.hi); b.n++; b.sumP += pf; b.wins += favWon ? 1 : 0;
    });
    const n = rows.length;
    return {
      n, rows, trend, bins, acc: acc / n, brier: brier / n, logloss: ll / n,
      maeMargin: maeM / n, maeTotal: maeT / n, favAcc: favN ? fav / favN : null, favN, homeRate: homeW / n,
      recAcc: recOk / n, cover80: cover / n, brierBase: 0.25
    };
  }
  function M_today(ctx) { return ctx.todayIdx; }

  /* ---------- Proiezioni dei giocatori ---------- */
  function playerLines(ctx, t, di, expPts) {
    const data = ctx.data, list = data.players[t].filter(p => p.box && p.mpg > 0);
    if (!list.length) return [];
    let baseMin = 0, baseP = 0, baseR = 0, baseA = 0, base3 = 0, expMin = 0;
    const rows = list.map(p => {
      const av = availability(p, di);
      baseMin += p.mpg * p.f; baseP += p.pts * p.f; baseR += p.trb * p.f; baseA += p.ast * p.f; base3 += p.fg3 * p.f;
      expMin += p.mpg * av;
      return { p, av };
    });
    const minScale = clamp(baseMin / (expMin || 1), 0.85, 1.3);
    let wP = 0, wR = 0, wA = 0, w3 = 0;
    rows.forEach(r => {
      r.mp = Math.min(40, r.p.mpg * minScale);
      const k = r.mp / r.p.mpg;
      r.rp = r.p.pts * k; r.rr = r.p.trb * k; r.ra = r.p.ast * k; r.r3 = r.p.fg3 * k;
      wP += r.rp * r.av; wR += r.rr * r.av; wA += r.ra * r.av; w3 += r.r3 * r.av;
    });
    const share = clamp(baseP / (data.ppg[t] || 113), 0.6, 1);
    const fP = clamp((expPts * share) / (wP || 1), 0.75, 1.35);
    const fR = clamp(baseR / (wR || 1), 0.8, 1.3), fA = clamp(baseA / (wA || 1), 0.8, 1.3), f3 = clamp(base3 / (w3 || 1), 0.8, 1.3);
    return rows.filter(r => r.av > 0).map(r => {
      const pts = r.rp * fP, reb = r.rr * fR, ast = r.ra * fA, fg3 = r.r3 * f3;
      return { name: r.p.name, av: r.av, mp: r.mp, pts, reb, ast, fg3, inj: r.p.inj || null };
    }).sort((a, b) => b.pts - a.pts);
  }
  function pOver(mu, L, kind) {
    if (mu <= 0) return 0;
    const sd = kind === 'pts' ? 1.45 * Math.sqrt(mu) + 0.8 : (kind === 'reb' ? 1.15 * Math.sqrt(mu) + 0.4 : 1.1 * Math.sqrt(mu) + 0.4);
    return 1 - Phi((L - 0.5 - mu) / sd);
  }
  function pDoubleDouble(l) {
    const a = pOver(l.pts, 10, 'pts'), b = pOver(l.reb, 10, 'reb'), c = pOver(l.ast, 10, 'ast');
    return a * b + a * c + b * c - 2 * a * b * c;
  }

  /* ---------- Simulazione della stagione ---------- */
  function simulate(ctx, nSims) {
    nSims = nSims || ctx.P.sims; const P = ctx.P, R = ctx.R, data = ctx.data;
    const W = new Int32Array(NT), L = new Int32Array(NT), sched = new Int32Array(NT);
    data.games.forEach(g => {
      sched[TIDX[g.h]]++; sched[TIDX[g.a]]++;
      if (g.played) { if (g.hs > g.as) { W[TIDX[g.h]]++; L[TIDX[g.a]]++; } else { W[TIDX[g.a]]++; L[TIDX[g.h]]++; } }
    });
    const rem = data.games.filter(g => !g.played).map(g => {
      const pr = predict(ctx, g); return { h: TIDX[g.h], a: TIDX[g.a], m: pr.margin };
    });
    const virt = []; // partite non ancora in calendario (NBA Cup) contro una squadra media
    CODES.forEach((c, i) => { const k = Math.max(0, 82 - sched[i]); for (let j = 0; j < k; j++) virt.push({ t: i, m: R.net[c] }); });
    const conf = CODES.map(c => TEAMS[c].c);
    const winsAll = Array.from({ length: NT }, () => new Int32Array(nSims));
    const top6 = new Float64Array(NT), playin = new Float64Array(NT), seed1 = new Float64Array(NT), bestRec = new Float64Array(NT);
    let seed = 12345;
    function rnd() { seed = (seed * 1664525 + 1013904223) >>> 0; return (seed + 0.5) / 4294967296; }
    function gauss() { return Math.sqrt(-2 * Math.log(rnd())) * Math.cos(2 * Math.PI * rnd()); }
    const w = new Float64Array(NT), eps = new Float64Array(NT);
    const tsd = CODES.map(c => Math.sqrt(R.netVar[c] + P.drift * P.drift));
    for (let s = 0; s < nSims; s++) {
      for (let i = 0; i < NT; i++) { w[i] = W[i]; eps[i] = gauss() * tsd[i]; }
      for (const g of rem) { const m = g.m + eps[g.h] - eps[g.a] + gauss() * P.sigma; if (m > 0) w[g.h]++; else w[g.a]++; }
      for (const v of virt) { if (v.m + eps[v.t] + gauss() * P.sigma > 0) w[v.t]++; }
      const key = []; for (let i = 0; i < NT; i++) { winsAll[i][s] = w[i]; key.push(w[i] + rnd() * 0.01); }
      ['E', 'W'].forEach(cf => {
        const idx = []; for (let i = 0; i < NT; i++) if (conf[i] === cf) idx.push(i);
        idx.sort((x, y) => key[y] - key[x]);
        idx.forEach((t, r) => { if (r < 6) top6[t]++; else if (r < 10) playin[t]++; if (r === 0) seed1[t]++; });
      });
      let bi = 0; for (let i = 1; i < NT; i++) if (key[i] > key[bi]) bi = i; bestRec[bi]++;
    }
    const out = {};
    CODES.forEach((c, i) => {
      const arr = Array.from(winsAll[i]).sort((a, b) => a - b);
      const mean = arr.reduce((s, v) => s + v, 0) / nSims;
      out[c] = {
        W: W[i], L: L[i], gp: W[i] + L[i], wMean: mean, lMean: 82 - mean, p10: arr[Math.floor(nSims * 0.1)], p90: arr[Math.floor(nSims * 0.9)],
        hist: (function () { const h = {}; arr.forEach(v => { h[v] = (h[v] || 0) + 1; }); return h; })(), sd: R.netVar ? Math.sqrt(R.netVar[c]) : null,
        pTop6: top6[i] / nSims, pPlayin: playin[i] / nSims, pPost: (top6[i] + playin[i]) / nSims, pSeed1: seed1[i] / nSims, pBest: bestRec[i] / nSims
      };
    });
    return out;
  }

  const api = { marginVar, TEAMS, CODES, DEFAULTS, team, dayIdx, idxDate, normName, Phi, build, predict, adjFor, fitRatings, playerLines, pOver, pDoubleDouble, simulate, availability, parseData };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.NBAModel = api;
})(typeof window !== 'undefined' ? window : globalThis);
