# Kiosk und Gesten auf dem Pi

Stand 8.11.2026, zu #15 (Ruhebildschirm) und #2 (Gesten). Auf dem Display läuft der
Ruhebildschirm aus Entwurf C4 im Chromium-Kiosk. Unten rechts sitzt die Figur (F2), ein Tipp darauf
startet ein Gespräch mit Elektra (`docs/stimme-und-geste.md`). Eine Handgeste vor der Kamera
blättert die Seiten um. Termine und Wetter sind noch Platzhalter, nur Uhr und Datum sind echt.

## Was läuft

| Teil | Datei im Repo | Auf dem Pi |
|---|---|---|
| Kiosk-Seite | `pi/kiosk/index.html` | `~/kuechen-display/kiosk/` |
| Wetterbild (W5, flach) | `docs/entwuerfe/wetter/flach/*.png` | `~/kuechen-display/kiosk/wetter/` |
| Figur (F2) | `docs/entwuerfe/figur/*-klein.png` | `~/kuechen-display/kiosk/figur/` |
| Küchen-Dienst: Seite und Ereignisse | `pi/dienst/dienst.py` | Dienst `kuechen-dienst` |
| Kameradienst | `pi/gesten/gesten.py`, `geste.py` | Dienst `kuechen-gesten`, nur beim Testen an |
| Chromium-Autostart | `pi/kiosk/kiosk.desktop` | `~/.config/autostart/kiosk.desktop` |
| Einrichtung | `pi/install-kiosk.sh` | `~/kuechen-display/install-kiosk.sh` |

Der Küchen-Dienst liefert die Seite auf `http://localhost:8080/` aus (nur lokal erreichbar) und
schickt ihr Ereignisse als Server-Sent Events an `/ereignisse`. Der Kameradienst liest die Kamera,
findet mit MediaPipe die Hände und schickt erkannte Gesten per POST an den Küchen-Dienst
(`/geste`, `/hand`). Bilder verlassen das Gerät nicht und werden nicht gespeichert.

## Gesten

Festlegung in #2:

| Geste | Wirkung |
|---|---|
| Hand zügig quer wischen, nach links | nächste Seite rechts (Heute → Morgen) |
| nach rechts | Seite links (Heute → Apps) |
| flache Hand, Finger nach oben, ca. 0,6 s ruhig | Stopp: Elektra hört auf zu sprechen |

So entscheidet der Code (Schwellen oben in `pi/gesten/geste.py`, Tests in `test_geste.py`):

- **Welche Hand:** Die Kamera sucht bis zu zwei Hände und nimmt die höher gehaltene. Mit nur einer
  gesuchten Hand blieb sie an der Hand hängen, die auf dem Tisch lag.
- **Wischen:** 0,28 Bildbreiten quer in höchstens 0,25 s, also gut 1,1 Bildbreiten/s. Das Ausholen
  vor dem Wischen ist langsamer und zählt nicht. Nach jeder Geste 1,2 s Pause.
- **Flache Hand:** eigene Regel aus den 21 Handpunkten, nicht MediaPipes „Open_Palm“. Jede der vier
  Fingerspitzen ist mindestens 1,45-mal so weit vom Handgelenk entfernt wie ihr Fingeransatz, und
  der Mittelfinger zeigt nach oben (Richtungswert ab 0,7).
- Die Kamera nimmt den Sensormodus 2304 × 1296 und damit den vollen Weitwinkel. Ohne Vorgabe wählt
  libcamera 1536 × 864, beim IMX708 ein Ausschnitt aus der Mitte.
- Kabel nach unten ist der Normalfall. Mit `KAMERA_KOPFUEBER=1` dreht der Dienst das Bild um 180°.

## Einrichten oder aktualisieren

Siehe `docs/stimme-und-geste.md`, Abschnitt „Einrichten“. Dazu das Wetterbild:

```bash
rsync -a docs/entwuerfe/wetter/flach/ --include '*.png' --exclude '*/' kuechen-display.local:kuechen-display/kiosk/wetter/
```

## Kiosk sofort neu starten

```bash
ssh kuechen-display.local 'pkill -x chromium; sleep 1; WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 setsid -f chromium --kiosk --noerrdialogs --disable-infobars --no-first-run --password-store=basic --ozone-platform=wayland --touch-events=enabled --overscroll-history-navigation=0 --lang=de-DE --disable-features=Translate "--app=http://localhost:8080/?debug=1" </dev/null >/tmp/kiosk.log 2>&1'
```

