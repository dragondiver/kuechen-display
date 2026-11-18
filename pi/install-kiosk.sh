#!/usr/bin/env bash
# Auf dem Pi: bash ~/kuechen-display/install-kiosk.sh   (idempotent, fragt sudo für die Dienste)
# Vom Mac aus ruft pi/push.sh dieses Skript auf (docs/deploy.md).
# Richtet Küchen-Dienst (mit Weckwort), Schlafwächter, Kameradienst und Chromium-Kiosk ein.
# Anleitung: docs/stimme-und-geste.md und docs/kiosk-und-gesten.md
set -euo pipefail
d=$(cd "$(dirname "$0")" && pwd)   # ~/kuechen-display, per rsync vom Mac befüllt

# Küchen-Dienst: Seite, Bridge, Ton. Braucht nur websockets.
[ -d ~/kuechen-venv ] || python3 -m venv ~/kuechen-venv
~/kuechen-venv/bin/python -c "import websockets" 2>/dev/null || ~/kuechen-venv/bin/pip install -q "websockets>=15,<16"

# Weckwort (#89, docs/stimme-und-geste.md): Vosk im selben venv, das deutsche Modell nur, wenn es fehlt.
# Das Weckwort darf ausfallen (Pi offline, Download kaputt, Prüfsumme falsch): Dann steht eine klare Meldung
# am Ende, und Dienst, Wächter und Kiosk werden trotzdem eingerichtet. Der Dienst schreibt ohne Modell einen
# Fehler ins Journal und lässt das Weckwort aus. Ein erneuter Lauf holt es nach.
# In einer Funktion, die in `if` steht, gilt `set -e` nicht; deshalb prüft jeder Schritt selbst.
VOSK_MODELL=vosk-model-small-de-0.15
VOSK_URL="https://alphacephei.com/vosk/models/$VOSK_MODELL.zip"
# SHA-256 der Zip-Datei, am 18.11.2026 auf dem Mac gemessen (shasum -a 256, 46 499 967 Bytes), nach Florians
# Freigabe des Downloads. Die Modellseite nennt selbst keine Summe.
VOSK_SHA256="b7e53c90b1f0a38456f4cd62b366ecd58803cd97cd42b06438e2c131713d5e43"
LADEN_TMP=""
# Strg-C beim Download räumt das halbe Verzeichnis weg; der Rest des Skripts bricht damit wie üblich ab.
trap 'rm -rf "${LADEN_TMP:-}"; exit 130' INT TERM
weckwort_einrichten() {
  rm -rf "$d"/modelle/.laden.*   # Reste eines abgebrochenen früheren Laufs
  ~/kuechen-venv/bin/python -c "import vosk" 2>/dev/null \
    || ~/kuechen-venv/bin/pip install -q "vosk>=0.3.45,<0.4" \
    || { echo "vosk konnte nicht installiert werden (offline?)." >&2; return 1; }
  [ -d "$d/modelle/$VOSK_MODELL" ] && return 0
  if [ "$VOSK_SHA256" = "HIER_PRUEFSUMME_EINTRAGEN" ]; then
    echo "Für das Weckwort-Modell $VOSK_MODELL ist in pi/install-kiosk.sh (VOSK_SHA256) noch keine" >&2
    echo "Prüfsumme eingetragen. Ohne sie wird nichts heruntergeladen. Siehe docs/stimme-und-geste.md, Weckwort." >&2
    return 1
  fi
  mkdir -p "$d/modelle" || return 1
  LADEN_TMP=$(mktemp -d "$d/modelle/.laden.XXXXXX") || return 1
  local tmp=$LADEN_TMP
  curl -sSfL -o "$tmp/modell.zip" "$VOSK_URL" \
    || { echo "Download von $VOSK_URL schlug fehl (offline?)." >&2; rm -rf "$tmp"; return 1; }
  echo "$VOSK_SHA256  $tmp/modell.zip" | sha256sum -c --status - \
    || { echo "Prüfsumme von $VOSK_URL stimmt nicht, Datei verworfen." >&2; rm -rf "$tmp"; return 1; }
  python3 -m zipfile -e "$tmp/modell.zip" "$tmp/entpackt" \
    || { echo "Entpacken von $VOSK_MODELL schlug fehl." >&2; rm -rf "$tmp"; return 1; }
  [ -d "$tmp/entpackt/$VOSK_MODELL" ] \
    || { echo "$VOSK_MODELL fehlt im Archiv." >&2; rm -rf "$tmp"; return 1; }
  mv "$tmp/entpackt/$VOSK_MODELL" "$d/modelle/$VOSK_MODELL" || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  LADEN_TMP=""
  echo "neu: $d/modelle/$VOSK_MODELL"
}
WECKWORT_FEHLT=0
weckwort_einrichten || WECKWORT_FEHLT=1

