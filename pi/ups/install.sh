#!/usr/bin/env bash
# Auf dem Pi: sudo bash install.sh   (idempotent)
# Installiert den Akku-Wächter für den UPS HAT (E). Anleitung: docs/akku-waechter.md
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Bitte mit sudo starten." >&2; exit 1; }
d=$(cd "$(dirname "$0")" && pwd)

raspi-config nonint do_i2c 0
python3 -c "import smbus" 2>/dev/null || apt-get install -y -q python3-smbus

install -d /usr/local/lib/ups-waechter
install -m 755 "$d/ups_waechter.py" /usr/local/lib/ups-waechter/ups_waechter.py
install -m 644 "$d/ups-waechter.service" /etc/systemd/system/ups-waechter.service
systemctl daemon-reload
systemctl enable ups-waechter.service
systemctl restart ups-waechter.service
echo "Fertig. Prüfen: systemctl status ups-waechter; cat /run/ups-waechter/status.json"
