# REPORT

Diario delle fasi, la più recente in cima.

---

# Fase 3: giocatori, minuti, disponibilità — completata

*23 novembre 2026, sera. Mi fermo qui e aspetto il tuo via libera per la fase 4.*

## In sintesi

- **Ho un archivio degli injury report ufficiali dal 2018-19 a oggi.** Per ogni partita c'è l'ultimo report pubblicato prima della palla a due, letto e trasformato in tabella: oltre 75.000 righe pre-partita tra il 2018-19 e il 2024-25. Il 2018-19 parte da metà dicembre, perché prima l'archivio non esiste.
- **Il nuovo modello "giocatori" batte il baseline ad armi pari.** Entrambi usano le stesse informazioni prima della partita, cioè risultati passati più l'injury report. Sulle 7.747 partite di sviluppo con report (2018-19 → 2024-25) l'errore medio sullo scarto è 10,46 contro 10,56 del baseline e 10,28 del mercato.
- **Il distacco dal mercato scende da 0,28 a 0,17 punti a partita.** Con l'intervallo di confidenza [0,12; 0,23] resta significativo: il mercato è ancora più preciso, ma la distanza si è ridotta di circa il 40%.
- **Il nuovo modello, con le sole informazioni disponibili prima della partita, arriva allo stesso livello del baseline che sa in anticipo chi gioca:** 10,46 contro 10,45.
- **La stagione di test 2025-26 non l'ho toccata**, come previsto dal protocollo: il confronto sul test si fa solo a fine fase 5.

## Confronto sulle stagioni di sviluppo con injury report (2018-19 → 2024-25, 7.747 partite)

| Modello | Errore medio sullo scarto | Distacco dal mercato [IC 95%] | Brier |
|---|---|---|---|
| Baseline senza assenze | 10,66 | +0,38 [0,31; 0,45] | 0,2162 |
| Baseline con injury report | 10,56 | +0,28 [0,22; 0,34] | 0,2138 |
| Giocatori + minuti, senza injury report | 10,58 | +0,30 [0,23; 0,36] | 0,2137 |
| **Giocatori + minuti, con injury report** | **10,46** | **+0,17 [0,12; 0,23]** | **0,2107** |
| Miscela 50/50 dei due modelli con report | 10,44 | +0,16 [0,11; 0,21] | 0,2105 |
| *Baseline che sa chi gioca (ottimistico)* | *10,45* | *+0,17* | *0,2109* |
| Mercato (chiusura) | 10,28 | — | 0,2066 |

Per stagione, il modello giocatori con report batte il baseline con report in tutte e 7 le stagioni, e la miscela dei due fa ancora un po' meglio in 5 stagioni su 7. Tabelle complete in `reports/fase3.md`.

## Come funziona

1. **Rating dei giocatori per possesso (RAPM).** Per ogni tratto di gioco con gli stessi 10 giocatori in campo si stimano un rating d'attacco e uno di difesa per giocatore. Le osservazioni sono pesate per i possessi e per quanto sono recenti (emivita 180 giorni, finestra di oltre due anni). Si parte da un prior: il BPM offensivo e difensivo della stagione precedente, aggiornato con il box score della stagione in corso. La stima si rifà ogni 7 giorni con i soli dati precedenti.
2. **Minuti attesi** per ogni giocatore: media recente dei minuti giocati, per la probabilità che scenda in campo, riscalata a 240 minuti di squadra. I minuti di chi manca si redistribuiscono e nessuno supera i 42. Errore medio per giocatore e partita: 4,8 minuti con l'injury report, 5,9 senza.
3. **Probabilità di giocare per stato del report**, stimata solo sulle stagioni precedenti:

| Stato nel report | Righe | Ha giocato |
|---|---|---|
| Out | 60.606 | 0,1% |
| Doubtful | 574 | 2,4% |
| Questionable | 3.348 | 53% |
| Probable | 1.693 | 90% |
| Available | 9.520 | 83% (spesso giocatori della G League richiamati: per loro si usa la partecipazione recente) |

4. **Forza della squadra in partita** = somma dei rating dei giocatori pesata per i minuti attesi, più il vantaggio campo stimato dai dati.

## Prove e scelte (ablation, su 4 stagioni di sviluppo)

