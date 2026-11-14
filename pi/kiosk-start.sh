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

exec chromium --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --password-store=basic --ozone-platform=wayland --touch-events=enabled \
  --overscroll-history-navigation=0 --lang=de-DE --disable-features=Translate \
  --autoplay-policy=no-user-gesture-required \
  "--app=http://localhost:8080/${1:-}"
