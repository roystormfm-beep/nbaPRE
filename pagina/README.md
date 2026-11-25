# Pagina «Pronostici NBA 2026/27»

Copia dei file della pagina pubblicata su claude.ai (https://claude.ai/artifact/78xpsAJ9UQorNUyo5VGScn) e stato
dei dati che il workflow `live` prepara per lei.

- `index.html`, `tools/freeze.js`: copie **esatte** dei file pubblicati. Il passo «Dati della pagina» esegue con
  node il modello contenuto in `index.html` per congelare i pronostici prima della palla a due. Ogni volta che la
  pagina viene ripubblicata, aggiornare anche queste copie (stesso commit), altrimenti i pronostici salvati
  vengono da un modello diverso da quello della pagina.
- `stato/injlearn.json`: peso delle assenze imparato dagli errori (fonte di verità; nel database c'è una copia).
- `stato/injuries.json`, `stato/bref.json`, `stato/pstats.json`: ultimo report infortuni valido, statistiche dei
  giocatori del giorno, statistiche reali delle giornate concluse.
- `stato/congelati.json`: pronostici congelati di ieri e oggi, rispediti a ogni giro.
- `stato/inviati.json`: quando è cambiato per l'ultima volta ogni documento (si rispedisce per 26 ore).

Il risultato è `predictions/pagina_sync.json`, campo `ops`: elenco ordinato di operazioni `set`/`merge` sul database
della pagina. Le copia l'unica attività pianificata di Claude («Sincronizzazione NBA»), senza leggere siti web.