`pkill -x chromium` trifft nur den Browser. Ein `pkill -f chromium…` würde die eigene
ssh-Befehlszeile mit beenden.

Das System läuft auf `en_GB`. Damit Chromium kein Übersetzungsfenster zeigt, reichen die Flags
`--lang=de-DE --disable-features=Translate` allein nicht: In
`~/.config/chromium/Default/Preferences` müssen außerdem `translate.enabled` auf `false` und die
Sprachen unter `intl` auf `de` stehen (bei beendetem Chromium ändern).

Zusätze an der Adresse:

- `?debug=1` zeigt unten links live, was die Kamera sieht (Handposition x/y, Handform, Sicherheit),
  die letzte Geste und Elektras Zustand.
- `?messen=1` blättert 60 s lang selbst hin und her und schreibt die Bildraten ins Journal des Dienstes.

## Prüfen

```bash
ssh kuechen-display.local 'journalctl -u kuechen-gesten -f | grep -E "Geste|Kamera:"'
```

Jede Minute steht dort eine Zeile `Kamera: … Bilder/s, … CPU … %`, jede erkannte Geste als
`Geste: {...}`.

## Messwerte vom 8.11.2026 (Tischtest am Schreibtisch)

Die Kamera lag unter dem Display und schaute leicht nach oben, später sitzt sie darüber.

- Ausholen vor dem Wischen: 0,3 bis 0,8 Bildbreiten/s, echte Wischer 1,7 bis 2,5. Mit dem alten
  Zeitfenster (0,8 s) zählte das Ausholen als Wischen in die Gegenrichtung.
- Flache Hand, kleinster Fingerwert: vor der Brust 1,57 bis 1,79, auf Bauchhöhe 1,83 bis 1,86,
  seitlich 1,59 bis 1,65. Faust 0,57, halb offene Hand 0,17, normal bewegte Hände im Median 1,36.
  MediaPipes „Open_Palm“ erkannte die seitliche flache Hand nur in 7 von 47 Bildern.
- Fingerrichtung: erhobene flache Hand 0,95 bis 1,0, Hand flach auf dem Tisch −0,8, normal
  bewegte Hände höchstens 0,61. Ohne diese Prüfung löste die liegende Hand alle 1,2 s einen Stopp aus.
- Handgröße (mittlerer Abstand Handgelenk zu Fingeransätzen): nah an der Kamera 0,17 bis 0,28,
  aus normaler Sitzposition 0,10 bis 0,15, Hand an Maus oder Tastatur 0,07 bis 0,13.
- Bildrate: eine Hand 28 Bilder/s (32 ms), zwei Hände 15 bis 18 Bilder/s (54 bis 65 ms). MediaPipes
  reine Handerkennung ist nicht schneller als der Gesture Recognizer.

## Messwerte vom 29.10.2026

- Glaseffekt (`backdrop-filter: blur(28px)`) mit Kamera-Erkennung gleichzeitig, `?messen=1`:
  beim Gleiten 56 Bilder/s (8 von 703 Frames über 33 ms), in Ruhe 59 Bilder/s.
- Handerkennung bei 640 × 360 mit einer Hand: 30 Bilder/s, im Mittel 31 ms, etwa ein Kern. Mit
  15 Bildern/s gingen schnelle Wischbewegungen verloren.
- Temperatur 54 °C, keine Drosselung (`throttled=0x0`).

## Bekannte Grenzen

- Seit der Suche nach zwei Händen schafft die Kamera nur 15 bis 18 Bilder/s. Nahe, schnelle Wischer
  gehen dabei verloren (12 s nah wischen: 7 Bilder mit Hand, kein Wischer erkannt).
- Hände an Maus oder Tastatur haben Wischer ausgelöst. Eine Grenze für die Handgröße (nur nahe
  Hände zählen, etwa ab 0,16) ist gemessen, aber nicht eingebaut.
- Hält die Hand zwischen zwei Wischern kurz flach und aufrecht inne, zählt das als Stopp.
- Alle Werte stammen vom Schreibtisch. In der Küche hängt die Kamera über dem Display und die
  Abstände sind andere.
- Schrift: Auf dem Pi gibt es weder SF Pro noch Helvetica. Chromium nimmt Nimbus Sans, die keinen
  dünnen Schnitt hat.
