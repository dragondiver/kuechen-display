# Code auf das Küchen-Display bringen

`pi/push.sh` spiegelt den Ordner `pi/` vom Mac auf den Pi, startet den Küchen-Dienst neu und
lädt den Kiosk. Es ersetzt die einzelnen rsync-Zeilen, die vorher in den Anleitungen standen.

## Voraussetzungen

- Der Pi ist einmal eingerichtet: Geheimnisse aus 1Password (`docs/datenweg.md`, „Einrichten“)
  und Gerätewerte der Bridge (`docs/stimme-und-geste.md`, Schritt 2).
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
3. Spiegelt `pi/dienst`, `pi/gesten`, `pi/schlafen`, `pi/werkzeuge`, `pi/kiosk`, dazu die Wetterbilder aus
   `docs/entwuerfe/wetter/flach/` und die Figur aus `docs/entwuerfe/figur/*-klein.png`.
   Verglichen wird nach Inhalt, nicht nach Zeitstempel.
4. Ruft auf dem Pi `install-kiosk.sh` auf: venvs, Units, Neustart von `kuechen-dienst` und `kuechen-schlafen`
   (Display nach Ruhe aus, `docs/schlafen.md`).
   `kuechen-gesten` bleibt aus.
5. Beendet Chromium und startet ihn mit `kiosk-start.sh` neu.
6. Zeigt, ob der Dienst läuft, die letzten Zeilen aus dem Journal und ob Chromium läuft.

Ein laufendes Gespräch mit Elektra am Display bricht beim Neustart ab.

Der Küchen-Dienst liefert die Kiosk-Dateien mit `Cache-Control: no-cache` aus, Chromium fragt also bei jedem Laden nach
und holt nach einem Deploy die neue Seite (bei unveränderter Datei kommt ein 304). Ohne den Header zeigte der Kiosk
am 17.11.2026 auch nach einem Neustart die alte Startseite aus dem Plattencache; deshalb leert `kiosk-start.sh` einmalig
`~/.cache/chromium/Default/Cache` (nur den HTTP-Cache, keine Anmeldungen), erkennbar an `~/.cache/kuechen-display/http-cache.marke`.

## Kiosk mit Debug-Zeile

```bash
KIOSK_ZUSATZ='?debug=1' pi/push.sh
```

Nur den Browser neu starten, ohne etwas zu übertragen:

```bash
ssh kuechen-display.local "pkill -o -x chromium; i=0; while pgrep -x chromium >/dev/null && [ \$i -lt 20 ]; do sleep 0.5; i=\$((i+1)); done; if pgrep -x chromium >/dev/null; then pkill -x chromium; sleep 2; pkill -9 -x chromium; fi; setsid -f sh kuechen-display/kiosk-start.sh '?debug=1' </dev/null >/tmp/kiosk.log 2>&1"
```

Die Backslashes vor `$i` und `$((i+1))` stehen da, weil die Zeile in doppelten Anführungszeichen steht: Ohne sie würde schon der Mac die Variable ersetzen, und die Warteschleife bräche sofort ab.

`kiosk-start.sh` ist derselbe Aufruf, den der Autostart beim Hochfahren benutzt
(`~/.config/autostart/kiosk.desktop`). Es wartet bis zu 30 s auf den Küchen-Dienst, bevor es
Chromium startet.

## Was das Skript nicht macht

- Den Akku-Wächter (`pi/ups/`). Er läuft als root und ändert sich selten: `docs/akku-waechter.md`.
- Die Gerätewerte der Bridge auf raspi-agent (`pi/bruecke/geraete.conf`): `docs/stimme-und-geste.md`.
- Die `.env` mit den Geheimnissen. Die bringt `heim-agent/deploy/pi-env-push.sh kuechen-display`.
- Das Display einschalten. Ist es per `wlr-randr` aus, bleibt es aus. (Was `kuechen-schlafen` ausschaltet, schaltet
  es selbst wieder ein, auch bei `push.sh`; Notausgang in `docs/schlafen.md`.)

## Anderes Ziel

```bash
ZIEL=anderer-pi.local PFAD=kuechen-display pi/push.sh
```