| Scelta | Effetto sull'errore medio | Decisione |
|---|---|---|
| Correzione per la fortuna al tiro (tiri da tre e liberi alla media di squadra) | peggiora di 0,03 | **non usata** in questa forma |
| Prior aggiornato con il box score della stagione | migliora di 0,02 | usata |
| Componente di squadra dentro il RAPM | nessun effetto | tenuta (innocua) |
| Correzione di squadra dai risultati recenti | peggiora di 0,04-0,20 | non usata: ci pensa l'ensemble della fase 5 |
| Forza della regolarizzazione (1.500 / 3.000 / 6.000 / 12.000) | 3.000 è la migliore | 3.000 |
| Emivita (90 / 180 / 365 / 730 giorni) | 180 e 365 equivalenti | 180 |

- **Riposo non annunciato.** Il prompt chiedeva un modello della probabilità di riposo nei back-to-back. I dati dicono che non serve: un giocatore di rotazione che non compare nell'injury report salta la partita solo nell'1% dei casi circa (2,7% nel 2018-19, 0,6-1,4% dal 2019-20), e nei back-to-back la quota sale al massimo di un punto. I riposi vengono quasi sempre dichiarati nel report.
- **I "minuti giocati davvero" non sono un buon limite superiore.** Dipendono dal punteggio: nelle partite a senso unico giocano le riserve. Per questo quella versione sbaglia più di quella con i minuti attesi (10,52 contro 10,46).

## Cosa resta debole

- **Il totale dei punti.** Il modello giocatori sbaglia il totale di 15,6 punti in media, contro 14,8 del baseline e 14,3 del mercato, perché non stima il ritmo delle singole squadre. È il lavoro della fase 4 (ritmo, arbitri).
- **Il contesto:** riposo, viaggi, fusi orari, altitudine, vantaggio campo per squadra. Il calendario è già pronto dalla fase 1 ma non è ancora usato dal modello: fase 4.
- **Due approssimazioni nell'archivio:**
  - i report "orari" fino al 2024-25 escono in realtà alla mezz'ora (il file "06PM" è il report delle 18:30), quindi a volte il report usato è di 30 minuti prima della palla a due invece dei 45 previsti;
  - nel 2018-19 i report mancano fino a metà dicembre.

## Correzioni fatte in questa fase

- **Codifica dei nomi** di Basketball-Reference (vedi la nota nella fase 2): numeri del baseline rifatti.
- **Lettore dei PDF:** il formato dei report è cambiato tre volte (2018-19 → 2020-21 con "Category" e "Previous Status", poi 7 colonne con spazi, poi 7 colonne senza spazi). Il lettore riconosce tutti e tre i formati ed è verificato da un test su 17 report di esempio dal 2018 al 2026.

## Prossimo passo: fase 4 (contesto e totali)

1. Vantaggio campo per stagione e per squadra (con shrinkage), riposo, viaggi, fusi orari, altitudine, calendario fitto, partite senza obiettivi a fine stagione.
2. Ritmo delle squadre e arbitri per stimare i possessi, quindi totale e scarto coerenti tra loro.
3. Misura di quanto ogni elemento migliora il modello, sempre sulle stagioni di sviluppo.

---

# Fase 2: baseline — completata (numeri corretti il 23/11 sera)

*23 novembre 2026.*

> **Correzione.** Nella prima versione di questa fase i nomi con accenti scaricati da Basketball-Reference erano stati letti con la codifica sbagliata (per esempio "JokiÄ‡" invece di "Jokić"). Per circa 27 giocatori a stagione il modello non trovava quindi il BPM della stagione precedente, e fra questi c'erano Jokić, Dončić, Vučević e Şengün. Ho corretto la lettura e rifatto backtest e ritaratura. I numeri qui sotto sono quelli corretti: il baseline migliora di circa 0,1 punti per partita.

## In sintesi

- **Il modello della pagina è stato riscritto in Python senza differenze.** Sugli stessi dati, Python e JavaScript danno gli stessi rating, punti, probabilità e correzioni per le assenze, con scarti dell'ordine di 0,0000000000001 punti. Il confronto copre 101 partite con i dati della pagina e 3 giornate storiche, ed è un test automatico.
- **Backtest giorno per giorno su tutte le 14.439 partite dal 2014-15 al 2025-26.** Ogni pronostico usa solo quello che si sapeva la mattina della partita, e un test automatico lo verifica.
- **Il mercato è più preciso del baseline in tutte e 12 le stagioni.** Nel 2025-26 la linea di chiusura sbaglia lo scarto di 10,88 punti in media. Il baseline sbaglia di 11,28 senza considerare le assenze e di 10,93 se sa in anticipo chi scende in campo.

