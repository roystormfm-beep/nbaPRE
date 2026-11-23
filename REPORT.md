# REPORT

Diario delle fasi, la più recente in cima.

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
