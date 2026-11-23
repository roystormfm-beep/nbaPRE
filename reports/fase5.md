# Fase 5 — Ensemble, calibrazione, backtest completo

## Test 2025-26 (mai usato per scelte o tarature)

Partite: 1214.

| Metrica | Modello | Mercato | Differenza [IC 95%] |
|---|---:|---:|---:|
| MAE scarto | 11,058 | 10,886 | +0,172 [+0,058; +0,292] |
| RMSE scarto | 14,065 | 13,913 | |
| MAE totale | 14,964 | 14,548 | |
| MAE punti per squadra | 9,390 | 9,165 | |
| Brier | 0,1995 | 0,1942 | +0,0054 [+0,0024; +0,0083] |
| Log loss | 0,5827 | 0,5696 | +0,0132 [+0,0068; +0,0204] |
| ECE | 0,0379 | 0,0267 | |
| Vincitori indovinati | 69,8% | 69,4% | |
| Contro lo spread di chiusura | 583-629 (48,1% [45,2; 50,8]) | | |
| ROI a -110 | -8,2% [-13,5; -3,0] | | |

Probabilità di coprire lo spread di chiusura: log loss 0,7041 (moneta: 0,6931), ECE 0,074. Intervalli dello scarto: 50% → 49,3%, 80% → 78,4%, 95% → 94,2% delle partite.

Partite in cui modello e mercato differiscono di almeno 3 punti: 224; errore medio modello 10,92, mercato 10,58.

### Componenti e ablation (scarto)

| Modello | MAE | vs mercato | vs ensemble finale |
|---|---:|---:|---:|
| Baseline della pagina (v2), senza assenze | 11,308 | +0,422 [+0,223; +0,616] | +0,249 [+0,088; +0,416] |
| Baseline ritarato, con injury report | 11,289 | +0,404 [+0,230; +0,579] | +0,231 [+0,074; +0,390] |
| Elo con margine di vittoria | 11,472 | +0,586 [+0,355; +0,804] | +0,414 [+0,224; +0,617] |
| Rating di squadra (ritmo ed efficienza) | 11,420 | +0,534 [+0,326; +0,738] | +0,362 [+0,189; +0,550] |
| LightGBM su squadra e contesto | 11,377 | +0,491 [+0,305; +0,677] | +0,319 [+0,153; +0,483] |
| Giocatori + minuti, senza injury report | 11,257 | +0,371 [+0,199; +0,544] | +0,199 [+0,072; +0,317] |
| Giocatori + minuti, con injury report | 11,132 | +0,246 [+0,097; +0,398] | +0,074 [+0,004; +0,149] |
| … + contesto (riposo, fine stagione) | 11,109 | +0,223 [+0,072; +0,363] | +0,050 [+0,006; +0,097] |
| Ensemble finale | 11,058 | +0,172 [+0,049; +0,293] | — |
| Mercato (linea di chiusura) | 10,886 | — | — |

### Totale

| Modello | MAE | vs mercato | vs finale |
|---|---:|---:|---:|
| Baseline ritarato | 15,135 | +0,587 [+0,347; +0,845] | +0,171 [-0,013; +0,357] |
| Rating di squadra | 14,927 | +0,379 [+0,157; +0,605] | -0,037 [-0,226; +0,155] |
| LightGBM | 15,067 | +0,519 [+0,276; +0,777] | +0,103 [-0,074; +0,288] |
| Solo giocatori (fase 3) | 16,058 | +1,510 [+1,098; +1,927] | +1,094 [+0,740; +1,446] |
| Finale: ritmo di squadra × giocatori disponibili | 14,964 | +0,416 [+0,216; +0,617] | — |
| Mercato (linea di chiusura) | 14,548 | — | — |

### Per stagione

| Stagione | Partite | MAE | mercato | differenza [IC 95%] | MAE totale | mercato | Brier | mercato |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025-26 | 1214 | 11,06 | 10,89 | +0,17 [+0,06; +0,29] | 14,96 | 14,55 | 0,1995 | 0,1942 |

