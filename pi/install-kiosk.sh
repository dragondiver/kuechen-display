#!/usr/bin/env bash
# Auf dem Pi: bash ~/kuechen-display/install-kiosk.sh   (idempotent, fragt sudo für den Dienst)
# Richtet Gestendienst und Chromium-Kiosk ein. Anleitung: docs/kiosk-und-gesten.md
set -euo pipefail
d=$(cd "$(dirname "$0")" && pwd)   # ~/kuechen-display, per rsync vom Mac befüllt

[ -d ~/gesten-venv ] || python3 -m venv --system-site-packages ~/gesten-venv
~/gesten-venv/bin/python -c "import mediapipe" 2>/dev/null || ~/gesten-venv/bin/pip install -q mediapipe
[ -f "$d/gesture_recognizer.task" ] || curl -sSfL -o "$d/gesture_recognizer.task" \
  https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task

sudo install -m 644 "$d/gesten/kuechen-gesten.service" /etc/systemd/system/kuechen-gesten.service
sudo systemctl daemon-reload
sudo systemctl enable kuechen-gesten.service
sudo systemctl restart kuechen-gesten.service

install -d ~/.config/autostart
install -m 644 "$d/kiosk/kiosk.desktop" ~/.config/autostart/kiosk.desktop
echo "Fertig. Kiosk startet nach dem nächsten Anmelden; sofort: siehe docs/kiosk-und-gesten.md"