# Kameradienst: MediaPipe, mit System-Paketen für picamera2 und libcamera.
[ -d ~/gesten-venv ] || python3 -m venv --system-site-packages ~/gesten-venv
~/gesten-venv/bin/python -c "import mediapipe" 2>/dev/null || ~/gesten-venv/bin/pip install -q mediapipe
[ -f "$d/gesture_recognizer.task" ] || curl -sSfL -o "$d/gesture_recognizer.task" \
  https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task

[ -f "$d/.env" ] || [ -f ~/.config/kuechen-display/geraete-token ] || echo "Achtung: $d/.env fehlt, siehe docs/datenweg.md"

sudo install -m 644 "$d/dienst/kuechen-dienst.service" /etc/systemd/system/kuechen-dienst.service
sudo install -m 644 "$d/gesten/kuechen-gesten.service" /etc/systemd/system/kuechen-gesten.service
# Schlafen (docs/schlafen.md, #48): swayidle meldet Ruhe, wlopm schaltet den Ausgang. Beides ist auf dem
# Pi 5 vorinstalliert gewesen (16.11.2026); fehlt eins, kommt es hier dazu.
for paket in swayidle wlopm; do
  command -v "$paket" >/dev/null || sudo apt-get install -y "$paket"
done
sudo install -m 644 "$d/schlafen/kuechen-schlafen.service" /etc/systemd/system/kuechen-schlafen.service
sudo systemctl daemon-reload
sudo systemctl enable kuechen-dienst.service
sudo systemctl restart kuechen-dienst.service
sudo systemctl enable kuechen-schlafen.service
sudo systemctl restart kuechen-schlafen.service
# Kamera nur beim Testen (8.11.2026): kein enable, und ein früheres enable zurücknehmen.
sudo systemctl disable kuechen-gesten.service 2>/dev/null || true

# Fenster und Tastatur (docs/kiosk-und-gesten.md, „Bildschirmtastatur“): labwc maximiert Chromium
# randlos, das Panel blendet sich aus. Beim ersten Mal bleibt die alte Datei als *.vor-kiosk liegen.
setze() {  # setze <quelle> <ziel> <befehl, wenn geändert>
  cmp -s "$1" "$2" && return 0
  [ -f "$2" ] && [ ! -f "$2.vor-kiosk" ] && cp -p "$2" "$2.vor-kiosk"
  install -D -m 644 "$1" "$2"
  echo "neu: $2"
  sh -c "$3" || true
}
setze "$d/kiosk/labwc-rc.xml" ~/.config/labwc/rc.xml 'pgrep -x labwc >/dev/null && kill -HUP $(pgrep -x labwc)'
setze "$d/kiosk/wf-panel-pi.ini" ~/.config/wf-panel-pi/wf-panel-pi.ini 'pkill -x wf-panel-pi'

install -d ~/.config/autostart
install -m 644 "$d/kiosk/kiosk.desktop" ~/.config/autostart/kiosk.desktop
if [ "$WECKWORT_FEHLT" = 1 ]; then
  echo "ACHTUNG: Das Weckwort ist nicht eingerichtet (Meldung weiter oben). Alles andere läuft." >&2
  echo "Mit Netz erneut bash ~/kuechen-display/install-kiosk.sh, dann holt es Vosk und das Modell nach." >&2
fi
echo "Fertig. Kamera für Gesten: sudo systemctl start kuechen-gesten (und stop danach)."
