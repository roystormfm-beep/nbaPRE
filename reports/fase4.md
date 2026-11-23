# Fase 4 — Contesto e totali

Campione: stagioni di sviluppo con injury report pre-partita (2018-19 → 2024-25), partite con linea di chiusura.
Ogni correzione è stimata solo sulle stagioni precedenti a quella pronosticata. Stagione di test 2025-26 non toccata.
Tra parentesi: intervallo di confidenza al 95% (bootstrap appaiato). Negativo = errore più basso.

## Scarto (casa − ospiti)

| Variante | Partite | MAE | RMSE | vs fase 3 | vs mercato |
|---|---:|---:|---:|---:|---:|
| Fase 3: giocatori + injury report (nessun contesto) | 7747 | 10.458 | 13.356 | — | +0.174 [+0.117; +0.231] |
| + vantaggio del campo (ricalibrato) | 7747 | 10.460 | 13.358 | +0.001 [-0.001; +0.004] | +0.175 [+0.118; +0.234] |
| Contesto completo | 7747 | 10.427 | 13.319 | -0.032 [-0.051; -0.012] | +0.142 [+0.088; +0.197] |
| Contesto completo senza vantaggio del campo per squadra | 7747 | 10.426 | 13.318 | -0.032 [-0.052; -0.012] | +0.142 [+0.085; +0.197] |
| Contesto completo senza riposo e calendario fitto | 7747 | 10.456 | 13.354 | -0.002 [-0.010; +0.005] | +0.172 [+0.115; +0.228] |
| Contesto completo senza viaggi e fusi orari | 7747 | 10.427 | 13.318 | -0.032 [-0.053; -0.011] | +0.142 [+0.087; +0.197] |
| Contesto completo senza altura (Denver, Utah) | 7747 | 10.426 | 13.319 | -0.032 [-0.052; -0.012] | +0.142 [+0.086; +0.197] |
| Contesto completo senza fine stagione (squadre senza obiettivi / già sicure) | 7747 | 10.431 | 13.324 | -0.027 [-0.047; -0.006] | +0.147 [+0.094; +0.205] |
| Contesto essenziale: campo + riposo + fine stagione (scelto) | 7747 | 10.427 | 13.318 | -0.032 [-0.052; -0.013] | +0.142 [+0.088; +0.195] |

## Totale punti

| Variante | Partite | MAE | RMSE | vs fase 3 | vs mercato |
|---|---:|---:|---:|---:|---:|
| Fase 3: giocatori (punti dai minuti e dall'efficienza) | 7748 | 15.597 | 19.835 | — | +1.313 [+1.163; +1.466] |
| Squadre: ritmo × efficienza di squadra | 7748 | 14.828 | 18.832 | -0.769 [-0.900; -0.634] | +0.544 [+0.451; +0.635] |
| Combinato: ritmo di squadra × efficienza dei giocatori disponibili | 7748 | 14.713 | 18.686 | -0.884 [-1.008; -0.758] | +0.430 [+0.343; +0.515] |
| Combinato + correzione di livello (scelto) | 7748 | 14.595 | 18.492 | -1.002 [-1.146; -0.862] | +0.311 [+0.237; +0.389] |
| + contesto (riposo, viaggi, altura, momento della stagione) | 7748 | 14.612 | 18.510 | -0.985 [-1.126; -0.847] | +0.329 [+0.249; +0.405] |
| + arbitri | 7748 | 14.593 | 18.488 | -1.004 [-1.140; -0.861] | +0.309 [+0.233; +0.388] |

Arbitri: 128 arbitri stimati; effetti molto piccoli (deviazione standard 0.05 punti sul totale).

## Modello finale della fase 4 (scarto: contesto essenziale; totale: combinato + livello)

| Metrica | Modello | Mercato | Differenza [IC 95%] |
|---|---:|---:|---:|
| MAE scarto | 10.427 | 10.284 | +0.142 [+0.086; +0.197] |
| MAE totale | 14.593 | 14.281 | |
| MAE punti per squadra | 9.052 | 8.898 | |
| Brier (vittoria casa) | 0.2099 | 0.2066 | +0.0033 [+0.0017; +0.0048] |
| Log loss | 0.6068 | 0.5998 | +0.0070 [+0.0036; +0.0106] |
| Calibrazione (ECE) | 0.0102 | 0.0074 | |
| Vincitori indovinati | 67.0% | 67.9% | |

Brier fase 3 sullo stesso campione: 0.2107; fase 4 − fase 3: -0.0008 [-0.0013; -0.0003].

## Per stagione (modello finale)

| Stagione | Partite | MAE scarto | mercato | MAE totale | mercato | Brier | mercato |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2018-19 | 787 | 9.77 | 9.69 | 14.50 | 14.20 | 0.2014 | 0.1983 |
| 2019-20 | 1041 | 9.97 | 9.92 | 15.04 | 14.86 | 0.2121 | 0.2099 |
| 2020-21 | 1063 | 10.88 | 10.73 | 14.67 | 14.39 | 0.2197 | 0.2137 |
| 2021-22 | 1214 | 10.80 | 10.61 | 14.32 | 14.05 | 0.2099 | 0.2088 |
| 2022-23 | 1214 | 9.95 | 9.78 | 14.46 | 14.21 | 0.2205 | 0.2163 |
| 2023-24 | 1215 | 10.69 | 10.56 | 14.89 | 14.23 | 0.2025 | 0.1985 |
| 2024-25 | 1213 | 10.68 | 10.52 | 14.31 | 14.10 | 0.2017 | 0.1990 |

## Effetti stimati (modello usato per il 2024-25, allenato fino al 2023-24)

Punti di scarto per la squadra di casa quando la condizione vale per lei (al netto di quanto già visto dal modello giocatori).

| Variabile | Effetto |
|---|---:|
| vantaggio_campo | -0.14 |
| diff_rest0 | -1.03 |
| diff_rest1 | +0.22 |
| diff_rest3 | +0.01 |
| diff_three_in_four | -0.44 |
| diff_dens | -0.28 |
| diff_late_lowwin | -0.71 |
| diff_late_top | -0.43 |
| diff_b2b_road | -0.38 |
