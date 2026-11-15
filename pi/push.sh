#!/usr/bin/env bash
# Vom Mac: bringt pi/ auf das Küchen-Display, startet den Küchen-Dienst neu und lädt den Kiosk.
#
#   pi/push.sh                  spiegeln, einrichten, neu starten
#   NUR_ZEIGEN=1 pi/push.sh     nur zeigen, was sich auf dem Pi ändern würde
#   KIOSK_ZUSATZ='?debug=1' pi/push.sh    Kiosk mit Debug-Zeile starten
#
# Gespiegelt wird der lokale Checkout, nicht origin/main. Anleitung: docs/deploy.md
set -euo pipefail

ZIEL=${ZIEL:-kuechen-display.local}
PFAD=${PFAD:-kuechen-display}
NUR_ZEIGEN=${NUR_ZEIGEN:-}
KIOSK_ZUSATZ=${KIOSK_ZUSATZ:-}

cd "$(dirname "$0")/.."

echo "→ Stand: $(git rev-parse --abbrev-ref HEAD) $(git rev-parse --short HEAD)"
if [ -n "$(git status --porcelain -- pi docs/entwuerfe/wetter/flach docs/entwuerfe/figur)" ]; then
  echo "  Achtung: uncommittete Änderungen gehen mit auf den Pi."
fi
if git rev-parse -q --verify origin/main >/dev/null && [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "  Achtung: der Checkout ist nicht origin/main (zuletzt geholter Stand)."
fi

echo "→ Tests"
python3 -m pytest -q pi | tail -1

# Nach Inhalt vergleichen (--checksum), nicht nach Zeitstempel: ein frischer Checkout hat
# lauter neue Zeitstempel, und die Liste soll nur echte Änderungen zeigen.
rs=(rsync -rlp --checksum --itemize-changes --exclude __pycache__ --exclude '.*_cache' --exclude .benchmarks)
[ -n "$NUR_ZEIGEN" ] && rs+=(--dry-run)

# Chromium liest den Hintergrund der Rückweg-Erweiterung nur neu ein, wenn sich "version" in
# manifest.json ändert; sonst läuft der alte Code weiter (#70, 15.11.2026: Diktat kam nie an).
neu_version=$(grep -o '"version": *"[^"]*"' pi/kiosk-rueckweg/manifest.json)
if ! ssh "$ZIEL" "cat $PFAD/kiosk-rueckweg/hintergrund.js" 2>/dev/null | cmp -s - pi/kiosk-rueckweg/hintergrund.js; then
  alt_version=$(ssh "$ZIEL" "grep -o '\"version\": *\"[^\"]*\"' $PFAD/kiosk-rueckweg/manifest.json" 2>/dev/null || true)
  if [ -n "$alt_version" ] && [ "$alt_version" = "$neu_version" ]; then
    echo "Abbruch: hintergrund.js ist geändert, manifest.json hat aber noch $neu_version." >&2
    echo "Version in pi/kiosk-rueckweg/manifest.json erhöhen, sonst behält Chromium den alten Hintergrund." >&2
    exit 1
  fi
fi

echo "→ spiegeln nach $ZIEL:$PFAD${NUR_ZEIGEN:+ (nur zeigen)}"
# Die Zielordner legt rsync nicht von selbst an (erster Deploy).
[ -n "$NUR_ZEIGEN" ] || ssh "$ZIEL" "mkdir -p $PFAD/kiosk/wetter $PFAD/kiosk/figur $PFAD/kiosk-rueckweg"
{
  # dienst/ und gesten/ mit --delete: eine umbenannte Datei soll auf dem Pi nicht liegen bleiben.
  "${rs[@]}" --delete --exclude 'test_*.py' pi/dienst/ "$ZIEL:$PFAD/dienst/"
  "${rs[@]}" --delete --exclude 'test_*.py' pi/gesten/ "$ZIEL:$PFAD/gesten/"
  "${rs[@]}" --delete pi/werkzeuge/ "$ZIEL:$PFAD/werkzeuge/"
  "${rs[@]}" --delete pi/kiosk-rueckweg/ "$ZIEL:$PFAD/kiosk-rueckweg/"
  # kiosk/ ohne --delete: wetter/ und figur/ kommen aus docs/entwuerfe und liegen nicht in pi/kiosk.
  "${rs[@]}" pi/kiosk/ "$ZIEL:$PFAD/kiosk/"
  "${rs[@]}" --include '*.png' --exclude '*' docs/entwuerfe/wetter/flach/ "$ZIEL:$PFAD/kiosk/wetter/"
  "${rs[@]}" --include '*-klein.png' --exclude '*' docs/entwuerfe/figur/ "$ZIEL:$PFAD/kiosk/figur/"
  "${rs[@]}" pi/install-kiosk.sh pi/kiosk-start.sh "$ZIEL:$PFAD/"
} | sed 's/^/  /'

if [ -n "$NUR_ZEIGEN" ]; then
  echo "Nichts geändert. Zeilen mit < würden übertragen, *deleting würde gelöscht."
  exit 0
fi

echo "→ einrichten und Küchen-Dienst neu starten"
ssh -t "$ZIEL" "bash $PFAD/install-kiosk.sh"

echo "→ Kiosk neu laden"
# pkill -x trifft nur den Browser; -f würde diese ssh-Zeile mit beenden.
ssh "$ZIEL" "pkill -x chromium; sleep 1; setsid -f sh $PFAD/kiosk-start.sh '$KIOSK_ZUSATZ' </dev/null >/tmp/kiosk.log 2>&1"

echo "→ Zustand"
sleep 4
ssh "$ZIEL" 'systemctl is-active kuechen-dienst; journalctl -u kuechen-dienst -n 4 --no-pager | cut -c1-160; pgrep -x chromium >/dev/null && echo "Chromium läuft" || echo "Chromium läuft NICHT, siehe /tmp/kiosk.log"'