### Per mese

| Mese | Partite | MAE | mercato | MAE totale | mercato |
|---|---:|---:|---:|---:|---:|
| 2025-10 | 64 | 10,74 | 10,98 | 16,37 | 16,23 |
| 2025-11 | 219 | 10,00 | 9,83 | 14,40 | 13,87 |
| 2025-12 | 197 | 11,61 | 11,61 | 15,92 | 15,64 |
| 2026-01 | 233 | 11,36 | 11,04 | 15,11 | 14,21 |
| 2026-02 | 166 | 11,55 | 11,42 | 14,61 | 14,37 |
| 2026-03 | 239 | 10,80 | 10,69 | 14,16 | 13,86 |
| 2026-04 | 96 | 11,60 | 10,96 | 15,62 | 15,55 |

## Sviluppo 2018-19 → 2024-25

Partite: 7747.

| Metrica | Modello | Mercato | Differenza [IC 95%] |
|---|---:|---:|---:|
| MAE scarto | 10,412 | 10,284 | +0,128 [+0,076; +0,177] |
| RMSE scarto | 13,314 | 13,210 | |
| MAE totale | 14,593 | 14,281 | |
| MAE punti per squadra | 9,054 | 8,898 | |
| Brier | 0,2096 | 0,2066 | +0,0030 [+0,0016; +0,0044] |
| Log loss | 0,6063 | 0,5998 | +0,0065 [+0,0033; +0,0098] |
| ECE | 0,0078 | 0,0074 | |
| Vincitori indovinati | 66,6% | 67,9% | |
| Contro lo spread di chiusura | 3909-3738 (51,1% [50,0; 52,3]) | | |
| ROI a -110 | -2,4% [-4,5; -0,3] | | |

Probabilità di coprire lo spread di chiusura: log loss 0,7012 (moneta: 0,6931), ECE 0,047. Intervalli dello scarto: 50% → 49,4%, 80% → 79,1%, 95% → 94,4% delle partite.

Partite in cui modello e mercato differiscono di almeno 3 punti: 1486; errore medio modello 10,79, mercato 10,38.

### Componenti e ablation (scarto)

| Modello | MAE | vs mercato | vs ensemble finale |
|---|---:|---:|---:|
| Baseline della pagina (v2), senza assenze | 10,669 | +0,384 [+0,313; +0,454] | +0,257 [+0,199; +0,316] |
| Baseline ritarato, con injury report | 10,564 | +0,279 [+0,218; +0,339] | +0,151 [+0,100; +0,205] |
| Elo con margine di vittoria | 10,762 | +0,477 [+0,400; +0,554] | +0,349 [+0,283; +0,421] |
| Rating di squadra (ritmo ed efficienza) | 10,751 | +0,466 [+0,388; +0,542] | +0,339 [+0,275; +0,404] |
| LightGBM su squadra e contesto | 10,680 | +0,395 [+0,321; +0,467] | +0,267 [+0,205; +0,330] |
| Giocatori + minuti, senza injury report | 10,583 | +0,299 [+0,232; +0,362] | +0,171 [+0,123; +0,218] |
| Giocatori + minuti, con injury report | 10,458 | +0,174 [+0,118; +0,229] | +0,046 [+0,021; +0,070] |
| … + contesto (riposo, fine stagione) | 10,427 | +0,142 [+0,086; +0,197] | +0,015 [-0,003; +0,032] |
| Ensemble finale | 10,412 | +0,128 [+0,077; +0,179] | — |
| Mercato (linea di chiusura) | 10,284 | — | — |

### Totale

| Modello | MAE | vs mercato | vs finale |
|---|---:|---:|---:|
| Baseline ritarato | 14,801 | +0,519 [+0,422; +0,610] | +0,207 [+0,128; +0,287] |
| Rating di squadra | 14,825 | +0,544 [+0,454; +0,636] | +0,232 [+0,148; +0,315] |
| LightGBM | 14,788 | +0,507 [+0,409; +0,602] | +0,195 [+0,119; +0,279] |
| Solo giocatori (fase 3) | 15,595 | +1,313 [+1,163; +1,465] | +1,001 [+0,866; +1,142] |
| Finale: ritmo di squadra × giocatori disponibili | 14,593 | +0,312 [+0,235; +0,390] | — |
| Mercato (linea di chiusura) | 14,281 | — | — |

