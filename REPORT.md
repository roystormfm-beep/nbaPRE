# REPORT — Fase 0: ricognizione

*23 novembre 2026. Fase completata: mi fermo qui e aspetto il tuo via libera per la fase 1.*

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