## I numeri da battere (stagione di test 2025-26, 1.230 partite)

| | Baseline senza assenze | Baseline che sa chi gioca (ottimistico) | Mercato (chiusura) |
|---|---|---|---|
| Errore medio sullo scarto | 11,28 | 10,93 | **10,88** |
| Errore quadratico medio sullo scarto (RMSE) | 14,42 | 14,00 | **13,92** |
| Errore medio sul totale | 15,08 | 15,08 | **14,58** |
| Brier (probabilità di vittoria) | 0,2013 | 0,1952 | **0,1947** |
| Log loss | 0,589 | 0,573 | 0,571 |
| Calibrazione (ECE, più basso è meglio) | 0,030 | 0,028 | 0,026 |
| Vincitori indovinati | 69,1% | 71,1% | 69,3% |
| Contro lo spread di chiusura | 49,3% [46,6; 52,2] | 50,8% [48,0; 53,7] | — |
| ROI a -110 | -5,8% [-10,9; -0,7] | -3,0% [-8,3; +2,3] | — |

Differenze con il mercato, con intervallo di confidenza al 95% (bootstrap appaiato; positivo = il mercato è più preciso):
- **Senza assenze:** errore medio +0,41 [0,22; 0,60]; Brier +0,007 [0,002; 0,012]. Il mercato è più preciso con margine sicuro.
- **Sapendo chi gioca:** errore medio +0,05 [-0,08; +0,19]; Brier +0,0005 [-0,003; +0,004]. Differenza non significativa: con l'informazione perfetta sulle presenze il baseline è alla pari del mercato. Quell'informazione però prima della palla a due non c'è, e la fase 3 misura quanta se ne può avere davvero.

## Per stagione (errore medio sullo scarto)

| Stagione | Mercato | Baseline senza assenze | Baseline che sa chi gioca |
|---|---|---|---|
| 2014-15 | 9,05 | 9,47 | 9,32 |
| 2015-16 | 9,08 | 9,29 | 9,23 |
| 2016-17 | 9,71 | 9,99 | 9,91 |
| 2017-18 | 9,45 | 9,91 | 9,77 |
| 2018-19 | 9,93 | 10,23 | 10,09 |
| 2019-20 | 9,91 | 10,10 | 10,03 |
| 2020-21 | 10,71 | 11,16 | 10,83 |
| 2021-22 | 10,64 | 11,12 | 10,90 |
| 2022-23 | 9,76 | 10,18 | 10,01 |
| 2023-24 | 10,54 | 10,95 | 10,74 |
| 2024-25 | 10,51 | 10,95 | 10,74 |
| 2025-26 | 10,88 | 11,28 | 10,93 |

Il distacco senza assenze passa da circa 0,3 punti (2014-15 → 2019-20) a circa 0,4-0,5 (dal 2020-21): nelle stagioni recenti le assenze contano di più. Intervalli di confidenza per stagione in `reports/baseline_fase2.md`.

## Ritaratura sulle sole stagioni di sviluppo

Alcuni parametri del modello v2 erano stati tarati sul 2025-26, che qui è la stagione di test. Per un confronto pulito ho ritarato il baseline solo sul periodo 2014-15 → 2024-25, un parametro alla volta.

| Parametro | Pagina | Ritarato |
|---|---|---|
| Emivita dei risultati | 30 giorni | 60 giorni |
| Peso del rating di partenza dai roster | 1,25 | 0,75 |
| Peso delle assenze | 0,6 | 0,8 |
| Soglia degli scarti contati a metà | 20 | 15 |
| Deviazione standard di una partita | 10,5 | 10,25 |

Sulle stagioni di sviluppo il baseline ritarato è un po' più preciso (10,12 contro 10,14 con le assenze; 10,28 contro 10,30 senza). Sul test fa un po' peggio della pagina (10,98 contro 10,93; 11,36 contro 11,28). Il timore che la taratura sul 2025-26 gonfiasse i numeri della pagina era quindi fondato, ma l'effetto è piccolo. Dalla fase 3 in poi il riferimento pulito è il baseline ritarato.

## Approssimazioni dichiarate

