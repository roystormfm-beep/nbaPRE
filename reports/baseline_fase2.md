# Fase 2 — baseline contro mercato

Intervalli di confidenza al 95% da bootstrap appaiato sulle partite (2.000 ricampionamenti).
Differenza = modello − mercato: positiva vuol dire che il mercato è più preciso.
CLV: lato scelto dal modello confrontandosi con la linea d'apertura; punti guadagnati rispetto alla chiusura (solo stagioni con apertura: 2014-15 → 2016-17 e 2023-24 → 2025-26).

### Modello v2 della pagina, parametri attuali

| Assenze | Periodo | Partite | Errore medio scarto: modello / mercato | Differenza [IC 95%] | Brier: modello / mercato | Differenza [IC 95%] | Log loss: modello / mercato | Calibrazione (ECE): modello / mercato | Vincitori: modello / mercato | Errore medio totale: modello / mercato | Contro lo spread (IC 95%) | ROI a -110 (IC 95%) | CLV in punti (IC 95%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| senza assenze | sviluppo 2014-15 → 2024-25 | 13091 | 10,32 / 9,93 | 0,39 [0,34; 0,44] | 0,2146 / 0,2049 | 0,0097 [0,0082; 0,0113] | 0,6182 / 0,5954 | 0,020 / 0,007 | 65,7% / 68,1% | 14,64 / 14,13 | 50,1% [49,3; 51,0] | -4,3% [-6,0; -2,6] | 0,34 [0,29; 0,40] |
| senza assenze | test 2025-26 | 1230 | 11,38 / 10,88 | 0,51 [0,32; 0,70] | 0,2038 / 0,1947 | 0,0091 [0,0040; 0,0140] | 0,5941 / 0,5707 | 0,014 / 0,026 | 68,4% / 69,3% | 15,08 / 14,58 | 47,9% [45,1; 50,7] | -8,6% [-13,9; -3,5] | 0,19 [0,07; 0,31] |
| assenze "chi ha giocato" (ottimistico) | sviluppo 2014-15 → 2024-25 | 13091 | 10,16 / 9,93 | 0,23 [0,19; 0,27] | 0,2103 / 0,2049 | 0,0053 [0,0042; 0,0065] | 0,6080 / 0,5954 | 0,018 / 0,007 | 66,7% / 68,1% | 14,64 / 14,13 | 49,9% [49,0; 50,8] | -4,8% [-6,4; -3,0] | 0,79 [0,73; 0,84] |
| assenze "chi ha giocato" (ottimistico) | test 2025-26 | 1230 | 11,02 / 10,88 | 0,14 [0,00; 0,28] | 0,1977 / 0,1947 | 0,0030 [-0,0005; 0,0063] | 0,5784 / 0,5707 | 0,022 / 0,026 | 70,2% / 69,3% | 15,08 / 14,58 | 51,2% [48,5; 53,9] | -2,2% [-7,5; 3,1] | 0,78 [0,66; 0,89] |

### Per stagione (errore medio sullo scarto)

| Stagione | Partite | Mercato: errore medio | Modello senza assenze | Differenza [IC 95%] | Modello "chi ha giocato" | Differenza [IC 95%] |
|---|---|---|---|---|---|---|
| 2014-15 | 1157 | 9,05 | 9,44 | 0,38 [0,19; 0,56] | 9,30 | 0,24 [0,08; 0,38] |
| 2015-16 | 1230 | 9,08 | 9,32 | 0,24 [0,08; 0,40] | 9,25 | 0,18 [0,05; 0,30] |
| 2016-17 | 1186 | 9,71 | 10,00 | 0,29 [0,12; 0,45] | 9,92 | 0,20 [0,06; 0,34] |
| 2017-18 | 1230 | 9,45 | 9,91 | 0,47 [0,31; 0,62] | 9,77 | 0,33 [0,20; 0,45] |
| 2018-19 | 1230 | 9,93 | 10,24 | 0,31 [0,15; 0,47] | 10,12 | 0,19 [0,07; 0,30] |
| 2019-20 | 1059 | 9,91 | 10,12 | 0,21 [0,01; 0,40] | 10,04 | 0,13 [-0,01; 0,28] |
| 2020-21 | 1080 | 10,71 | 11,21 | 0,50 [0,28; 0,70] | 10,88 | 0,17 [0,02; 0,33] |
| 2021-22 | 1230 | 10,64 | 11,12 | 0,49 [0,29; 0,67] | 10,91 | 0,28 [0,14; 0,41] |
| 2022-23 | 1230 | 9,76 | 10,21 | 0,45 [0,24; 0,66] | 10,04 | 0,28 [0,13; 0,44] |
| 2023-24 | 1230 | 10,54 | 11,05 | 0,51 [0,31; 0,71] | 10,81 | 0,28 [0,13; 0,43] |
| 2024-25 | 1229 | 10,51 | 10,96 | 0,45 [0,27; 0,65] | 10,76 | 0,25 [0,10; 0,39] |
| 2025-26 | 1230 | 10,88 | 11,38 | 0,51 [0,32; 0,70] | 11,02 | 0,14 [0,00; 0,28] |

### Modello v2 ritarato sulle sole stagioni di sviluppo

| Assenze | Periodo | Partite | Errore medio scarto: modello / mercato | Differenza [IC 95%] | Brier: modello / mercato | Differenza [IC 95%] | Log loss: modello / mercato | Calibrazione (ECE): modello / mercato | Vincitori: modello / mercato | Errore medio totale: modello / mercato | Contro lo spread (IC 95%) | ROI a -110 (IC 95%) | CLV in punti (IC 95%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| senza assenze | sviluppo 2014-15 → 2024-25 | 13091 | 10,29 / 9,93 | 0,35 [0,30; 0,40] | 0,2138 / 0,2049 | 0,0089 [0,0075; 0,0103] | 0,6157 / 0,5954 | 0,009 / 0,007 | 65,9% / 68,1% | 14,68 / 14,13 | 49,8% [48,9; 50,7] | -4,9% [-6,6; -3,3] | 0,33 [0,27; 0,38] |
| senza assenze | test 2025-26 | 1230 | 11,38 / 10,88 | 0,50 [0,31; 0,70] | 0,2030 / 0,1947 | 0,0083 [0,0037; 0,0131] | 0,5924 / 0,5707 | 0,027 / 0,026 | 68,8% / 69,3% | 15,11 / 14,58 | 48,3% [45,4; 51,1] | -7,8% [-13,3; -2,7] | 0,16 [0,03; 0,28] |
| assenze "chi ha giocato" (ottimistico) | sviluppo 2014-15 → 2024-25 | 13091 | 10,12 / 9,93 | 0,19 [0,15; 0,22] | 0,2095 / 0,2049 | 0,0046 [0,0035; 0,0057] | 0,6061 / 0,5954 | 0,008 / 0,007 | 67,0% / 68,1% | 14,68 / 14,13 | 50,0% [49,1; 50,8] | -4,6% [-6,2; -2,9] | 0,81 [0,76; 0,86] |
| assenze "chi ha giocato" (ottimistico) | test 2025-26 | 1230 | 10,99 / 10,88 | 0,12 [-0,02; 0,26] | 0,1972 / 0,1947 | 0,0025 [-0,0009; 0,0057] | 0,5772 / 0,5707 | 0,035 / 0,026 | 69,7% / 69,3% | 15,11 / 14,58 | 50,5% [47,6; 53,3] | -3,6% [-9,2; 1,8] | 0,84 [0,73; 0,95] |
