# Stimme auf dem Küchen-Display

Stand 8.11.2026, zu #15 und rundfunk#128. Das Display ist ein Netz-Gerät der rundfunk-Bridge auf
raspi-agent. Ein Tipp aufs Mikrofon startet ein Gespräch mit Elektra, ihre Antwort kommt über den
Standard-Ausgang des Pi (beim Tischtest die Shokz per Bluetooth). Elektra kann dabei die Seiten
der Anzeige wechseln.

## Was läuft

| Teil | Datei im Repo | Wo |
|---|---|---|
| Küchen-Dienst: Seite, Bridge, Ton | `pi/dienst/dienst.py`, `vertrag.py` | Pi, Dienst `kuechen-dienst`, venv `~/kuechen-venv` |
| Gerätewerte für die Bridge | `pi/bruecke/geraete.conf` | raspi-agent, `/etc/systemd/system/rundfunk.service.d/` |
| Geheimnisse | nicht im Repo, 1Password `kuechen-display/.env` | Pi, `~/kuechen-display/.env` (Rechte 600); früher `~/.config/kuechen-display/geraete-token` |
| Kameradienst | `pi/gesten/` | Pi, Dienst `kuechen-gesten`, nur beim Testen an |
| Messskript Handpunkte | `pi/werkzeuge/handpunkte_messen.sh` | Pi, `~/kuechen-display/werkzeuge/` |

Der Küchen-Dienst liefert die Kiosk-Seite auf `http://localhost:8080/` aus und schickt ihr
Ereignisse unter `/ereignisse`. Er hält die WebSocket-Verbindung zu
`ws://raspi-agent.local:8000/geraet/netz` (Gerät `kueche`), schickt Kanal 0 des XVF3800 als
PCM16 mit 16 kHz und spielt Elektras Ton mit `pw-cat`. Zwischen zwei Antworten spielt er Stille,
damit Bluetooth wach bleibt; sonst fehlt am Anfang etwa eine Sekunde.

## Bedienung

| Was | Wirkung |
|---|---|
| Tipp aufs Mikrofon, Elektra ist aus | Gespräch beginnt, sie hört zu |
| Tipp, während sie spricht | sie hört sofort auf und hört wieder zu |
| Tipp, während sie zuhört oder nachdenkt | Gespräch am Display beendet, Mikrofon zu |
| flache Hand vor der Kamera, während sie spricht | wie Tipp beim Sprechen (Kamera nur beim Testen) |