- **BPM della stagione in corso:** nel passato si usa la stima dal box score già prevista nel modello. Sui dati attuali della pagina il pronostico cambia di 0,11 punti in media (massimo 0,76).
- **Assenze:** due versioni, nessuna correzione oppure "chi ha giocato" (ottimistica). Dalla fase 3 c'è anche la versione con l'injury report vero.
- **Test di equivalenza:** fatto sugli stessi ingressi, perché il registro della pagina salva solo i pronostici e non i dati di quel momento.
- **Partite senza linea:** 118 (73 nel 2014-15, 44 nel 2016-17, una nel 2024-25), escluse dal confronto.

## Un segnale da approfondire (non un vantaggio)

Senza assenze, il baseline sceglie spesso il lato verso cui la linea si sposta tra apertura e chiusura: in media 0,34 punti nello sviluppo e 0,15 nel test, con intervalli che escludono lo zero. Alla chiusura però il vantaggio sparisce. Ci torno in fase 5.

## Dal vivo 2026-27 (registro della pagina)

Sulle 26 partite congelate prima della palla a due (19-22 novembre): errore medio 7,60 punti contro 7,04 del mercato, 20 vincitori su 26 come il mercato. Il campione è troppo piccolo per conclusioni.

## Come rifarlo

`nba backtest` (circa 2 minuti; con `--retune` anche la ritaratura, circa 10 minuti), poi `nba report`. `uv run pytest` lancia i test.

---

# Fase 1: ingestione storica — completata

*23 novembre 2026. Decisioni prese da te: repository `roystormfm-beep/nbaPRE`, quote gratuite ESPN, baseline = modello attuale della pagina (v2). Mi fermo qui e aspetto il tuo via libera per la fase 2.*

## In sintesi

- **12 stagioni pronte e controllate** (2014-15 → 2025-26): 14.439 partite, 444.068 stint (tratti di gioco con gli stessi 10 giocatori in campo), 307.057 righe giocatore-partita, 1.632 giocatori.
- **Punteggi finali verificati:** per tutte le 14.439 partite concordano almeno due fonti indipendenti, nel 99,8% dei casi tre o più (eventi, NBA Stats, cdn.nba.com, ESPN).
- **Quintetti in campo ricostruiti per il 99,99% del tempo di gioco.** Il play-by-play è utilizzabile per i quintetti in 14.412 partite su 14.439; le 27 escluse sono descritte più sotto.
- **Quote di mercato meglio del previsto:** linea di chiusura per il 99,6% delle partite (14.383) in **tutte** le 12 stagioni, non solo dal 2018-19 come stimato in fase 0. Linea d'apertura per 7.299 partite (2014-15 → 2016-17 e 2023-24 → 2025-26).
- **Il riferimento da battere ora ha un numero.** Sul 2025-26 (stagione di test) la linea di chiusura sbaglia lo scarto in media di **10,9 punti** e il totale di **14,6**; Brier score sulla vittoria **0,195**.

## Come è fatta

- `nba ingest --season 2025-26` (oppure `--all`) scarica il play-by-play e costruisce in `data/processed/` le tabelle `games_S`, `stints_S`, `player_games_S`, `lineup_issues_S` e `lines_S` (quote), più `schedule.parquet`. Se ci sono i dati ESPN li unisce da solo. Tempo: circa 4 minuti per 12 stagioni.
- `nba qc` rifà tutti i controlli e scrive `reports/qc_fase1.md` e `reports/qc_fase1.json`.
- `nba fetch-remote --task probe|espn|bref|all` raccoglie i dati esterni. Gira su GitHub Actions (workflow `fetch-remote`), salva in `data/external/` e fa il commit da solo. Il primo giro completo (circa 20.000 richieste) ha richiesto 10 minuti.
- Fonte degli eventi: NBA Stats v2 per 2014-15 → 2019-20, cdn.nba.com per 2020-21 → 2025-26.
- 6 test automatici (`uv run pytest`): ricostruzione dei quintetti su partite sintetiche e lettura dei formati ESPN e Basketball-Reference.

## Controlli di qualità

