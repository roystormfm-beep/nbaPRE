# Prompt per Claude Code: modello predittivo NBA di livello professionale

> Come usarlo: crea una cartella vuota (o un repository GitHub), copiaci `baseline_model.js` (allegato a questo prompt), apri Claude Code nella cartella e incolla tutto il testo sotto la riga.

---

## Ruolo e obiettivo

Sei un data scientist esperto di modelli sportivi. Devi costruire con me un sistema di previsione delle partite NBA per la stagione 2026/27 che sia il più accurato possibile con dati pubblici e granulari: play-by-play, quintetti in campo, minuti, infortuni, calendario, arbitri e quote.

Per ogni partita il sistema deve produrre:
- punti attesi per le due squadre, scarto atteso (casa − trasferta) e totale;
- probabilità di vittoria **calibrata**;
- la distribuzione dello scarto (non solo la media), così da stimare la probabilità di coprire qualsiasi spread;
- una spiegazione leggibile: quali fattori spostano il pronostico e di quanto (assenze, riposo, viaggio, forma).

Il riferimento con cui confrontarsi è il mercato. "Il migliore possibile" significa: **avvicinarsi il più possibile alla precisione della linea di chiusura dei bookmaker** e trovare i casi, se esistono, in cui il modello aggiunge informazione. Battere stabilmente la linea di chiusura è raro anche per i professionisti. Non dichiarare mai un vantaggio sul mercato senza intervalli di confidenza.

## Punto di partenza: il modello attuale (baseline da battere)

`baseline_model.js` è il modello che uso oggi in una pagina web. Funziona in Node e nel browser. In sintesi:
- rating di attacco e difesa per squadra stimati con una regressione ridge sui punti fatti e subiti (`lambda` 2, emivita 60 giorni, scarti oltre 15 punti contati a metà);
- vantaggio campo stimato con un prior di 2,2 punti;
- assenze: valore di ogni giocatore dal BPM di Basketball-Reference riportato verso un prior (300 minuti), moltiplicato per i minuti; effetto smorzato (0,8) e confrontato con la frazione di partite già saltate;
- penalità back-to-back di 1 punto;
- probabilità dalla normale con deviazione standard 11,5 più l'incertezza dei rating.

Lezioni dalla prima verifica (18 novembre 2026, 12 partite: 7 vincitori indovinati; i bookmaker 6 su 12):
1. **Molte assenze insieme sono sottostimate.** I Warriors senza Curry, Butler, Porziņģis e Moody erano quasi alla pari per il modello, -6,5 per il mercato; hanno perso di 22. Sommare il BPM dei singoli assenti non basta: servono minuti ridistribuiti e la qualità di chi entra davvero.
2. **Le assenze dell'ultimo minuto contano.** Toronto ha tenuto a riposo Barnes nel back-to-back e ha perso con Washington. Servono un modello di probabilità di riposo e l'aggiornamento con l'ultimo injury report prima della palla a due.
3. **Sul margine il mercato è più preciso.** Quando il modello si stacca dalla linea di oltre 3 punti, di solito gli manca un'informazione. Queste partite vanno segnalate con un "codice motivo".
4. **La varianza al tiro è enorme** (Bulls 21/46 da tre a Brooklyn, Celtics 11/44 a Denver). I rating devono essere corretti per la fortuna al tiro, soprattutto per il 3P% e il FT% concessi agli avversari.

## Dati da usare (verifica tu accessibilità e licenze, e documentale)

- **NBA Stats API** tramite il pacchetto Python `nba_api`: play-by-play (`PlayByPlayV3`), rotazioni con entrate e uscite (`GameRotation`), box score tradizionali, avanzati, tracking, hustle e matchup, quintetti (`LeagueDashLineups`), tiri con coordinate (`ShotChartDetail`). stats.nba.com blocca spesso gli IP dei server cloud: prevedi intestazioni, ritardi, retry e cache. Se serve, fai girare l'ingestione dal mio computer.
- **cdn.nba.com liveData** (JSON di play-by-play e box score per partita): di solito raggiungibile anche dal cloud. Usalo come alternativa.
- **pbpstats.com** (API): possessi, stint e statistiche per quintetto già ripuliti.
- **Basketball-Reference**: storico, BPM, controlli incrociati.
- **Injury report ufficiale NBA** (PDF pubblicati più volte al giorno): salva ogni versione con l'orario, perché serve sapere *quando* un'informazione era nota.
- **Designazioni arbitrali** (official.nba.com, pubblicate la mattina della partita): ritmo, falli e tiri liberi per il modello dei totali.
- **Calendario e geografia**: coordinate e altitudine delle arene, fusi orari, distanza percorsa, giorni di riposo, 3 partite in 4 notti, trasferte lunghe.
- **Quote storiche** (apertura e chiusura di spread, totale e moneyline): dataset pubblici (Kaggle, archivi Sportsbook Reviews) o un servizio a pagamento come The Odds API. Senza quote storiche non si può misurare il modello contro il mercato: è un requisito, non un extra.

Non inventare mai dati. Se una fonte non risponde, dimmelo e proponi un'alternativa.

## Architettura richiesta

