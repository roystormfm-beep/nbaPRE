# Fase 2 — baseline contro mercato

Intervalli di confidenza al 95% da bootstrap appaiato sulle partite (2.000 ricampionamenti).
Differenza = modello − mercato: positiva vuol dire che il mercato è più preciso.
CLV: lato scelto dal modello confrontandosi con la linea d'apertura; punti guadagnati rispetto alla chiusura (solo stagioni con apertura: 2014-15 → 2016-17 e 2023-24 → 2025-26).

### Modello v2 della pagina, parametri attuali

| Assenze | Periodo | Partite | Errore medio scarto: modello / mercato | Differenza [IC 95%] | Brier: modello / mercato | Differenza [IC 95%] | Log loss: modello / mercato | Calibrazione (ECE): modello / mercato | Vincitori: modello / mercato | Errore medio totale: modello / mercato | Contro lo spread (IC 95%) | ROI a -110 (IC 95%) | CLV in punti (IC 95%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| senza assenze | sviluppo 2014-15 → 2024-25 | 13091 | 10,30 / 9,93 | 0,37 [0,32; 0,42] | 0,2137 / 0,2049 | 0,0088 [0,0072; 0,0103] | 0,6161 / 0,5954 | 0,018 / 0,007 | 65,9% / 68,1% | 14,64 / 14,13 | 50,1% [49,3; 51,0] | -4,3% [-5,9; -2,7] | 0,34 [0,29; 0,40] |
| senza assenze | test 2025-26 | 1230 | 11,28 / 10,88 | 0,41 [0,22; 0,60] | 0,2013 / 0,1947 | 0,0066 [0,0016; 0,0118] | 0,5892 / 0,5707 | 0,030 / 0,026 | 69,1% / 69,3% | 15,08 / 14,58 | 49,3% [46,6; 52,2] | -5,8% [-10,9; -0,7] | 0,15 [0,03; 0,27] |
| assenze "chi ha giocato" (ottimistico) | sviluppo 2014-15 → 2024-25 | 13091 | 10,14 / 9,93 | 0,21 [0,17; 0,25] | 0,2093 / 0,2049 | 0,0044 [0,0033; 0,0055] | 0,6058 / 0,5954 | 0,015 / 0,007 | 66,8% / 68,1% | 14,64 / 14,13 | 50,2% [49,3; 51,1] | -4,1% [-5,8; -2,4] | 0,81 [0,76; 0,86] |
| assenze "chi ha giocato" (ottimistico) | test 2025-26 | 1230 | 10,93 / 10,88 | 0,05 [-0,08; 0,19] | 0,1952 / 0,1947 | 0,0005 [-0,0026; 0,0035] | 0,5732 / 0,5707 | 0,028 / 0,026 | 71,1% / 69,3% | 15,08 / 14,58 | 50,8% [48,0; 53,7] | -3,0% [-8,3; 2,3] | 0,81 [0,70; 0,92] |

### Per stagione (errore medio sullo scarto)

| Stagione | Partite | Mercato: errore medio | Modello senza assenze | Differenza [IC 95%] | Modello "chi ha giocato" | Differenza [IC 95%] |
|---|---|---|---|---|---|---|
| 2014-15 | 1157 | 9,05 | 9,47 | 0,41 [0,22; 0,59] | 9,32 | 0,27 [0,11; 0,41] |
| 2015-16 | 1230 | 9,08 | 9,29 | 0,22 [0,06; 0,37] | 9,23 | 0,15 [0,03; 0,28] |
| 2016-17 | 1186 | 9,71 | 9,99 | 0,28 [0,11; 0,44] | 9,91 | 0,19 [0,05; 0,32] |
| 2017-18 | 1230 | 9,45 | 9,91 | 0,46 [0,31; 0,61] | 9,77 | 0,32 [0,20; 0,44] |
| 2018-19 | 1230 | 9,93 | 10,23 | 0,30 [0,14; 0,45] | 10,09 | 0,16 [0,05; 0,27] |
| 2019-20 | 1059 | 9,91 | 10,10 | 0,19 [0,02; 0,37] | 10,03 | 0,12 [-0,02; 0,25] |
| 2020-21 | 1080 | 10,71 | 11,16 | 0,45 [0,25; 0,63] | 10,83 | 0,12 [-0,02; 0,26] |
| 2021-22 | 1230 | 10,64 | 11,12 | 0,48 [0,30; 0,66] | 10,90 | 0,26 [0,13; 0,38] |
| 2022-23 | 1230 | 9,76 | 10,18 | 0,42 [0,23; 0,62] | 10,01 | 0,25 [0,11; 0,39] |
| 2023-24 | 1230 | 10,54 | 10,95 | 0,42 [0,24; 0,59] | 10,74 | 0,20 [0,07; 0,34] |
| 2024-25 | 1229 | 10,51 | 10,95 | 0,44 [0,26; 0,64] | 10,74 | 0,23 [0,09; 0,37] |
| 2025-26 | 1230 | 10,88 | 11,28 | 0,41 [0,22; 0,60] | 10,93 | 0,05 [-0,08; 0,19] |

### Modello v2 ritarato sulle sole stagioni di sviluppo

| Assenze | Periodo | Partite | Errore medio scarto: modello / mercato | Differenza [IC 95%] | Brier: modello / mercato | Differenza [IC 95%] | Log loss: modello / mercato | Calibrazione (ECE): modello / mercato | Vincitori: modello / mercato | Errore medio totale: modello / mercato | Contro lo spread (IC 95%) | ROI a -110 (IC 95%) | CLV in punti (IC 95%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| senza assenze | sviluppo 2014-15 → 2024-25 | 13091 | 10,28 / 9,93 | 0,35 [0,30; 0,40] | 0,2132 / 0,2049 | 0,0083 [0,0069; 0,0098] | 0,6145 / 0,5954 | 0,008 / 0,007 | 66,1% / 68,1% | 14,68 / 14,13 | 49,6% [48,7; 50,5] | -5,3% [-7,0; -3,7] | 0,31 [0,25; 0,36] |
| senza assenze | test 2025-26 | 1230 | 11,36 / 10,88 | 0,48 [0,28; 0,68] | 0,2018 / 0,1947 | 0,0071 [0,0024; 0,0118] | 0,5899 / 0,5707 | 0,039 / 0,026 | 69,7% / 69,3% | 15,11 / 14,58 | 48,8% [46,0; 51,5] | -6,9% [-12,3; -1,6] | 0,14 [0,01; 0,26] |
| assenze "chi ha giocato" (ottimistico) | sviluppo 2014-15 → 2024-25 | 13091 | 10,12 / 9,93 | 0,18 [0,15; 0,22] | 0,2091 / 0,2049 | 0,0041 [0,0031; 0,0052] | 0,6051 / 0,5954 | 0,008 / 0,007 | 67,1% / 68,1% | 14,68 / 14,13 | 50,2% [49,3; 51,0] | -4,2% [-5,9; -2,6] | 0,80 [0,75; 0,85] |
| assenze "chi ha giocato" (ottimistico) | test 2025-26 | 1230 | 10,98 / 10,88 | 0,10 [-0,03; 0,25] | 0,1962 / 0,1947 | 0,0016 [-0,0019; 0,0047] | 0,5750 / 0,5707 | 0,038 / 0,026 | 70,1% / 69,3% | 15,11 / 14,58 | 51,3% [48,5; 54,1] | -2,1% [-7,3; 3,7] | 0,79 [0,67; 0,90] |
