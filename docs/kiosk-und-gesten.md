# Kiosk und Gesten auf dem Pi

Stand 29.10.2026, Durchstich zu #15 (Ruhebildschirm) und #2 (Gesten). Auf dem Display läuft der
Ruhebildschirm aus Entwurf C4 im Chromium-Kiosk. Eine Handgeste vor der Kamera blättert die
Seiten um. Termine und Wetter sind noch Platzhalter, nur Uhr und Datum sind echt.

## Was läuft

| Teil | Datei im Repo | Auf dem Pi |
|---|---|---|
| Kiosk-Seite | `pi/kiosk/index.html` | `~/kuechen-display/kiosk/` |
| Wetterbild (W5, flach) | `docs/entwuerfe/wetter/flach/*.png` | `~/kuechen-display/kiosk/wetter/` |
| Gestendienst und Webserver | `pi/gesten/gesten.py`, `geste.py` | `~/kuechen-display/gesten/`, Dienst `kuechen-gesten` |
| Chromium-Autostart | `pi/kiosk/kiosk.desktop` | `~/.config/autostart/kiosk.desktop` |
| Einrichtung | `pi/install-kiosk.sh` | `~/kuechen-display/install-kiosk.sh` |

Der Gestendienst ist ein Prozess: Er liefert die Seite auf `http://localhost:8080/` aus (nur lokal
erreichbar), liest die Kamera, erkennt mit MediaPipe Hand und Handform und schickt Gesten als
Server-Sent Events an `/ereignisse`. Bilder verlassen das Gerät nicht und werden nicht gespeichert.

**Gesten** (Festlegung in #2):

| Geste | Wirkung |
|---|---|
| Hand zügig quer wischen, nach links | nächste Seite rechts (Heute → Morgen/Woche) |
| nach rechts | Seite links (Heute → Apps) |
| flache Hand ruhig ca. 0,6 s zeigen | Stopp; zeigt vorerst nur kurz ein Hand-Symbol |

Nach jeder Geste ist 1,2 s Pause, damit das Zurückführen der Hand nicht gleich zurückblättert.
Die Schwellen stehen oben in `pi/gesten/geste.py`, die Tests in `pi/gesten/test_geste.py`.

## Einrichten oder aktualisieren

Vom Mac aus, im Checkout von `kuechen-display`:

```bash
rsync -a --exclude __pycache__ --exclude test_geste.py pi/gesten/ kuechen-display.local:kuechen-display/gesten/
```

```bash
rsync -a pi/kiosk/ kuechen-display.local:kuechen-display/kiosk/
```

```bash
rsync -a docs/entwuerfe/wetter/flach/ --include '*.png' --exclude '*/' kuechen-display.local:kuechen-display/kiosk/wetter/
```

```bash
rsync -a pi/install-kiosk.sh kuechen-display.local:kuechen-display/
```

```bash
ssh kuechen-display.local 'bash ~/kuechen-display/install-kiosk.sh'
```

`install-kiosk.sh` ist idempotent. Es legt das venv `~/gesten-venv` an (mit den System-Paketen,
damit `picamera2` und `libcamera` gehen) und installiert `mediapipe`, lädt das Modell
`gesture_recognizer.task` von Google, richtet den Dienst ein und startet ihn neu und legt den
Chromium-Autostart an. Der Kiosk startet beim nächsten Anmelden am Desktop von selbst.

## Kiosk sofort neu starten

```bash
ssh kuechen-display.local 'pkill -x chromium; sleep 1; WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 setsid -f chromium --kiosk --noerrdialogs --disable-infobars --no-first-run --password-store=basic --ozone-platform=wayland --touch-events=enabled --overscroll-history-navigation=0 "--app=http://localhost:8080/?debug=1" </dev/null >/tmp/kiosk.log 2>&1'
```

`pkill -x chromium` trifft nur den Browser. Ein `pkill -f chromium…` würde die eigene
ssh-Befehlszeile mit beenden.

Zusätze an der Adresse:

- `?debug=1` zeigt unten links live, was die Kamera sieht (Handposition x/y, Handform, Sicherheit),
  und die letzte erkannte Geste.
- `?messen=1` blättert 60 s lang selbst hin und her und schreibt die Bildraten ins Journal des Dienstes.

## Prüfen

```bash
ssh kuechen-display.local 'systemctl status kuechen-gesten --no-pager | head -5'
```

```bash
ssh kuechen-display.local 'journalctl -u kuechen-gesten -f | grep -E "Geste|Kamera:|Messung"'
```

Jede Minute steht dort eine Zeile `Kamera: … Bilder/s, … CPU … %`; jede erkannte Geste als `Geste: {...}`.

## Messwerte vom 29.10.2026

- **Glaseffekt** (`backdrop-filter: blur(28px)`) mit Kamera-Erkennung gleichzeitig, `?messen=1`:
  beim Gleiten 56 Bilder/s (8 von 703 Frames über 33 ms), in Ruhe 59 Bilder/s. Flüssig.
- **Handerkennung** bei 640 × 360: Kamera 30 Bilder/s, Erkennung im Mittel 31 ms, belegt etwa einen
  der vier Kerne. Mit 15 Bildern/s gingen schnelle Wischbewegungen verloren (Hand im Bild verwischt);
  seitdem 30 Bilder/s, kurze Belichtung und Lücken bis 0,3 s werden überbrückt.
- Temperatur 54 °C, keine Drosselung (`throttled=0x0`).

## Bekannte Grenzen

- Die Kamera liegt beim Tischtest lose; das Bild wird um 180° gedreht (Flachbandkabel nach oben).
  Im Gehäuse ggf. `Transform` in `gesten.py` anpassen.
- Schrift: Auf dem Pi gibt es weder SF Pro noch Helvetica; Chromium nimmt Nimbus Sans, die keinen
  dünnen Schnitt hat. Uhr und Temperatur wirken dadurch kräftiger als im Entwurf.
- Stopp hat noch nichts anzuhalten (Timer, Musik, Elektra kommen später).
