# Akku-Wächter und Ladeanzeige (UPS HAT E)

Stand 21.10.2026, zu #9. Der Waveshare UPS HAT (E) versorgt den Pi 5 aus vier 21700-Zellen.
Ohne Wächter läuft der Pi, bis die Zellen leer sind, und geht dann hart aus. Der Wächter
fährt ihn vorher sauber herunter.

## Was er tut

`pi/ups/ups_waechter.py` läuft als systemd-Dienst `ups-waechter.service` und liest alle 2 s
über I2C (Adresse `0x2D`) Ladezustand, Zellspannungen und Akkustrom.

| Bedingung | Reaktion |
|---|---|
| eine Zelle unter **3150 mV** und Akku lädt nicht (Strom unter 50 mA) | Warnung im Journal, Frist 60 s |
| Ladegerät kommt innerhalb der Frist | Entwarnung, nichts passiert |
| Frist abgelaufen | Befehl `0x55` an Register `0x01` des HAT, dann `systemctl poweroff` |

Nach `0x55` schaltet der HAT den Strom etwa 30 s später ab und **den Pi von selbst wieder ein**,
sobald ein Ladegerät steckt. Schwelle und Ablauf entsprechen Waveshares Beispiel `ups.py`
(<https://docs.waveshare.com/UPS-HAT-E-Tutorials-Raspberry-Pi>).

Den aktuellen Stand schreibt der Wächter nach `/run/ups-waechter/status.json`
(Modus, Prozent, Spannungen, Ströme, Restzeit). Eine spätere Anzeige auf dem Ruhebildschirm (#15)
oder in Home Assistant liest diese Datei, statt selbst I2C zu sprechen.

## Einrichten

Vom Mac aus, im Checkout von `kuechen-display`:

```bash
rsync -a pi/ups/ kuechen-display.local:~/ups-waechter/
ssh kuechen-display.local 'sudo bash ~/ups-waechter/install.sh'
```

`install.sh` ist idempotent. Es schaltet I2C ein, installiert `python3-smbus` falls nötig,
kopiert das Skript nach `/usr/local/lib/ups-waechter/` und startet den Dienst.

## Prüfen

```bash
ssh kuechen-display.local 'systemctl status ups-waechter --no-pager'
ssh kuechen-display.local 'cat /run/ups-waechter/status.json'
ssh kuechen-display.local 'journalctl -u ups-waechter --since today'
```

Im Journal steht jeder Wechsel des Zustands (laden, schnellladen, entladen, leerlauf) mit
Akkustand, außerdem Warnung, Entwarnung und Abschaltung.

## Ladeanzeige im Desktop (bis der Kiosk läuft)

Waveshares Beispielprogramm `batteryTray.py` zeigt ein Akku-Symbol in der Leiste. Es liegt
nicht in diesem Repo (fremder Code), sondern auf dem Pi unter `~/ups-hat-e/UPS_HAT_E/`:

```bash
ssh kuechen-display.local 'mkdir -p ~/ups-hat-e && cd ~/ups-hat-e && wget -q https://files.waveshare.com/wiki/UPS-HAT-E/UPS_HAT_E.zip && unzip -oq UPS_HAT_E.zip'
```

Es ist für X11 geschrieben. Unter Wayland (labwc) erscheint es nur mit `QT_QPA_PLATFORM=wayland`.
Autostart über eine Desktop-Datei:

```bash
ssh kuechen-display.local 'mkdir -p ~/.config/autostart && cat > ~/.config/autostart/akku-anzeige.desktop' <<'EOF'
[Desktop Entry]
Type=Application
Name=Akku-Anzeige
Comment=Ladeanzeige UPS HAT (E), Waveshare batteryTray.py
Exec=sh -c 'sleep 10; cd /home/florian/ups-hat-e/UPS_HAT_E && QT_QPA_PLATFORM=wayland exec python3 batteryTray.py'
Terminal=false
EOF
```

Wirkt beim nächsten Anmelden am Desktop. Die 10 s Wartezeit braucht es: Startet das Symbol vor der Leiste, läuft es, bleibt aber unsichtbar (am 21.10. beim Neustart beobachtet). Das Symbol fährt bei leerem Akku ebenfalls herunter;
das stört nicht, beide tun dasselbe. Entfernen: die Datei `~/.config/autostart/akku-anzeige.desktop` löschen.

## Grenzen

- Die Abschaltung ist mit einer I2C-Attrappe durchgespielt (leer → Entwarnung durch Laden → leer →
  Abschalten nach 60 s), aber noch nicht mit echt leeren Zellen ausgelöst.
- Die Prozentanzeige des HAT stimmt laut Waveshare erst nach einigen vollen Lade- und Entladezyklen.
- Fällt I2C dauerhaft aus (HAT ab, Bus gestört), kann der Wächter nichts messen und fährt auch nicht herunter;
  im Journal stehen dann `I2C-Lesefehler`. `status.json` wird in der Zeit nicht aktualisiert, eine Anzeige
  muss das Feld `zeit` (Unix-Sekunden) auf Alter prüfen.
- Den Strom rechnet der Wächter als echtes Zweierkomplement; Waveshares Beispiel liegt um 1 mA daneben (ohne Folgen).