| Stagione | Partite | Play-by-play coerente col finale | Minuti di squadra corretti | Tempo con 5 contro 5 | Punti per squadra | Vittorie in casa | Dev. std. dello scarto |
|---|---|---|---|---|---|---|---|
| 2014-15 | 1.230 | 99,43% | 99,92% | 99,98% | 100,0 | 57,5% | 13,5 |
| 2015-16 | 1.230 | 99,43% | 99,84% | 99,96% | 102,7 | 58,9% | 13,3 |
| 2016-17 | 1.230 | 99,35% | 100% | 100% | 105,6 | 58,4% | 13,7 |
| 2017-18 | 1.230 | 100% | 100% | 100% | 106,3 | 57,9% | 13,7 |
| 2018-19 | 1.230 | 100% | 99,76% | 99,96% | 111,2 | 59,3% | 14,4 |
| 2019-20 | 1.059 | 99,72% | 99,91% | 99,98% | 111,8 | 55,1% | 14,1 |
| 2020-21 | 1.080 | 100% | 99,95% | 99,98% | 112,1 | 54,4% | 15,2 |
| 2021-22 | 1.230 | 100% | 100% | 100% | 110,6 | 54,4% | 15,3 |
| 2022-23 | 1.230 | 100% | 100% | 100% | 114,7 | 58,0% | 13,7 |
| 2023-24 | 1.230 | 100% | 100% | 100% | 114,2 | 54,3% | 15,6 |
| 2024-25 | 1.230 | 99,92% | 99,96% | 99,99% | 113,8 | 54,4% | 15,9 |
| 2025-26 | 1.230 | 99,92% | 100% | 100% | 115,6 | 55,4% | 16,4 |