### Per stagione

| Stagione | Partite | MAE | mercato | differenza [IC 95%] | MAE totale | mercato | Brier | mercato |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018-19 | 787 | 9,81 | 9,69 | +0,13 [-0,02; +0,29] | 14,50 | 14,20 | 0,2028 | 0,1983 |
| 2019-20 | 1041 | 9,96 | 9,92 | +0,05 [-0,08; +0,17] | 15,04 | 14,86 | 0,2109 | 0,2099 |
| 2020-21 | 1063 | 10,88 | 10,73 | +0,15 [+0,01; +0,28] | 14,67 | 14,39 | 0,2196 | 0,2137 |
| 2021-22 | 1214 | 10,79 | 10,61 | +0,18 [+0,03; +0,31] | 14,32 | 14,05 | 0,2096 | 0,2088 |
| 2022-23 | 1214 | 9,92 | 9,78 | +0,15 [+0,02; +0,28] | 14,46 | 14,21 | 0,2203 | 0,2163 |
| 2023-24 | 1215 | 10,68 | 10,56 | +0,12 [+0,00; +0,25] | 14,89 | 14,23 | 0,2025 | 0,1985 |
| 2024-25 | 1213 | 10,62 | 10,52 | +0,11 [-0,02; +0,23] | 14,31 | 14,10 | 0,2006 | 0,1990 |

### Per mese

| Mese | Partite | MAE | mercato | MAE totale | mercato |
|---|---:|---:|---:|---:|---:|
| 2018-12 | 105 | 9,78 | 9,50 | 13,75 | 13,99 |
| 2019-01 | 221 | 9,87 | 9,70 | 14,37 | 14,10 |
| 2019-02 | 158 | 9,36 | 9,39 | 15,00 | 14,51 |
| 2019-03 | 224 | 10,11 | 9,97 | 14,79 | 14,21 |
| 2019-04 | 79 | 9,79 | 9,68 | 14,05 | 14,13 |
| 2019-10 | 52 | 9,09 | 9,14 | 17,84 | 16,13 |
| 2019-11 | 214 | 9,27 | 9,35 | 15,64 | 15,22 |
| 2019-12 | 219 | 10,20 | 10,06 | 14,32 | 14,30 |
| 2020-01 | 222 | 10,03 | 10,14 | 14,47 | 14,15 |
| 2020-02 | 168 | 10,59 | 10,40 | 13,90 | 14,07 |
| 2020-03 | 78 | 10,30 | 10,17 | 16,41 | 16,08 |
| 2020-08 | 80 | 10,30 | 10,16 | 14,83 | 15,51 |
| 2020-12 | 50 | 14,71 | 13,99 | 15,36 | 14,26 |
| 2021-01 | 222 | 10,77 | 10,76 | 15,64 | 15,47 |
| 2021-02 | 212 | 10,88 | 10,58 | 13,94 | 13,51 |
| 2021-03 | 204 | 10,42 | 10,40 | 14,00 | 13,92 |
| 2021-04 | 240 | 11,33 | 11,14 | 14,61 | 14,31 |
| 2021-05 | 135 | 9,51 | 9,45 | 15,10 | 14,86 |
| 2021-10 | 77 | 10,12 | 10,08 | 16,27 | 16,67 |
| 2021-11 | 225 | 10,67 | 10,49 | 13,99 | 13,74 |
| 2021-12 | 209 | 10,95 | 10,57 | 13,89 | 13,77 |
| 2022-01 | 231 | 10,60 | 10,58 | 14,86 | 14,33 |
| 2022-02 | 163 | 10,62 | 10,51 | 14,18 | 13,55 |
| 2022-03 | 229 | 10,88 | 10,56 | 13,97 | 13,67 |
| 2022-04 | 80 | 11,98 | 11,97 | 14,26 | 14,43 |
| 2022-10 | 86 | 10,20 | 10,43 | 13,51 | 13,42 |
| 2022-11 | 222 | 9,81 | 9,48 | 14,82 | 14,36 |
| 2022-12 | 222 | 10,21 | 10,11 | 13,85 | 13,70 |
| 2023-01 | 222 | 9,57 | 9,49 | 13,93 | 13,38 |
| 2023-02 | 163 | 9,54 | 9,38 | 15,35 | 15,45 |
| 2023-03 | 229 | 10,09 | 9,95 | 14,43 | 14,14 |
| 2023-04 | 70 | 10,50 | 10,12 | 16,09 | 16,21 |
| 2023-10 | 39 | 10,08 | 9,71 | 13,54 | 13,85 |
| 2023-11 | 219 | 10,33 | 10,12 | 14,65 | 13,93 |
| 2023-12 | 207 | 10,18 | 10,05 | 13,06 | 13,14 |
| 2024-01 | 231 | 11,18 | 11,30 | 17,06 | 16,12 |
| 2024-02 | 174 | 11,34 | 11,03 | 14,74 | 13,72 |
| 2024-03 | 230 | 10,53 | 10,53 | 15,18 | 14,17 |
| 2024-04 | 115 | 10,75 | 10,42 | 14,36 | 14,01 |
| 2024-10 | 55 | 9,90 | 10,25 | 16,24 | 15,70 |
| 2024-11 | 221 | 9,84 | 9,86 | 14,82 | 14,76 |
| 2024-12 | 191 | 10,64 | 10,34 | 14,95 | 14,76 |
| 2025-01 | 227 | 11,81 | 11,50 | 13,47 | 13,05 |
| 2025-02 | 176 | 10,28 | 10,43 | 14,25 | 13,84 |
| 2025-03 | 238 | 10,70 | 10,67 | 13,71 | 13,60 |
| 2025-04 | 105 | 10,47 | 10,00 | 14,37 | 14,56 |

