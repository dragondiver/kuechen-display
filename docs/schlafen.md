# Schlafen: Display nach Ruhe aus

Stand 16.11.2026, zu #48. Das Display geht nach 5 Minuten ohne Berührung aus und mit einem Tipp wieder an.
Der erste Tipp weckt nur: Er öffnet keine Kachel, startet kein Gespräch und klickt nichts in einer App.
Seit #89 weckt bei offenem Rezept auch das Wort „Weiter“ oder „Zurück“ (Abschnitt unten).
Wach bleibt es, solange ein Video läuft oder Elektra spricht oder ein Gespräch läuft. Spotify allein hält es
nicht wach. Nachts und im Akkubetrieb ist damit noch nichts entschieden, das bleibt in #48 offen.

## Wo die 5 Minuten stehen

In `pi/schlafen/schlafen.conf`, Zeile `RUHE_S=300`. Das ist die einzige Stelle. Ändern, dann `pi/push.sh`.
Zum schnellen Ausprobieren geht es auch direkt auf dem Pi (der nächste `pi/push.sh` setzt die Datei auf den
Stand des Repos zurück):

```bash
ssh kuechen-display.local 'sed -i "s/^RUHE_S=.*/RUHE_S=20/" kuechen-display/schlafen/schlafen.conf && sudo systemctl restart kuechen-schlafen'
```

Die zweite Einstellung, `AUS_WEG`, sagt, wie das Display ausgeht: `beides` (Ausgang aus und Beleuchtung auf 0),
`backlight` oder `ausgang`. Ein ungültiger Wert fällt auf den Standard zurück und steht als Fehler im Journal.

## Wie es funktioniert

Ein Dienst `kuechen-schlafen` (`pi/schlafen/schlafwaechter.py`, nur Python-Standardbibliothek) läuft neben
dem Küchen-Dienst. Er setzt sich aus drei Quellen zusammen.

- Ruhe: `swayidle` sieht alle Eingaben auf Ebene des Compositors, also auch die in einer App (Spotify) und
  die per VNC. Es meldet dem Wächter „ruhig“ nach einer Sekunde ohne Eingabe und „aktiv“ bei der nächsten.
  Der Wächter zählt die 5 Minuten selbst.
- Was wach hält: Der Küchen-Dienst beantwortet `GET /wach`. Elektra hält wach, solange ihr Zustand nicht
  „aus“ ist, also beim Zuhören, Nachdenken und Sprechen. Ein Video meldet die Rückweg-Erweiterung
  (`pi/kiosk-rueckweg/rueckweg.js`) alle 5 Sekunden, sobald auf der offenen Seite eins spielt. Der Dienst
  zählt es, wenn es spielt, ein Bild hat (Spotifys Audio-Element hat keins), nicht in Schleife läuft
  (Spotifys Canvas) und mindestens ein Fünftel des Fensters füllt (`pi/dienst/wach.py`). Bleibt die Meldung
  20 Sekunden aus, gilt das Video als beendet. Endet etwas, das wach gehalten hat, beginnen die 5 Minuten
  von da an neu.
