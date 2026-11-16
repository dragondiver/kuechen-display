#!/usr/bin/env bash
# Auf dem Pi: bash ~/kuechen-display/install-kiosk.sh   (idempotent, fragt sudo für die Dienste)
# Vom Mac aus ruft pi/push.sh dieses Skript auf (docs/deploy.md).
# Richtet Küchen-Dienst, Schlafwächter, Kameradienst und Chromium-Kiosk ein.
# Anleitung: docs/stimme-und-geste.md und docs/kiosk-und-gesten.md
set -euo pipefail
d=$(cd "$(dirname "$0")" && pwd)   # ~/kuechen-display, per rsync vom Mac befüllt

# Küchen-Dienst: Seite, Bridge, Ton. Braucht nur websockets.
[ -d ~/kuechen-venv ] || python3 -m venv ~/kuechen-venv
~/kuechen-venv/bin/python -c "import websockets" 2>/dev/null || ~/kuechen-venv/bin/pip install -q "websockets>=15,<16"

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
echo "Fertig. Kamera für Gesten: sudo systemctl start kuechen-gesten (und stop danach)."
