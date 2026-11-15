# Code auf das Küchen-Display bringen

`pi/push.sh` spiegelt den Ordner `pi/` vom Mac auf den Pi, startet den Küchen-Dienst neu und
lädt den Kiosk. Es ersetzt die einzelnen rsync-Zeilen, die vorher in den Anleitungen standen.

## Voraussetzungen

- Der Pi ist einmal eingerichtet: Token und Gerätewerte der Bridge, siehe
  `docs/stimme-und-geste.md`, Schritte 1 und 2.
- ssh auf `kuechen-display.local` geht mit Schlüssel, `sudo` dort ohne Passwort.
- Auf dem Mac ist `pytest` installiert (`pip install -r pi/requirements-test.txt`).

## Erst ansehen, was sich ändern würde

```bash
NUR_ZEIGEN=1 pi/push.sh
```

Das ändert nichts auf dem Pi. Zeilen mit `<` würden übertragen, Zeilen mit `*deleting` würden
gelöscht. Bleibt die Liste leer, ist der Pi auf dem Stand des Checkouts.

## Ausrollen

```bash
pi/push.sh
```

Der Ablauf:

1. Zeigt Branch und Commit. Es warnt, wenn uncommittete Änderungen mitgehen oder der Checkout
   nicht `origin/main` ist. Gespiegelt wird immer der lokale Checkout, also vorher
   `git pull`, wenn `main` auf den Pi soll.
2. Lässt die Tests laufen und bricht ab, wenn einer fehlschlägt.
3. Spiegelt `pi/dienst`, `pi/gesten`, `pi/werkzeuge`, `pi/kiosk`, dazu die Wetterbilder aus
   `docs/entwuerfe/wetter/flach/` und die Figur aus `docs/entwuerfe/figur/*-klein.png`.
   Verglichen wird nach Inhalt, nicht nach Zeitstempel.
4. Ruft auf dem Pi `install-kiosk.sh` auf: venvs, Units, Neustart von `kuechen-dienst`.
   `kuechen-gesten` bleibt aus.
5. Beendet Chromium und startet ihn mit `kiosk-start.sh` neu.
6. Zeigt, ob der Dienst läuft, die letzten Zeilen aus dem Journal und ob Chromium läuft.

Ein laufendes Gespräch mit Elektra am Display bricht beim Neustart ab.

## Kiosk mit Debug-Zeile

```bash
KIOSK_ZUSATZ='?debug=1' pi/push.sh
```

Nur den Browser neu starten, ohne etwas zu übertragen:

```bash
ssh kuechen-display.local "pkill -x chromium; sleep 1; setsid -f sh kuechen-display/kiosk-start.sh '?debug=1' </dev/null >/tmp/kiosk.log 2>&1"
```

`kiosk-start.sh` ist derselbe Aufruf, den der Autostart beim Hochfahren benutzt
(`~/.config/autostart/kiosk.desktop`). Es wartet bis zu 30 s auf den Küchen-Dienst, bevor es
Chromium startet.

## Was das Skript nicht macht

- Den Akku-Wächter (`pi/ups/`). Er läuft als root und ändert sich selten: `docs/akku-waechter.md`.
- Die Gerätewerte der Bridge auf raspi-agent (`pi/bruecke/geraete.conf`): `docs/stimme-und-geste.md`.
- Das Display einschalten. Ist es per `wlr-randr` aus, bleibt es aus.

## Anderes Ziel

```bash
ZIEL=anderer-pi.local PFAD=kuechen-display pi/push.sh
```