## Pesi dell'ensemble (stimati sulle stagioni precedenti)

| Stagione | Giocatori + minuti + contesto | Baseline ritarato | Rating di squadra | Elo | LightGBM | costante |
|---|---:|---:|---:|---:|---:|---:|
| 2018-19 | 0,71 | 0,00 | 0,00 | 0,24 | 0,00 | -0,59 |
| 2019-20 | 0,73 | 0,35 | 0,00 | 0,00 | 0,00 | -0,19 |
| 2020-21 | 0,71 | 0,27 | 0,00 | 0,02 | 0,04 | -0,21 |
| 2021-22 | 0,87 | 0,15 | 0,00 | 0,00 | 0,00 | -0,47 |
| 2022-23 | 0,80 | 0,23 | 0,00 | 0,00 | 0,00 | -0,32 |
| 2023-24 | 0,73 | 0,28 | 0,00 | 0,00 | 0,00 | -0,05 |
| 2024-25 | 0,78 | 0,25 | 0,00 | 0,00 | 0,00 | -0,07 |
| 2025-26 | 0,76 | 0,27 | 0,00 | 0,00 | 0,03 | -0,20 |

## Forma della distribuzione dello scarto (sviluppo)

| Forma | Log loss | Brier | ECE | copertura 80% | copertura 95% | effetto del totale | effetto della differenza |
|---|---:|---:|---:|---:|---:|---:|---:|
| normale | 0,6065 | 0,2097 | 0,0096 | 80,1% | 94,2% | 0,00 | 0,000 |
| normale_v | 0,6066 | 0,2097 | 0,0099 | 80,0% | 94,2% | 0,38 | 0,001 |
| t | 0,6063 | 0,2096 | 0,0078 | 79,1% | 94,4% | 0,46 | -0,009 |
| empirica | 0,6066 | 0,2097 | 0,0054 | 79,1% | 94,5% | 0,38 | 0,001 |