Das Mikrofon sitzt auf der Seite „Heute“ an der Figur. In einer App wie Spotify ist die Kiosk-Seite
weg; dort ist der Mikro-Knopf ganz rechts in der Rückweg-Leiste oben links (#70). Er wirkt wie der
Tipp aufs Mikrofon und leuchtet orange, solange Elektra dran ist.

## Was Elektra am Display kann

| Werkzeug | Beispiel | Wirkung |
|---|---|---|
| `seite_zeigen` | „zeig mir morgen“, „zurück zu heute“, „zeig die Apps“ | wechselt die Seite, aus einer App heraus zurück zum Kiosk |
| `app_oeffnen` | „öffne Spotify“ | öffnet die App; bietet die Bridge nur an, weil der Dienst `APPS = ["spotify"]` meldet |
| `rezeptschritt` | „nächster Schritt“ | noch ohne Rezept-App, Elektra hört „Es ist kein Rezept offen“ |

Eine neue App braucht drei Stellen: den Namen in `APPS` (`pi/dienst/dienst.py`), `data-app` an ihrer
Kachel (`pi/kiosk/index.html`) und den Eintrag in `APPS` von `pi/kiosk-rueckweg/rueckweg.js`.

**Befehle in einer App.** Ist eine App vorn, hält der Küchen-Dienst einen Befehl der Bridge vier
Sekunden bereit. Die Rückweg-Leiste fragt jede Sekunde `GET http://localhost:8080/lage` ab (über
`hintergrund.js`, weil die https-Seite localhost nicht selbst fragen darf), bekommt Elektras
Zustand und einen wartenden Befehl, führt ihn aus und quittiert. Holt ihn niemand ab, hört Elektra
„Die Anzeige ist nicht offen“. Als „App vorn“ gilt: Die Leiste hat in den letzten 2,5 Sekunden
gefragt und seitdem hat sich keine Kiosk-Seite verbunden.

Beim Beenden per Tipp erfährt die Bridge nichts, weil der Vertrag keine Nachricht dafür hat. Sie
hört keinen Ton mehr und schließt die Live-Sitzung nach ihrer Ruhezeit selbst.

## Einrichten

Alles vom Mac aus, im Checkout von `kuechen-display`.

**1. Token auf den Pi bringen.** Das Token der Bridge steht als `RUNDFUNK_GERAETE_TOKEN` im
1Password-Environment `kuechen-display/.env` und kommt mit `pi-env-push.sh` auf den Pi. Die
Schritte stehen in `docs/datenweg.md`, Abschnitt „Einrichten“. Bis das Environment eingerichtet
ist, gilt die frühere Datei `~/.config/kuechen-display/geraete-token` weiter.

**2. Gerätewerte für die Bridge einspielen.** Das braucht sudo auf raspi-agent und startet die
Bridge neu. Ein laufendes Gespräch mit Elektra im Studio bricht dabei ab.

```bash
scp pi/bruecke/geraete.conf raspi-agent.local:/tmp/geraete.conf
```

```bash
ssh -t raspi-agent.local 'sudo install -D -m 644 /tmp/geraete.conf /etc/systemd/system/rundfunk.service.d/geraete.conf && sudo systemctl daemon-reload && sudo systemctl restart rundfunk && systemctl is-active rundfunk'
```

**3. Dateien auf den Pi und einrichten.**

```bash
pi/push.sh
```

Das Skript spiegelt `pi/`, die Wetterbilder und die Figur (F2), ruft auf dem Pi
`install-kiosk.sh` auf und lädt den Kiosk neu. Einzelheiten: `docs/deploy.md`.

`install-kiosk.sh` legt `~/kuechen-venv` (nur `websockets`) und `~/gesten-venv` (MediaPipe) an,
installiert beide Units, startet `kuechen-dienst` und lässt `kuechen-gesten` aus.

## Prüfen

```bash
ssh kuechen-display.local 'journalctl -u kuechen-dienst -n 20 --no-pager'
```

Nach dem Start steht dort „Mit der Bridge verbunden: … als kueche“. Bei einem Gespräch folgen
Zeilen wie `Zustand: zuhoeren`, `Zustand: sprechen`. Auf der Seite mit `?debug=1` zeigt die Zeile
unten links Elektras Zustand.

Nur die Ereignisse ansehen, die die Seite bekommt:

```bash
ssh kuechen-display.local 'curl -sN http://127.0.0.1:8080/ereignisse'
```

Einen Text in der Zeile der Seite anzeigen (zum Beispiel Anweisungen beim Messen):

```bash
ssh kuechen-display.local 'curl -s -X POST -d "{\"text\": \"Hallo\"}" http://127.0.0.1:8080/hinweis'
```

## Kamera beim Testen

Die Kamera läuft nur beim Testen (Entscheidung 8.11.2026).

```bash
ssh kuechen-display.local 'sudo systemctl start kuechen-gesten'
```

```bash
ssh kuechen-display.local 'sudo systemctl stop kuechen-gesten'
```

Was die Kamera sieht, zeigt `rpicam-hello` als Fenster über dem Kiosk. Vorher den Kameradienst
stoppen, beide zusammen gehen nicht:

```bash
ssh kuechen-display.local 'sudo systemctl stop kuechen-gesten; WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 setsid -f rpicam-hello -t 120000 --viewfinder-width 960 --viewfinder-height 540 </dev/null >/dev/null 2>&1'
```

Handpunkte mitschneiden, mit Anweisungen und Countdown auf dem Display:

```bash
ssh kuechen-display.local 'sudo systemctl set-environment GESTEN_PUNKTE=1 && sudo systemctl restart kuechen-gesten'
```

```bash
ssh kuechen-display.local 'sh ~/kuechen-display/werkzeuge/handpunkte_messen.sh "Nach links wischen|12" "Tippen|12"'
```

```bash
ssh kuechen-display.local 'sudo systemctl unset-environment GESTEN_PUNKTE; sudo systemctl stop kuechen-gesten'
```

Ohne Argumente misst das Skript die sechs Handhaltungen vom 8.11.2026. Der Mitschnitt liegt in
`/tmp/handpunkte.txt`, die Abschnittsgrenzen in `/tmp/handpunkte-marken.txt`.

## Messwerte vom 8.11.2026

- Erste Antwort: Der Aufbau der Live-Sitzung bei OpenAI dauert im Studio im Median 2,3 s
  (66 Gespräche in 7 Tagen, 1,3 bis 3,8 s), in der Küche einmal 3,1 s. Ab der zweiten Frage
  liegen 0,1 bis 0,3 s zwischen „gehört“ und dem ersten Ton. Das Display verzögert nichts.
- Ende zu Ende: Uhrzeit, `seite_zeigen` morgen und heute mit Quittung, Abbruch per Tipp.
- Gesten: siehe `docs/kiosk-und-gesten.md`.

## Offen

- rundfunk braucht eine Nachricht `ende`, damit ein Tipp die Live-Sitzung sofort schließt, und
  Werkzeuge für „vor“ und „zurück“, damit man per Sprache blättern kann.
- Echounterdrückung ist mit Bluetooth nicht prüfbar. Sie braucht den Lautsprecher am XVF3800.