Ogni squadra ha 82 partite (72 nel 2020-21; da 64 a 75 nel 2019-20, per l'interruzione Covid e la "bolla"). Nelle cinque stagioni coperte sia da NBA Stats sia da cdn.nba.com ho ricostruito tutto due volte: minuti per giocatore uguali entro un minuto nel 99,8-99,99% dei casi, punti nel 99,8-99,98%. Tabelle complete in `reports/qc_fase1.md`.

**Problemi trovati e corretti**
- **Righe ripetute** nell'archivio NBA Stats (118 solo nel 2017-18), che gonfiavano i punti: rimosse.
- **Sostituzioni registrate fuori sequenza** (un giocatore tira prima che la fonte lo faccia entrare). Creavano un sesto "titolare" e minuti contati due volte: in una partita di prova 7 minuti e mezzo. Ora gli eventi sono ordinati per cronometro, e chi entra più tardi senza essere mai uscito non conta come titolare.
- **Punteggio finale letto dall'ultima riga**, che a volte è un evento fuori sequenza con il punteggio vecchio: ora si usa il massimo.
- **Un errore mio.** Avevo trattato come incompleti i punteggi sotto i 150 punti totali, ma ESPN ha confermato che erano partite vere, per esempio Memphis-Charlotte 71-69 del 1° novembre 2014. Soglia abbassata a 120.

**Partite escluse dai quintetti (27, `pbp_ok = False`).** Il punteggio finale resta valido; non usarle serve a non attribuire punti sbagliati ai quintetti.
- In 24 partite il play-by-play ha un punto in meno del finale ufficiale (manca un tiro libero): 22 tra il 2014-15 e il 2016-17, una nel 2024-25 e una nel 2025-26.
- 3 partite della "bolla" 2020 non hanno eventi.

**Un dato da tenere d'occhio:** la deviazione standard dello scarto finale sale da 13,5 (2014-15) a 16,4 (2025-26). Le partite sono diventate più "larghe" e il modello dovrà tenerne conto quando stima l'incertezza (fase 5).

## Quote di mercato (ESPN)

| Stagione | Linea di chiusura | Linea d'apertura | Bookmaker (mediana) | Errore medio sullo scarto | Errore medio sul totale | Brier |
|---|---|---|---|---|---|---|
| 2014-15 | 96,8% | 96,7% | 5 | 9,07 | 13,43 | 0,194 |
| 2015-16 | 100% | 100% | 7 | 9,08 | 13,58 | 0,195 |
| 2016-17 | 98,7% | 97,2% | 10 | 9,73 | 13,68 | 0,212 |
| 2017-18 | 100% | — | 7 | 9,45 | 14,57 | 0,204 |
| 2018-19 | 100% | — | 7 | 9,93 | 14,50 | 0,204 |
| 2019-20 | 100% | — | 8 | 9,91 | 14,88 | 0,210 |
| 2020-21 | 100% | — | 11 | 10,71 | 14,37 | 0,214 |
| 2021-22 | 100% | — | 12 | 10,64 | 14,12 | 0,209 |
| 2022-23 | 100% | — | 13 | 9,76 | 14,16 | 0,216 |
| 2023-24 | 100% | 99,6% | 10 | 10,54 | 14,22 | 0,199 |
| 2024-25 | 99,9% | 99,9% | 1 | 10,51 | 14,11 | 0,199 |
| 2025-26 | 100% | 100% | 1 | 10,88 | 14,58 | 0,195 |

- **Come si calcola:**
  - la linea di chiusura è la mediana tra i bookmaker dell'ultima linea prima della partita salvata da ESPN;
  - la probabilità di vittoria è la mediana delle probabilità implicite nelle moneyline, tolto il margine del bookmaker;
  - sono escluse le linee "live" (durante la partita) e i siti di pronostici (teamrankings, numberfire, accuscore).
- **Limite:** dal 2024-25 ESPN salva un solo bookmaker (DraftKings). Sul periodo recente il riferimento è quindi una sola casa, non la media del mercato.
- **Valore rispetto alla chiusura (CLV):** si potrà misurare solo dove c'è l'apertura, cioè 2014-15 → 2016-17 e 2023-24 → 2025-26.

## Altri dati raccolti

- **Basketball-Reference:** statistiche avanzate (BPM, minuti) e medie per partita dal 2013-14 al 2026-27. Il BPM di fine stagione servirà come prior "stagione precedente", che è un'informazione disponibile prima che inizi la stagione successiva.
- **Archivio degli injury report ufficiali:** i PDF orari esistono almeno da gennaio 2019. Ho provato 12 date tra il 15/01/2019 e il 15/11/2025 e li ho trovati tutti. Quindi la disponibilità "con l'orario" si può ricostruire dal 2018-19 in poi; per le stagioni 2014-15 → 2017-18 servirà l'approssimazione dichiarata in fase 0. Per gennaio 2026 nessuno degli orari provati ha risposto: il formato del nome è cambiato, lo sistemo in fase 3.
- **Sedi neutre** (dati ESPN): Città del Messico, Parigi, Londra, Berlino, Las Vegas (semifinali e finale di Coppa) e la "bolla" di Orlando. Sono nel calendario con le coordinate giuste, e i viaggi verso l'Europa arrivano a 8.300 km e 7 fusi orari.

## Cosa cambia per le fasi successive

1. **Stagione in corso:** da GitHub Actions cdn.nba.com risponde 403 e stats.nba.com non risponde. Per il play-by-play del 2026-27 userò l'API di pbpstats (risponde: 248 partite al 22/11) oppure ESPN. Risolvo in fase 6.
2. **Il confronto con il mercato vale su tutte le 12 stagioni**, quindi anche la taratura (2014-15 → 2024-25) potrà essere misurata contro la linea.
3. **Privacy del repository:** `nbaPRE` è pubblico e ora contiene quote dei bookmaker e tabelle di Basketball-Reference. Consiglio di renderlo privato: i minuti gratuiti di GitHub Actions bastano ampiamente.

## Prossimo passo: fase 2 (baseline)

Riscrivo in Python il modello v2 della pagina e verifico che dia gli stessi numeri della versione JavaScript sulle partite già congelate. Poi lo misuro stagione per stagione accanto alla linea di chiusura: sono i numeri da battere.

---

# Fase 0: ricognizione

*23 novembre 2026. Fase completata.*

## In sintesi

- **Lo storico c'è ed è gratuito.** Il play-by-play di tutte le partite dal 2014-15 al 2025-26 si scarica da qui, sostituzioni comprese. Dalle sostituzioni si ricostruiscono i quintetti in campo, la base per i rating dei giocatori (RAPM).
- **Le quote storiche ci sono, gratis, dal 2018-19.** Le dà l'API di ESPN: per ogni partita la linea finale di uno o più bookmaker, con apertura e chiusura nelle stagioni recenti. Il confronto con il mercato si farà quindi dal 2018-19 al 2025-26.
- **Il vincolo vero è la rete.** Da questo ambiente cloud non si raggiungono i siti NBA, ESPN e Basketball-Reference. Stagione in corso, injury report, arbitri e quote devono arrivare da **GitHub Actions** (consigliato) o dal tuo computer.
- **Il baseline allegato non è quello che gira oggi.** La pagina usa una versione ricalibrata il 19/11 ed è quella che ho preso come baseline. È stata tarata sul 2025-26: su quella stagione i suoi numeri saranno ottimistici (vedi §2).

## 1. Fonti verificate

Prove fatte oggi dalla shell di questo ambiente e, dove la shell è bloccata, con una lettura web che dice solo se la fonte risponde.

| Fonte | A cosa serve | Shell | Lettura web | Esito e limiti |
|---|---|---|---|---|
| Dataset `shufinskiy/nba_data` su GitHub (licenza Apache 2.0) | Play-by-play storico | ✅ scaricato | — | NBA Stats v3 1996-97→2025-26, CDN NBA 2020-21→2025-26, pbpstats 2000-01→2024-25, matchup 2017-18→2025-26. Controllo sul 2025-26: 1.230 partite, 30 squadre × 82, ~124 sostituzioni a partita. **Qualità:** punteggio finale incompleto in 13 partite nella fonte NBA Stats v3 e in 1 nella fonte CDN; da incrociare con una terza fonte in fase 1. |
| stats.nba.com (`nba_api` 1.12.0 installato) | Box score avanzati, tracking, rotazioni | ❌ bloccato | non provata | Non indispensabile: lo storico è già nel dataset, la stagione in corso arriva da cdn.nba.com. Dai server cloud (GitHub Actions compreso) è spesso bloccato; dal tuo computer di solito funziona. |
| cdn.nba.com (liveData) | Play-by-play e box score 2026-27 | ❌ | ❌ errore del sito | Da provare al primo run di GitHub Actions. |
| API pbpstats.com | Possessi e stint 2026-27 | ❌ | ✅ 248 partite 2026-27 fino al 22/11 | Utilizzabile fuori da qui. |
| Basketball-Reference | BPM storico, controlli incrociati | ❌ | ✅ (già usato dalle attività pianificate della pagina) | Limite di frequenza delle richieste: solo poche pagine (BPM per stagione, verifiche). |
| Injury report ufficiale NBA (PDF) | Disponibilità con l'orario | ❌ | ✅ elenco dei PDF, più versioni al giorno (`Injury-Report_AAAA-MM-GG_HH_MMAM.pdf`) | Da verificare in fase 1 da quando esiste l'archivio storico. Dove manca: approssimazione dichiarata (§5). |
| Designazioni arbitrali (official.nba.com) | Ritmo e falli per i totali | ❌ | ✅ designazioni del 22/11 | Lo storico degli arbitri si ricava dalle box score. |
| API ESPN, quote per partita | Quote storiche e correnti | ❌ | ✅ | 2025-26: DraftKings con apertura, chiusura e linea attuale (es. ORL −4,5 → −5,5, totale 230,5 → 227,5). 2022-23: 16 fonti (bookmaker e siti di pronostici), solo linea finale. 2018-19: 9 fonti, solo linea finale. Circa 10.000 richieste per 8 stagioni. API non documentata: può cambiare senza preavviso. |
| The Odds API | Quote storiche (alternativa) | ❌ | — | A pagamento (da 30 $/mese). Storico da giugno 2020; ogni chiamata storica costa 10 crediti per mercato e per regione. Serve solo se le quote ESPN non bastano. |
| Archivio SportsbookReviewsOnline | Quote prima del 2018 | ❌ | ❌ | Non verificabile da qui; non necessario. |
| PyPI, raw.githubusercontent.com | Pacchetti, dataset | ✅ | — | Python 3.12.3 e `uv` pronti. |

## 2. Quale baseline

Il file allegato (`baseline_model_v1.js`) è la prima versione. La pagina oggi gira con una versione diversa, che ho estratto e salvato come `baseline_model.js`:

| Parametro | Allegato (v1) | Pagina (v2, dal 19/11) |
|---|---|---|
| Ridge `lambda` | 2 | 8 (verso un rating di partenza costruito dai roster) |
| Emivita | 60 giorni | 30 giorni |
| Forza del prior sul vantaggio campo | 40 | 200 |
| Deviazione standard di una partita | 11,5 | 10,5 |
| Soglia degli scarti contati a metà | 15 | 20 |
| Peso delle assenze | 0,8 | 0,6 |
| BPM di un sostituto | −2 | −3 |
| Novità | — | Prior dai roster con il BPM 2025/26 (peso 1,25); rientri senza partite stagionali valutati dall'anno scorso con rendimento ridotto (0,85); riposo in giorni |

I commenti della v2 dicono che peso delle assenze e sostituto sono stati **tarati sulle partite 2025-26**. Per questo in fase 2:
1. misuro la v2 così com'è, segnalando che sul 2025-26 è un risultato "in casa" e quindi ottimistico;
2. la ritaro sul periodo 2014-15→2024-25 e la rimisuro sul 2025-26, per un confronto pulito con il nuovo modello;
3. il confronto più pulito resta il dal vivo 2026-27: il registro della pagina ha già 26 pronostici congelati prima della partita (dal 19/11).

## 3. Dove far girare cosa

- **Questo ambiente:** sviluppo, backtest e modelli. 2 CPU e 7 GB di RAM bastano per il RAPM su 12 stagioni. I suoi file però non sopravvivono alla sessione.
- **Un tuo repository GitHub privato** (es. `nba-model`):
  - salva il codice e i dati elaborati tra una sessione e l'altra;
  - con GitHub Actions scarica la stagione in corso, le quote storiche ESPN (una tantum, richieste lente nell'arco di una notte), gli injury report e pubblica i pronostici due volte al giorno.
  - Con il piano gratuito di GitHub i minuti per i repository privati sono limitati, ma ampiamente sufficienti per questo uso.
- **Il tuo computer:** solo come riserva, se stats.nba.com servisse davvero.

## 4. Piano e tempi

| Fase | Cosa | Risultato | Sessioni di lavoro |
|---|---|---|---|
| 1. Ingestione storica | Play-by-play 2014-15→2025-26 in Parquet/DuckDB; partite, stint e box score per giocatore ricavati dal play-by-play; arene (coordinate, fusi, altitudine); quote ESPN 2018-19→2025-26; BPM storico. Controlli: punteggi incrociati su tre fonti, 240 minuti per squadra (+ supplementari), giocatori duplicati, partite mancanti. | Database pulito + rapporto di qualità | 2 + una notte di download |
| 2. Baseline | La v2 riscritta in Python; test di equivalenza con la versione JS sulle 26 partite congelate (differenza sotto 0,1 punti); misura dal 2018-19 al 2025-26 accanto alla linea di chiusura. | I numeri da battere | 1 |
| 3. Giocatori + minuti + disponibilità | RAPM per attacco e difesa con prior dal box score e decadimento nel tempo; correzione per la fortuna al tiro; proiezione dei minuti; modello del riposo nei back-to-back. | Forza di squadra partita per partita | 3 |
| 4. Contesto + totali | Riposo, viaggio, fusi, altitudine, vantaggio campo per squadra con shrinkage; ritmo e arbitri per i totali. | Scarto e totale coerenti | 2 |
| 5. Ensemble + calibrazione | Elo con margine, rating di squadra, LightGBM, pesi in walk-forward; distribuzione dello scarto; backtest completo, ablation, 50 partite peggiori. | Modello finale e report HTML | 2 |
| 6. Pipeline dal vivo | GitHub Actions, `predictions/latest.json` nel formato della pagina, confronto affiancato con il baseline. | Pronostici automatici | 1 + una settimana di rodaggio |

**Totale: circa 11 sessioni.** Con le tue approvazioni tra una fase e l'altra sono 4-5 settimane: il nuovo modello sarebbe dal vivo tra fine dicembre e inizio gennaio. Il giudizio sul dal vivo (almeno 500 partite) arriverebbe verso marzo; fino ad allora fa fede il backtest sul 2025-26.

## 5. Approssimazioni da dichiarare fin d'ora

- **Disponibilità nello storico.** Dove non c'è l'injury report con l'orario, l'unica stima è "chi ha giocato davvero". È un'informazione più completa di quella che si ha prima della palla a due (manca la sorpresa dell'ultimo minuto) e rende il backtest ottimistico. Lo misurerò sul periodo coperto dall'archivio.
- **Chiusura = ultima linea salvata da ESPN.** L'apertura c'è solo nelle stagioni recenti, quindi il valore rispetto alla chiusura (CLV) si potrà misurare solo lì.
- **Mercato di riferimento.** DraftKings e gli altri bookmaker USA non sono la linea più precisa (Pinnacle). Se servisse, c'è l'opzione a pagamento.
- **Uso dei dati.** Uso personale e non commerciale; i dati grezzi non vanno ripubblicati.

## 6. Cosa mi serve per la fase 1

1. **Repository:** crea un repository GitHub privato (es. `nba-model`) e dimmi il nome. Lo collego alla sessione e ci salvo il lavoro.
2. **Quote:** va bene partire con la via gratuita (ESPN)?
3. **Baseline:** confermi la versione attuale della pagina (v2) come riferimento da battere?

## File in questa cartella

- `PROMPT.md`: il prompt di lavoro
- `baseline_model.js`: modello attuale della pagina (v2)
- `baseline_model_v1.js`: modello allegato al prompt (v1)
- `recon/`: prove di raggiungibilità (`probe.sh`, `probe_shell.txt`), elenco dei dataset (`list_data.txt`)
