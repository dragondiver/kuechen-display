#!/usr/bin/env bash
# Auf dem Pi: bash ~/kuechen-display/install-kiosk.sh   (idempotent, fragt sudo für die Dienste)
# Richtet Küchen-Dienst, Kameradienst und Chromium-Kiosk ein.
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

[ -f ~/.config/kuechen-display/geraete-token ] || echo "Achtung: Token fehlt, siehe docs/stimme-und-geste.md"

sudo install -m 644 "$d/dienst/kuechen-dienst.service" /etc/systemd/system/kuechen-dienst.service
sudo install -m 644 "$d/gesten/kuechen-gesten.service" /etc/systemd/system/kuechen-gesten.service
sudo systemctl daemon-reload
sudo systemctl enable kuechen-dienst.service
sudo systemctl restart kuechen-dienst.service
# Kamera nur beim Testen (8.11.2026): kein enable, und ein früheres enable zurücknehmen.
sudo systemctl disable kuechen-gesten.service 2>/dev/null || true

install -d ~/.config/autostart
install -m 644 "$d/kiosk/kiosk.desktop" ~/.config/autostart/kiosk.desktop
echo "Fertig. Kamera für Gesten: sudo systemctl start kuechen-gesten (und stop danach)."
