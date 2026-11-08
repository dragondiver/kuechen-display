#!/bin/sh
# Handpunkte mitschneiden, mit Anweisungen und Countdown auf dem Display.
# Voraussetzung: kuechen-gesten läuft mit GESTEN_PUNKTE=1 (sudo systemctl set-environment GESTEN_PUNKTE=1,
# dann Neustart). Aufruf mit Abschnitten "Anweisung|Sekunden", ohne Argumente die Handhaltungen
# vom 8.11.2026. Ausgabe: /tmp/handpunkte.txt, Abschnittsgrenzen in /tmp/handpunkte-marken.txt
DIENST=http://127.0.0.1:8080
hinweis() { curl -s -X POST -H 'Content-Type: application/json' -d "{\"text\": \"$1\"}" "$DIENST/hinweis" >/dev/null; }
if [ $# -eq 0 ]; then
  set -- "Flache Hand vor der Brust, Handfläche zum Display|10" "Flache Hand tiefer, auf Bauchhöhe|10" \
    "Faust|10" "Hand halb offen, wie um einen Kochlöffel|10" "Flache Hand weit rechts oder links|10" \
    "Hände normal bewegen, keine Geste|10"
fi
: >/tmp/handpunkte-marken.txt
gesamt=0
for a in "$@"; do gesamt=$((gesamt + ${a##*|} + 3)); done
timeout $((gesamt + 10)) curl -sN "$DIENST/ereignisse" | while IFS= read -r z; do
  case "$z" in data:*) printf "%s %s\n" "$(date +%M:%S.%N | cut -c1-8)" "$z";; event:*) printf "%s " "$z";; esac
done >/tmp/handpunkte.txt &
for i in 5 4 3 2 1; do hinweis "Gleich geht es los · $i"; sleep 1; done
n=0
for a in "$@"; do
  n=$((n + 1)); text=${a%|*}; i=${a##*|}
  echo "anfang $n $(date +%M:%S.%N | cut -c1-8) $text" >>/tmp/handpunkte-marken.txt
  while [ "$i" -gt 0 ]; do hinweis "$n/$# · $text · noch $i s"; sleep 1; i=$((i - 1)); done
  echo "ende $n $(date +%M:%S.%N | cut -c1-8)" >>/tmp/handpunkte-marken.txt
  hinweis "Hand runter"; sleep 3
done
hinweis "Fertig, danke"
sleep 2; hinweis ""
wait
