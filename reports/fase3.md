# Fase 3 — giocatori, minuti, disponibilità

Stagioni 2018-19 → 2024-25, 7747 partite con injury report e linea.

| Modello | Errore medio scarto | Differenza dal mercato [IC 95%] | RMSE | Brier | Differenza Brier [IC 95%] |
|---|---|---|---|---|---|
| Baseline senza assenze | 10,66 | 0,38 [0,31; 0,45] | 13,62 | 0,2162 | 0,0096 [0,0076; 0,0115] |
| Baseline con injury report | 10,60 | 0,31 [0,25; 0,37] | 13,55 | 0,2145 | 0,0079 [0,0062; 0,0096] |
| Giocatori + minuti, senza injury report | 10,58 | 0,30 [0,23; 0,36] | 13,50 | 0,2137 | 0,0072 [0,0053; 0,0090] |
| Giocatori + minuti con injury report | 10,47 | 0,18 [0,12; 0,24] | 13,36 | 0,2109 | 0,0043 [0,0028; 0,0059] |
| Miscela 50/50 (giocatori + baseline, injury report) | 10,46 | 0,17 [0,12; 0,23] | 13,37 | 0,2109 | 0,0043 [0,0029; 0,0058] |
| Baseline che sa chi gioca (ottimistico) | 10,45 | 0,17 [0,12; 0,22] | 13,38 | 0,2109 | 0,0043 [0,0029; 0,0056] |
| Giocatori con i minuti giocati davvero (ottimistico) | 10,52 | 0,24 [0,19; 0,29] | 13,43 | 0,2091 | 0,0026 [0,0012; 0,0040] |
| Mercato (linea di chiusura) | 10,28 | — [—; —] | 13,21 | 0,2066 | — [—; —] |

| Stagione | Partite | Mercato | Baseline senza | Baseline report | Giocatori senza report | Giocatori report | Miscela |
|---|---|---|---|---|---|---|---|
| 2018-19 | 787 | 9,69 | 10,04 | 10,30 | 9,89 | 9,89 | 10,01 |
| 2019-20 | 1041 | 9,92 | 10,03 | 10,05 | 10,10 | 10,01 | 9,98 |
| 2020-21 | 1063 | 10,73 | 11,17 | 11,13 | 11,03 | 10,87 | 10,92 |
| 2021-22 | 1214 | 10,61 | 11,09 | 10,92 | 10,96 | 10,82 | 10,80 |
| 2022-23 | 1214 | 9,78 | 10,16 | 10,03 | 10,10 | 9,98 | 9,92 |
| 2023-24 | 1215 | 10,56 | 10,98 | 10,89 | 10,85 | 10,75 | 10,74 |
| 2024-25 | 1213 | 10,52 | 10,93 | 10,74 | 10,89 | 10,74 | 10,67 |

Errore medio sul totale: mercato 14,28, baseline 14,80, giocatori 15,60.