- Weckwort (#89): Der Küchen-Dienst hört bei offenem Rezept auf „Weiter“ und „Zurück“
  (`docs/stimme-und-geste.md`). Bei dunklem Display weckt das Wort nur und blättert nicht. Dafür melden sich
  Wächter und Dienst gegenseitig: Der Wächter hängt an jede Frage `?dunkel=0` oder `?dunkel=1` an (dann mit dem Header `X-Kuechen: 1`, sonst antwortet der Dienst 403), der Dienst
  antwortet zusätzlich mit `start` (ändert sich bei jedem Start des Dienstes) und `wecken` (Zähler der Wörter,
  die das Display wecken sollen). Steigt der Zähler bei gleichem `start`, schaltet der Wächter das Display ein
  und die 5 Minuten beginnen neu. Bei dunklem Display fragt er jede Sekunde statt alle 5, damit das Wecken
  nicht bis zu 5 Sekunden dauert. Vor dem Ausschalten meldet er „dunkel“ und erst dann schaltet er ab; nach
  dem Einschalten meldet er „hell“. Schlägt das Einschalten fehl, gilt das Display weiter als dunkel.
  Erster Stand nach dem Start des Wächters oder des Dienstes wird nur gemerkt, er weckt nichts nachträglich.
- Entscheidung: `pi/schlafen/ruhe.py` ist reine Logik ohne Hardware und Uhr, mit Tests in `test_ruhe.py`.

Beim Ausschalten merkt sich der Wächter die Helligkeit (`/sys/class/backlight/10-0045/brightness`), setzt sie
auf 0 und schaltet den Ausgang mit `wlopm --off DSI-1` ab. Beim Wecken kommt erst der Ausgang, dann der
gemerkte Wert zurück, nicht fest 255. Der Wert liegt zusätzlich in `/run/kuechen-schlafen/helligkeit`, damit
ein abgestürzter und neu gestarteter Wächter ihn zurückgeben kann.

### Warum der erste Tipp verschluckt wird

labwc gibt eine Berührung auch bei ausgeschaltetem Ausgang an das Fenster darunter weiter. Im Quelltext
(labwc master, nicht die auf dem Pi laufende Version 0.20.2) schaltet `wlopm --off` nur den Ausgang ab, und
`handle_touch_down` fragt nicht nach, ob der Ausgang an ist. Darauf verlässt sich der Wächter nicht. Er sperrt
stattdessen den Touch, bevor das Display ausgeht: Er öffnet das Goodix-Gerät (`/dev/input/eventN`, gesucht
über den Namen „10-0014 Goodix Capacitive TouchScreen“ aus `labwc-rc.xml`) und setzt `EVIOCGRAB`. Solange
die Sperre steht, bekommt labwc nichts vom Touch. Der Wächter liest ihn selbst. Beim Aufsetzen des Fingers
schaltet er das Display an und gibt den Touch erst frei, wenn der Finger wieder oben ist, spätestens nach
5 Sekunden. So kommt weder das Aufsetzen noch das Loslassen in einem Fenster an. Eingaben, die nicht vom
Touch kommen (VNC, eine Tastatur), wecken ebenfalls, ohne dass es etwas zu verschlucken gibt. Elektra weckt
das Display nicht: Spricht sie bei dunklem Display von sich aus (eine Erinnerung), bleibt es dunkel und sie
kommt nur als Ton. Wach halten verhindert das Einschlafen, aufwecken kann es nichts. Aufwecken kann nur eine
Eingabe oder, bei offenem Rezept, das gesprochene „Weiter“ oder „Zurück“. Läuft beim Wecken per
Tipp noch ein Gespräch oder ein Video, beginnen die 5 Minuten erst nach dessen Ende.

### Wenn etwas ausfällt

Im Zweifel bleibt das Display an. Das gilt für jeden Fall, den der Wächter erkennt:

- `swayidle` stirbt: Fehler im Journal, Display an, nach 5 Sekunden neuer Start. Bis es wieder läuft, wird
  nicht geschlafen.
- Der Küchen-Dienst antwortet nicht: gilt als „hält wach“.
- Der Wächter meldet sich beim Dienst nicht (ausgeschaltet, hängt): Nach 15 Sekunden gilt das Display dem
  Dienst als „Zustand unbekannt“. Dann weckt das Weckwort nur und blättert nicht, und im Journal des Dienstes
  steht „Zustand des Displays unbekannt“. Das ist Absicht: Ein dunkles Display soll nie unbemerkt blättern.
- Der Touch lässt sich nicht sperren (Gerät nicht gefunden, keine Rechte) oder `wlopm` und die Beleuchtung
  gehen beide nicht: Fehler im Journal, das Display bleibt an, nächster Versuch nach einer Minute.
- Das Einschalten klappt nicht: Fehler im Journal, alle 3 Sekunden ein neuer Versuch.
- Der Wächter stirbt, auch mit `kill -9`: `ExecStopPost` ruft `schlafwaechter.py --an` auf, und `systemd`
  startet ihn nach 5 Sekunden neu. Beim Start gibt er ein dunkles Display zurück.

## Einrichten und aktualisieren

Nichts von Hand. `pi/push.sh` spiegelt `pi/schlafen/` nach `~/kuechen-display/schlafen/`, und
`install-kiosk.sh` installiert die Unit `kuechen-schlafen.service`, aktiviert sie und startet sie neu. Fehlen
`swayidle` oder `wlopm`, installiert es sie mit `apt`. Die Unit gibt dem Dienst die Gruppen `input` und
`video` und die Wayland-Umgebung (`WAYLAND_DISPLAY=wayland-0`, `XDG_RUNTIME_DIR=/run/user/1000`). Läuft
`push.sh` bei schlafendem Display, geht es dabei an.

## Nachsehen per SSH

```bash
# läuft der Wächter, was hat er zuletzt getan
ssh kuechen-display.local 'systemctl is-active kuechen-schlafen; journalctl -u kuechen-schlafen -n 25 --no-pager'

# live mitlesen
ssh kuechen-display.local 'journalctl -u kuechen-schlafen -f'

# was hält gerade wach (Küchen-Dienst)
ssh kuechen-display.local 'curl -s localhost:8080/wach'

# Beleuchtung und Ausgang
ssh kuechen-display.local 'cat /sys/class/backlight/10-0045/brightness; WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 wlopm'
```

Im Journal stehen: `Start: Ruhe 300 s, Aus-Weg beides`, `swayidle läuft`, `Wach halten: …` bei jeder
Änderung, `Display aus nach 300 s Ruhe` und `Display an: Berührung (verschluckt)`. Beim Küchen-Dienst
(`journalctl -u kuechen-dienst`) erscheint `Video: läuft, hält das Display wach`.

## Wenn das Display dunkel bleibt

Display einschalten, ohne etwas zu verstehen:

```bash
ssh kuechen-display.local 'WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 python3 kuechen-display/schlafen/schlafwaechter.py --an'
```

Das gibt die gemerkte Helligkeit zurück und schaltet den Ausgang an. Geht es auch dann nicht, hilft
`ssh kuechen-display.local 'sudo systemctl stop kuechen-schlafen'` (der Stopp schaltet selbst ein), notfalls
ein Neustart des Pi. Schlafen dauerhaft abschalten: `sudo systemctl disable --now kuechen-schlafen`. Zurück
geht es mit `pi/push.sh`.

Reagiert der Touch nach dem Wecken nicht, steht im Journal vermutlich `Berührung hängt länger als 5 s` oder
ein Touch-Fehler. Dann `sudo systemctl restart kuechen-schlafen`: Das schließt die Touch-Sperre.

## Abnahme am Gerät

Geprüft ist bisher nur, was ohne Pi geht (Tests, eine Attrappe von `swayidle`, `wlopm` und Touch, siehe
unten). Am Gerät mit Florian durchgehen, in dieser Reihenfolge:

1. Nach `pi/push.sh`: `systemctl is-active kuechen-schlafen` meldet `active`, das Journal zeigt `swayidle läuft`
   und keine Fehler. Fehler wegen `input` oder `Touch` heißen: Rechte am Goodix-Gerät fehlen.
2. Kurzer Probelauf: `RUHE_S=20` wie oben setzen und 25 Sekunden nichts tun. Das Display wird dunkel
   (Beleuchtung und Bild wirklich aus, nicht nur dunkelgrau), das Journal sagt `Display aus`.
3. Einmal auf die Kachel „Spotify“ tippen, während es dunkel ist: Das Display geht an, Spotify öffnet
   sich nicht, auch nicht beim Loslassen. Die Helligkeit ist wieder dieselbe wie vorher
   (`cat /sys/class/backlight/10-0045/brightness`). Der Kiosk ist noch maximiert und zeigt den Ruhebildschirm.
4. Ein zweiter Tipp bedient das Display wie immer (Gespräch starten, Kachel öffnen).
5. Elektra: Gespräch beginnen und 25 Sekunden schweigen. Das Display bleibt an
   (`curl -s localhost:8080/wach` zeigt `elektra (zuhoeren)`), nach Ende des Gesprächs geht es nach der
   Ruhezeit aus.
6. Video: ein Video abspielen, das mindestens ein Fünftel des Bildschirms füllt (ein Video in Kachelgröße zählt
   nicht), zum Beispiel über SSH (die
   Adresse eines Videos vorher einsetzen):
   `ssh kuechen-display.local 'WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 nohup chromium --ozone-platform=wayland "https://VIDEO-ADRESSE" >/dev/null 2>&1 &'`
   (das Fenster geht im laufenden Chromium auf, die Erweiterung ist also dabei; steht danach kein `Video: läuft`
   im Journal des Küchen-Dienstes, stimmt das nicht, dann gilt die Prüfung per `curl` unten). Das Display bleibt über die Ruhezeit hinaus an,
   `curl -s localhost:8080/wach` zeigt `video`. Pausieren oder Fenster schließen: Nach 20 Sekunden und der
   Ruhezeit geht es aus. Der Dienst lässt sich auch ohne Video prüfen:

   ```bash
   ssh kuechen-display.local "curl -s -X POST -H 'X-Kuechen: 1' -d '{\"videos\":[{\"spielt\":true,\"bild\":true,\"schleife\":false,\"flaeche\":0.9}]}' localhost:8080/video; curl -s localhost:8080/wach"
   ```
7. Spotify allein: Musik auf dem Evoke spielen, die Spotify-Seite offen lassen. Das Display geht nach der
   Ruhezeit aus, die Musik läuft weiter. `curl -s localhost:8080/wach` zeigt dabei `"haelt": false`.
8. Weckwort bei dunklem Display: Abnahme in `docs/stimme-und-geste.md`, Abschnitt „Weckwort“ (Punkt 4 dort).
9. Zum Schluss `RUHE_S=300` zurücksetzen (`pi/push.sh`) und prüfen, dass die Datei wieder 300 sagt.

## Nicht gemessen

Alles unten steht auf Annahmen aus Quelltext und Handbuch, nicht aus einem Lauf am Gerät.

- Ob swayidle unter labwc 0.20.2 eine Berührung als Eingabe zählt. Es ist der übliche Weg, aber nicht
  nachgemessen. Zeigt das Journal kein `Display aus` nach der Ruhezeit, ist das der erste Verdacht.
- Ob die Befehle von swayidle (`echo IDLE`, `echo AKTIV`) auf dem Pi in der Ausgabe des Wächters ankommen.
- Ob `wlopm --off DSI-1` das Waveshare-Panel dunkel macht und `--on` es wieder zurückbringt, ob die
  Beleuchtung auf 0 ganz dunkel ist (in #48 wurde nur der Strom gemessen) und ob das Fenster danach
  maximiert bleibt. Bleibt der Ausgang nach `--on` schwarz, `AUS_WEG=backlight` setzen.
- Ob `EVIOCGRAB` die Berührung wirklich vor labwc verbirgt und ob der Touch nach der Freigabe normal geht,
  auch wenn die Sperre mitten in einer Berührung freigegeben wird.
- Ob die Gruppe `input` in der Unit für `/dev/input/event*` reicht.
- Die Grenze von einem Fünftel der Fensterfläche für „ein Video“ und ob YouTube, Spotify und die Seiten
  der späteren Apps `<video>` so benutzen wie angenommen. Videos in eingebetteten Frames und im Shadow DOM
  sieht die Erweiterung nicht.
- Das Weckwort (#89): Wie schnell ein gesprochenes Wort das dunkle Display einschaltet (Erkennung, Zähler,
  Frage jede Sekunde, `wlopm --on`), ob die Seite bei dunklem Display als verborgen gilt und ihre Zeitgeber
  gedrosselt werden, und ob `EVIOCGRAB` beim Wecken ohne Berührung etwas stört (es gibt dann keine Sperre
  zu lösen, der Weg ist wie bei „Eingabe nicht Touch“).
- Die Ersparnis an Strom. Aus #48 gilt: Beleuchtung aus spart rund 1,5 bis 2 W, ob der abgeschaltete
  Ausgang mehr bringt, ist offen.

Was ohne Pi geprüft ist: die Logik in `test_ruhe.py`, `test_wach.py` und `test_schlafwaechter.py`
(`python3 -m pytest -q pi`), dazu ein Lauf der Schleife von `schlafwaechter.py` auf dem Mac gegen
Attrappen (Aus nach Ruhe, Wecken beim Tippen, Freigabe nach dem Loslassen, Helligkeit zurück, Notausgang
bei SIGTERM). Die Attrappen ersetzen swayidle, wlopm, die Beleuchtung und das Touch-Gerät.