## Modello consapevole del mercato — sviluppo (2016-17, 2023-24, 2024-25)

| Informazione | Partite | Correlazione col movimento | Errore sul movimento (apertura → modello) | Direzione giusta | CLV medio | CLV con disaccordo ≥ 3 |
|---|---:|---:|---:|---:|---:|---:|
| all'apertura (senza injury report) | 3603 | 0,36 | 1,54 → 1,51 | 68,2% [65,1; 71,4] su 831 | +0,48 [+0,41; +0,55] | +1,27 [+1,07; +1,49] su 846 |
| prima della gara (con injury report) | 1213 | 0,76 | 1,91 → 1,53 | 82,9% [79,8; 86,0] su 620 | +1,30 [+1,16; +1,46] | +3,30 [+2,94; +3,70] su 344 |

## Modello consapevole del mercato — test 2025-26

| Informazione | Partite | Correlazione col movimento | Errore sul movimento (apertura → modello) | Direzione giusta | CLV medio | CLV con disaccordo ≥ 3 |
|---|---:|---:|---:|---:|---:|---:|
| all'apertura (senza injury report) | 1214 | 0,25 | 1,48 → 1,53 | 62,6% [58,0; 67,0] su 455 | +0,39 [+0,27; +0,51] | +0,77 [+0,47; +1,08] su 310 |
| prima della gara (con injury report) | 1214 | 0,59 | 1,48 → 1,37 | 76,0% [72,6; 79,1] su 657 | +0,84 [+0,73; +0,96] | +1,96 [+1,66; +2,29] su 285 |

## Le 50 partite peggiori del test (ensemble)

Motivi: TIRO3 44, LIBERI 4, ASSENZA 5, RIENTRO 7, SUPPL 0, SENSO_UNICO 44, MERCATO 8, nessun motivo 0

