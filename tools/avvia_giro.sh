#!/usr/bin/env bash
# Avvia un giro del workflow "live" su GitHub (stesso lavoro dei giri automatici) e aspetta che finisca.
# Lo usa l'attività pianificata di Claude "Giri modello NBA", perché gli orari automatici di GitHub
# arrivano spesso in ritardo di ore o saltano.
# Uscita: 0 giro riuscito; 1 giro fallito o non concluso in tempo; 3 giro non avviato.
set -uo pipefail
R=roystormfm-beep/nbaPRE
T0=$(date -u -d '-60 seconds' +%Y-%m-%dT%H:%M:%SZ)

# solo API REST: nelle sessioni di Claude GraphQL non è disponibile
if ! gh api -X POST "repos/$R/actions/workflows/live.yml/dispatches" -f ref=main -f "inputs[step]=all" > /dev/null; then
  echo "ERRORE: non riesco ad avviare il giro (accesso a GitHub?)"; exit 3
fi

ID=""
for _ in $(seq 1 20); do
  sleep 6
  ID=$(gh run list -R "$R" --workflow live.yml --event workflow_dispatch -L 5 --json databaseId,createdAt \
        -q "[.[] | select(.createdAt >= \"$T0\")] | last | .databaseId // empty" 2>/dev/null)
  [ -n "$ID" ] && break
done
[ -n "$ID" ] || { echo "ERRORE: giro avviato ma non trovato nell'elenco"; exit 3; }
echo "giro $ID avviato"

# un giro normale dura 1-5 minuti; può aspettare in coda dietro un giro automatico di GitHub.
# Se dopo 9 minuti non è finito, lo stato stampato è "queued" o "in_progress": si può riprendere con
#   gh run watch ID -R roystormfm-beep/nbaPRE
timeout 540 gh run watch "$ID" -R "$R" --interval 20 > /dev/null 2>&1
gh run view "$ID" -R "$R" --json status,conclusion,createdAt,updatedAt \
  -q '"stato \(.status), esito \(.conclusion // "-") (\(.createdAt) -> \(.updatedAt))"'
gh run view "$ID" -R "$R" --log 2>/dev/null | grep -E "pronostici pubblicati" | sed -E 's/^.*Z //' || true
[ "$(gh run view "$ID" -R "$R" --json conclusion -q .conclusion)" = "success" ]
