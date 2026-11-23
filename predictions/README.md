# Pronostici dal vivo (stagione 2026-27)

Questi file sono scritti da GitHub Actions (workflow `live`) due volte al giorno: alle 14:30 e alle 22:20 UTC, cioè la mattina negli Stati Uniti e circa un'ora prima delle prime partite serali. Si possono anche rifare a mano con `nba live update` e poi `nba predict --date AAAA-MM-GG`.

Sono pronostici a scopo informativo, non consigli di scommessa.

## File

| File | Contenuto |
|---|---|
| `latest.json` | Pronostici dell'ultimo giorno calcolato |
| `AAAA-MM-GG.json` | Pronostici di quel giorno (data USA) |
| `registro_2026.csv` | Ogni pronostico pubblicato, una riga per partita e per esecuzione: serve a misurare il modello dal vivo |
| `ricostruiti_2026.csv` | Tutte le partite già giocate, pronosticate a posteriori con le sole informazioni precedenti a ciascuna |
| `confronto_2026.json` | Confronto con il mercato e con la pagina (`nba live compare`) |

**Una partita già iniziata non viene più riscritta.** Nel file del giorno resta il pronostico congelato prima della palla a due.

## Formato

Ogni file del giorno ha la stessa struttura dei documenti `nba/predlog-*` della pagina:

```
{"meta": {...}, "g": {"AAAA-MM-GG_AWAY_HOME": riga, ...}}
```

Campi di ogni riga:

| Campo | Significato |
|---|---|
| `d` | Data USA della partita |
| `a`, `h` | Squadra in trasferta e squadra di casa (codici a 3 lettere della pagina) |
| `tip` | Inizio della partita (UTC) |
| `t` | Quando è stato calcolato il pronostico (UTC) |
| `src` | `dal vivo` |
| `mv` | Versione del modello: commit del codice + impronta della configurazione |
| `ap`, `hp` | Punti attesi della squadra in trasferta e di quella di casa |
| `m` | Scarto atteso (casa − trasferta) |
| `p` | Probabilità che vinca la squadra di casa |
| `sd` | Deviazione standard dello scarto. Serve per la probabilità di coprire qualsiasi spread: P(casa copre −X) = P(scarto > X) |
| `tot` | Totale atteso dei punti |
| `outA`, `outH` | Assenze considerate dall'injury report, con l'effetto in punti di scarto |
| `why` | I 3 fattori principali del pronostico, in punti di scarto |
| `fattori` | Tutti i fattori: campo, qualità dei giocatori disponibili, assenze di casa e ospiti, riposo e calendario, altri modelli. La somma è `m` |
| `mk` | Linea di mercato al momento del calcolo: `sp` (spread della squadra di casa), `tot`, `ph` (probabilità di vittoria della casa senza margine), `src`, `at` |
| `dmk` | Modello − mercato, in punti di scarto |
| `motivo` | Codice motivo quando il modello si stacca dalla linea di 3 punti o più |
| `injAsOf` | Orario (New York) dell'injury report usato |

## Codici motivo

| Codice | Quando scatta |
|---|---|
| `DUBBI` | Ci sono giocatori importanti (almeno 20 minuti) in dubbio |
| `ASSENZE` | Le assenze dell'injury report pesano 2,5 punti o più |
| `RIPOSO` | L'effetto di riposo e calendario è di 1,5 punti o più |
| `POCHE_PARTITE` | Una delle due squadre ha giocato meno di 10 partite |
| `MODELLI_DIVERSI` | Modello giocatori e baseline differiscono di 4 punti o più |
| `SCONOSCIUTO` | Nessuno dei casi sopra: probabilmente al modello manca un'informazione |

Nei test sul 2025-26, quando modello e mercato differivano di 3 punti o più, è stato più vicino al risultato il mercato.