| Data | Partita | Risultato | Scarto | Pronostico | Mercato | Errore | Motivi |
|---|---|---|---:|---:|---:|---:|---|
| 2026-02-20 | DEN @ POR | 157-103 | -54 | -1.4 | -1.5 | -52.6 | TIRO3 (-24 punti per la casa); LIBERI (-6 punti per la casa); SENSO_UNICO |
| 2026-03-29 | ORL @ TOR | 87-139 | +52 | +1.0 | +1.5 | +51.0 | TIRO3 (+22 punti per la casa); SENSO_UNICO |
| 2026-02-11 | NYK @ PHI | 138-89 | -49 | -0.8 | -2.5 | -48.2 | TIRO3 (-29 punti per la casa); SENSO_UNICO |
| 2026-01-10 | CHA @ UTA | 150-95 | -55 | -8.2 | -6.5 | -46.8 | TIRO3 (-21 punti per la casa); ASSENZA UTA: Svi Mykhailiuk; RIENTRO CHA: Ryan Kalkbrenner; SENSO_UNICO |
| 2026-04-10 | MEM @ UTA | 101-147 | +46 | +0.9 | +4.5 | +45.1 | TIRO3 (+30 punti per la casa); MERCATO (linea -4.5); ASSENZA MEM: Javon Small; SENSO_UNICO |
| 2025-12-14 | MIL @ BKN | 82-127 | +45 | +0.9 | -1.5 | +44.1 | TIRO3 (+24 punti per la casa); SENSO_UNICO |
| 2026-01-21 | BKN @ NYK | 66-120 | +54 | +10.9 | +12.5 | +43.1 | TIRO3 (+24 punti per la casa); SENSO_UNICO |
| 2026-01-05 | CHA @ OKC | 124-97 | -27 | +14.0 | +15.5 | -41.0 | TIRO3 (-26 punti per la casa); LIBERI (-7 punti per la casa); SENSO_UNICO |
| 2026-02-01 | BKN @ DET | 77-130 | +53 | +14.2 | +13.5 | +38.8 | TIRO3 (+14 punti per la casa); SENSO_UNICO |
| 2025-11-25 | ORL @ PHI | 144-103 | -41 | -2.3 | -4.5 | -38.7 | RIENTRO ORL: Noah Penda; SENSO_UNICO |
| 2026-03-06 | NYK @ DEN | 142-103 | -39 | -0.6 | +1.5 | -38.4 | TIRO3 (-30 punti per la casa); SENSO_UNICO |
| 2026-03-19 | MIL @ UTA | 96-128 | +32 | -5.9 | -5.5 | +37.9 | SENSO_UNICO |
| 2026-02-22 | PHI @ MIN | 135-108 | -27 | +10.2 | +9.5 | -37.2 | TIRO3 (-29 punti per la casa); ASSENZA MIN: Naz Reid; SENSO_UNICO |
| 2025-12-10 | PHX @ OKC | 89-138 | +49 | +12.4 | +15.5 | +36.6 | TIRO3 (+26 punti per la casa); MERCATO (linea -15.5); SENSO_UNICO |
| 2026-02-01 | CHI @ MIA | 91-134 | +43 | +6.6 | +5.5 | +36.4 | TIRO3 (+27 punti per la casa); RIENTRO MIA: Davion Mitchell; SENSO_UNICO |
| 2026-03-04 | CHA @ BOS | 118-89 | -29 | +6.9 | +6.5 | -35.9 | TIRO3 (-13 punti per la casa); SENSO_UNICO |
| 2026-03-08 | ORL @ MIL | 130-91 | -39 | -3.2 | -6.5 | -35.8 | TIRO3 (-15 punti per la casa); MERCATO (linea +6.5); SENSO_UNICO |
| 2026-02-06 | NYK @ DET | 80-118 | +38 | +2.3 | +5.5 | +35.7 | TIRO3 (+19 punti per la casa); ASSENZA NYK: OG Anunoby; MERCATO (linea -5.5); SENSO_UNICO |
| 2025-11-21 | MIA @ CHI | 143-107 | -36 | -0.8 | +2.5 | -35.2 | TIRO3 (-11 punti per la casa); RIENTRO MIA: Keshad Johnson; SENSO_UNICO |
| 2025-11-20 | SAC @ MEM | 96-137 | +41 | +6.1 | +3.5 | +34.9 | SENSO_UNICO |
| 2026-04-02 | LAL @ OKC | 96-139 | +43 | +8.4 | +9.5 | +34.6 | TIRO3 (+23 punti per la casa); SENSO_UNICO |
| 2026-04-10 | PHX @ LAL | 73-101 | +28 | -6.4 | -2.5 | +34.4 | TIRO3 (+25 punti per la casa); MERCATO (linea +2.5); SENSO_UNICO |
| 2026-01-26 | PHI @ CHA | 93-130 | +37 | +2.7 | +1.5 | +34.3 | TIRO3 (+12 punti per la casa); SENSO_UNICO |
| 2026-01-13 | MIN @ MIL | 139-106 | -33 | +0.9 | +1.5 | -33.9 | TIRO3 (-21 punti per la casa); RIENTRO MIN: Joan Beringer; SENSO_UNICO |
| 2025-12-07 | GSW @ CHI | 123-91 | -32 | +1.8 | -1.5 | -33.8 | TIRO3 (-25 punti per la casa); MERCATO (linea +1.5); SENSO_UNICO |
| 2025-12-04 | BOS @ WAS | 146-101 | -45 | -11.7 | -10.5 | -33.3 | TIRO3 (-13 punti per la casa); SENSO_UNICO |
| 2025-10-24 | MIA @ MEM | 146-114 | -32 | +1.3 | +3.5 | -33.3 | TIRO3 (-23 punti per la casa); SENSO_UNICO |
| 2026-01-05 | NYK @ DET | 90-121 | +31 | -2.1 | -1.5 | +33.1 | TIRO3 (+8 punti per la casa); SENSO_UNICO |
| 2026-03-11 | HOU @ DEN | 93-129 | +36 | +3.0 | +6.5 | +33.0 | TIRO3 (+40 punti per la casa); LIBERI (+5 punti per la casa); MERCATO (linea -6.5); SENSO_UNICO |
| 2026-04-12 | PHX @ OKC | 135-103 | -32 | +0.9 | +7.5 | -32.9 | TIRO3 (-11 punti per la casa); RIENTRO PHX: CJ Huntley; SENSO_UNICO |
| 2026-03-07 | ORL @ MIN | 119-92 | -27 | +5.9 | +6.5 | -32.9 | TIRO3 (-6 punti per la casa); SENSO_UNICO |
| 2026-03-03 | SAS @ PHI | 131-91 | -40 | -7.5 | -7.5 | -32.5 | TIRO3 (-21 punti per la casa); SENSO_UNICO |
| 2026-02-04 | CLE @ LAC | 124-91 | -33 | -1.3 | -2.5 | -31.7 | TIRO3 (-16 punti per la casa); ASSENZA LAC: James Harden; SENSO_UNICO |
| 2025-12-30 | SAC @ LAC | 90-131 | +41 | +9.5 | +9.5 | +31.5 | SENSO_UNICO |
| 2026-01-10 | MIA @ IND | 99-123 | +24 | -6.6 | -6.5 | +30.6 | TIRO3 (+28 punti per la casa) |
| 2025-11-25 | ATL @ WAS | 113-132 | +19 | -11.3 | -10.5 | +30.3 | TIRO3 (+17 punti per la casa) |
| 2025-12-05 | CHA @ TOR | 111-86 | -25 | +5.3 | +6.5 | -30.3 | RIENTRO CHA: KJ Simpson; SENSO_UNICO |
| 2025-11-13 | IND @ PHX | 98-133 | +35 | +4.9 | +3.5 | +30.1 | TIRO3 (+7 punti per la casa); SENSO_UNICO |
| 2026-01-28 | NYK @ TOR | 119-92 | -27 | +3.1 | +1.5 | -30.1 | TIRO3 (-8 punti per la casa); SENSO_UNICO |
| 2026-02-12 | MIL @ OKC | 110-93 | -17 | +13.0 | +13.5 | -30.0 | TIRO3 (-9 punti per la casa) |
| 2026-01-13 | ATL @ LAL | 116-141 | +25 | -5.0 | +1.5 | +30.0 | TIRO3 (+31 punti per la casa); MERCATO (linea -1.5); SENSO_UNICO |
| 2026-01-25 | GSW @ MIN | 111-85 | -26 | +3.6 | +5.5 | -29.6 | LIBERI (-6 punti per la casa); SENSO_UNICO |
| 2025-12-27 | UTA @ SAS | 127-114 | -13 | +16.5 | +14.5 | -29.5 | TIRO3 (-29 punti per la casa) |
| 2025-12-14 | WAS @ IND | 108-89 | -19 | +10.5 | +10.5 | -29.5 | TIRO3 (-12 punti per la casa) |
| 2026-01-03 | BOS @ LAC | 146-115 | -31 | -1.6 | +1.5 | -29.4 | TIRO3 (-13 punti per la casa); SENSO_UNICO |
| 2026-01-19 | DAL @ NYK | 114-97 | -17 | +12.3 | +12.5 | -29.3 | TIRO3 (-17 punti per la casa) |
| 2025-12-29 | MIN @ CHI | 136-101 | -35 | -5.9 | -6.5 | -29.1 | TIRO3 (-7 punti per la casa); SENSO_UNICO |
| 2026-01-22 | CHA @ ORL | 124-97 | -27 | +2.0 | +3.5 | -29.0 | TIRO3 (-10 punti per la casa); SENSO_UNICO |
| 2025-11-12 | MEM @ BOS | 95-131 | +36 | +7.1 | +8.5 | +28.9 | TIRO3 (+24 punti per la casa); SENSO_UNICO |
| 2026-01-25 | BKN @ LAC | 89-126 | +37 | +8.2 | +10.5 | +28.8 | TIRO3 (+28 punti per la casa); SENSO_UNICO |
