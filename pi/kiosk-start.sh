#!/bin/sh
# Auf dem Pi: startet Chromium im Kiosk auf dem Ruhebildschirm.
# Ein Aufruf für beide Wege, damit die Flags nicht auseinanderlaufen:
#   beim Hochfahren  ~/.config/autostart/kiosk.desktop
#   nach einem Deploy  pi/push.sh (vom Mac)
# Aufruf: kiosk-start.sh [Zusatz]   z. B. kiosk-start.sh '?debug=1'
# Anleitung: docs/kiosk-und-gesten.md
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

# Die Seite kommt vom Küchen-Dienst. Ohne ihn zeigt Chromium seine Fehlerseite und
# lädt nicht von selbst neu, also bis zu 30 s auf ihn warten.
n=0
while [ "$n" -lt 30 ] && ! curl -s -o /dev/null --max-time 2 http://localhost:8080/; do
  n=$((n + 1))
  sleep 1
done

# Kein --kiosk: Im Vollbild läge der Kiosk über der Bildschirmtastatur. Randlos und maximiert
# macht ihn die labwc-Fensterregel (kiosk/labwc-rc.xml). Die beiden Wayland-IME-Flags lassen
# Chromium mit squeekboard reden, sonst geht die Tastatur nie auf (Test 15.11.2026).
# Kein Panel im Kiosk: Auch ausgeblendet lässt es oben einen Streifen von 5 px stehen, und seine
# Hinweise („Updates are available“, Netzteil) lägen über dem Kiosk. Pi OS startet es über
# /etc/xdg/labwc/autostart mit lwrespawn; labwc läuft mit -m, ein eigener Autostart kann es also
# nicht weglassen. Deshalb hier erst lwrespawn, dann das Panel beenden. Zurück für VNC:
#   setsid -f lwrespawn /usr/bin/wf-panel-pi
pkill -f 'lwrespawn /usr/bin/wf-panel-pi' 2>/dev/null || true
pkill -x wf-panel-pi 2>/dev/null || true

# Rückweg-Leiste oben links auf Seiten, die aus der Apps-Seite geöffnet werden (#10, docs/spotify.md).
RUECKWEG="$(cd "$(dirname "$0")" && pwd)/kiosk-rueckweg"

exec chromium --noerrdialogs --disable-infobars --no-first-run \
  --password-store=basic --ozone-platform=wayland --touch-events=enabled \
  --overscroll-history-navigation=0 --lang=de-DE --disable-features=Translate \
  --autoplay-policy=no-user-gesture-required --load-extension="$RUECKWEG" \
  --enable-wayland-ime --wayland-text-input-version=3 \
  "--app=http://localhost:8080/${1:-}"