1. **Rating dei giocatori per possesso.** RAPM (regressione ridge sugli stint del play-by-play) separato per attacco e difesa, su più stagioni con decadimento nel tempo e un prior dal box score (stile EPM/LEBRON). Correzione per la fortuna: 3P% e FT% avversari riportati verso la media.
2. **Proiezione dei minuti.** Minuti attesi per ogni giocatore, dati la disponibilità (probabilità di giocare per stato: out, doubtful, questionable, probable), le rotazioni recenti, il rischio di partita a senso unico e la probabilità di riposo nei back-to-back (modello sulle scelte passate di ogni squadra e giocatore).
3. **Forza della squadra nella singola partita** = somma dei rating dei giocatori pesata per i minuti proiettati, più una componente di squadra (sistema, allenatore) stimata con un modello bayesiano gerarchico. Così cinque assenze insieme pesano per quello che valgono davvero.
4. **Contesto.** Vantaggio campo stimato per stagione e per squadra (con shrinkage, non fissato), riposo (0, 1, 2, 3+ giorni), viaggio e fusi orari, altitudine, densità del calendario, fine stagione (squadre senza obiettivi).
5. **Ritmo ed efficienza per i totali.** Possessi attesi da ritmo di entrambe le squadre e arbitri; punti per possesso da attacco e difesa; da qui totale e scarto in modo coerente.
6. **Distribuzione dello scarto.** Verifica se la normale basta o se serve una t di Student o i residui empirici. La varianza deve dipendere dal ritmo e dalla differenza di forza. La probabilità di vittoria deve risultare calibrata.
7. **Ensemble.** Combina (a) il modello giocatori + minuti, (b) i rating di squadra sui risultati recenti, (c) un Elo con margine di vittoria, (d) un gradient boosting (LightGBM) sulle feature di contesto. Pesi stimati in walk-forward. Tieni separato un modello "consapevole del mercato" (con la linea d'apertura come input) per stimare il movimento della linea: non mescolarlo con il modello "puro".
8. **Inizio stagione.** Prior preseason da rating delle stagioni precedenti, curve d'età e cambi di roster, aggiornati in modo bayesiano partita dopo partita. A metà novembre le squadre hanno solo 12-15 partite: è qui che il prior conta di più.

## Protocollo di valutazione (non negoziabile)

- **Walk-forward stretto**: ogni pronostico usa solo informazioni disponibili prima della palla a due. Scrivi test automatici anti-leakage (ogni feature ha un timestamp precedente all'inizio della partita). Per lo storico degli infortuni usa l'injury report con l'orario; dove non esiste, dichiara l'approssimazione.
- **Stagioni**: 2014-15 → 2024-25 per sviluppo e taratura, 2025-26 come test mai toccato prima della fine, 2026-27 dal vivo.
- **Metriche**, sempre affiancate a quelle della linea di chiusura sullo stesso campione: MAE e RMSE dello scarto, MAE del totale, log loss, Brier score, curva di calibrazione ed ECE, record contro lo spread e ROI a -110 con intervalli bootstrap, valore rispetto alla chiusura (CLV) dei pronostici fatti all'apertura.
- **Significatività**: bootstrap appaiato sulle differenze partita per partita, oppure test di Diebold-Mariano. Niente conclusioni sotto le 500 partite.
- **Ablation**: quanto aggiunge ogni componente (giocatori, minuti, riposo, viaggio, arbitri, ensemble).
- **Analisi degli errori**: le 50 partite peggiori, con i motivi.

## Ingegneria

- Python 3.12; dipendenze con `uv`. Struttura: `ingest/`, `features/`, `models/`, `evaluate/`, `publish/`, `tests/`. Dati in Parquet e DuckDB. Configurazione in YAML, semi fissi, risultati riproducibili.
- Comandi: `nba ingest --season 2025-26`, `nba backtest`, `nba predict --date 2026-11-20`, `nba report`.
- Report HTML del backtest con grafici: calibrazione, errore per mese, contro il mercato, importanza delle componenti.
- **Pipeline giornaliera**: GitHub Actions (o il mio computer) due volte al giorno: injury report, quote, pronostici. Pubblica `predictions/latest.json` e `predictions/AAAA-MM-GG.json` nel repository.
- **Formato di uscita compatibile con la mia pagina**: una riga per partita con `d` (data USA), `a`, `h` (codici a 3 lettere: ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS), `tip` (inizio UTC), `ap`, `hp` (punti attesi), `m` (scarto casa), `p` (probabilità casa), `sd`, `outA`/`outH` (assenze considerate, testo) e `why` (i 3 fattori principali). La pagina salva già ogni sera i pronostici del modello base in questo formato: così i due modelli si potranno confrontare sulle stesse partite.

## Come lavorare con me

Procedi per fasi. **Alla fine di ognuna fermati**, scrivi un riepilogo in `REPORT.md` con i numeri e aspetta il mio via libera.

0. **Ricognizione**: verifica le fonti (cosa risponde, da dove, con quali limiti) e proponi il piano dettagliato con i tempi.
1. **Ingestione storica** con controlli di qualità (partite mancanti, punteggi che non tornano, giocatori duplicati).
2. **Baseline**: riproduci `baseline_model.js` in Python e misuralo sul 2025-26 accanto alla linea di chiusura. Questi sono i numeri da battere.
3. **Giocatori + minuti + disponibilità.**
4. **Contesto + totali.**
5. **Ensemble + calibrazione**, backtest completo e ablation.
6. **Pipeline dal vivo** e pubblicazione del JSON.

Regole: niente dati inventati, niente risultati senza intervallo di confidenza, niente ottimizzazione sul set di test. Spiega le scelte in modo semplice e concreto: non sono uno statistico sportivo. Le previsioni sono a scopo informativo, non consigli di scommessa.
