# Stimme auf dem Küchen-Display

Stand 8.11.2026, zu #15 und rundfunk#128. Das Display ist ein Netz-Gerät der rundfunk-Bridge auf
raspi-agent. Ein Tipp aufs Mikrofon startet ein Gespräch mit Elektra, ihre Antwort kommt über den
Standard-Ausgang des Pi (beim Tischtest die Shokz per Bluetooth). Elektra kann dabei die Seiten
der Anzeige wechseln.

## Was läuft

| Teil | Datei im Repo | Wo |
|---|---|---|
| Küchen-Dienst: Seite, Bridge, Ton | `pi/dienst/dienst.py`, `vertrag.py` | Pi, Dienst `kuechen-dienst`, venv `~/kuechen-venv` |
| Weckwort „Weiter“/„Zurück“ | `pi/dienst/weckwort.py` | im Küchen-Dienst, Modell unter `~/kuechen-display/modelle/` |
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
| Tipp, die Bridge ist nicht erreichbar (Mikrofon blass) | vier Sekunden „Elektra ist gerade nicht erreichbar“, es beginnt nichts (#50) |
| flache Hand vor der Kamera, während sie spricht | wie Tipp beim Sprechen (Kamera nur beim Testen) |

Das Mikrofon sitzt auf der Seite „Heute“ an der Figur. In einer App wie Spotify ist die Kiosk-Seite
weg; dort ist der Mikro-Knopf ganz rechts in der Rückweg-Leiste oben links (#70). Er wirkt wie der
Tipp aufs Mikrofon und leuchtet orange, solange Elektra dran ist.

## Was Elektra am Display kann

| Werkzeug | Beispiel | Wirkung |
|---|---|---|
| `seite_zeigen` | „zeig mir morgen“, „zurück zu heute“, „zeig die Apps“ | wechselt die Seite, aus einer App heraus zurück zum Kiosk |
| `app_oeffnen` | „öffne Spotify“, „öffne Rezepte“ | öffnet die App; bietet die Bridge nur an, weil der Dienst `APPS = ["spotify", "rezepte"]` meldet |
| `rezeptschritt` | „nächster Schritt“ | in der Koch-Ansicht von mise-en-place (`mise-en-place.fhuber.com/<locale>/kd/recipes/<id>`): `richtung` `vor` oder `zurueck` löst Pfeil rechts bzw. links aus, die Ansicht blättert. Auf der Rezeptauswahl (`/<locale>/kd/recipes`, ohne id) lösen `vor` und `zurueck` Pfeil runter bzw. hoch aus, die Liste blättert um eine Bildschirmhöhe. Auf der Übersicht eines Rezepts (`/<locale>/kd/recipes/<id>/overview`) löst `vor` Pfeil rechts aus (die Übersicht startet damit das Kochen), `zurueck` gibt dort eine kurze Fehlermeldung. Sonst hört Elektra „Es ist kein Rezept offen“ |

Eine neue App braucht drei Stellen: den Namen in `APPS` (`pi/dienst/dienst.py`), `data-app` an ihrer
Kachel (`pi/kiosk/index.html`) und den Eintrag in `APPS` von `pi/kiosk-rueckweg/rueckweg.js`.

**Befehle in einer App.** Ist eine App vorn, hält der Küchen-Dienst einen Befehl der Bridge vier
Sekunden bereit. Die Rückweg-Leiste fragt jede Sekunde `GET http://localhost:8080/lage` mit dem Header
`X-Kuechen: 1` ab (über `hintergrund.js`, weil die https-Seite localhost nicht selbst fragen darf; ohne den Header
antwortet der Dienst 403, #120), bekommt Elektras
Zustand und einen wartenden Befehl, führt ihn aus und quittiert. Holt ihn niemand ab, hört Elektra
„Die Anzeige ist nicht offen“. Als „App vorn“ gilt: Die Leiste hat in den letzten 2,5 Sekunden
gefragt und seitdem hat sich keine Kiosk-Seite verbunden.

Beim Beenden per Tipp schickt das Display `{"type":"ende"}` an die Bridge (seit 15.11.2026,
rundfunk#238). Sie schließt die Live-Sitzung sofort und antwortet mit dem Zustand „aus“. Vorher
wartete sie bis zu ihrer Ruhezeit.

**Lautstärke an die Bridge (#105, rundfunk#253).** Das Display meldet seine Schieberstellung. Die erste
Nachricht nach dem Verbinden ist `{"type":"hallo","apps":[…],"lautstaerke":N}` mit N von 0 bis 100, der
Stellung beim Verbinden (die gemerkte, auch wenn PipeWire noch nicht da ist). Danach geht bei jeder Änderung
`{"type":"lautstaerke","wert":N}` an die Bridge, egal ob der Schieber in der Leiste, der auf den Hauptseiten
oder ein Befehl der Bridge sie ausgelöst hat. Beim Ziehen kommt jede Zwischenstellung einzeln, in der
Reihenfolge der Änderungen, der zuletzt gemeldete Wert ist der Endstand. Die Bridge antwortet nicht. Ohne
Leitung wird nichts gesendet und nichts aufgehoben; beim nächsten Verbinden steht der Stand im hallo. Eine
Bridge ohne diese Nachricht warnt im Log und ignoriert das Feld im hallo. Von der Bridge zum Display gilt
weiter `{"type":"lautstaerke","wert":0..100}`.

## Diktat ins Suchfeld

Ohne Elektra (#70, Festlegung 15.11.2026). Bekommt in einer App ein Textfeld den Fokus, zum Beispiel
Spotifys Suche „Was möchtest du wiedergeben?“, erscheint darunter der Knopf „Sprechen“. Tippen und
sprechen. Nach zwei Sekunden Pause hört er von selbst auf; noch mal tippen beendet sofort. Wer
nichts sagt, hat 10 Sekunden Bedenkzeit, länger als 20 Sekunden nimmt er nie auf (alle drei Werte
Florian, 15.11.2026: 1 s Pause hätte bei „spiel was von … äh … Queen“ zu früh geschnitten). Der Text
ersetzt den Inhalt des Feldes, ein Punkt am Ende fällt weg.

Die Rezeptauswahl von mise-en-place (mise-en-place#223) hat einen eigenen Mikrofon-Knopf und markiert ihn mit
`data-kd-diktat="<id des Textfelds>"`, etwa `<button data-kd-diktat="kd-suche">` neben
`<input id="kd-suche" type="search">`. Ein Tipp darauf startet das Diktat sofort, ohne das Feld zu fokussieren (der Fokus würde die Bildschirmtastatur hochholen; hat das Feld ihn schon, bleibt er),
der nächste Tipp während „Hört zu …“ beendet es; der Knopf „Sprechen“ zeigt dabei den Stand (nächster Absatz). Das Attribut wirkt nur auf `mise-en-place.fhuber.com` (`KOCH_ANSICHT.host` in `rueckweg.js`)
und nur bei echten Tipps (`isTrusted`); ein Skript mit `el.click()` startet nichts, und auf jedem anderen
Host bleibt es ohne Wirkung. Behandelt die Erweiterung den Tipp, kommt er bei der Seite nicht mehr an (ein eigener
`onClick`, der das Feld fokussiert, würde sonst die Tastatur hochholen). Gibt es die id nicht oder ist es kein
Textfeld, passiert nichts, die Seite bekommt den Tipp dann und fokussiert selbst. Während „Erkenne …“ und bei Fehlern tut der Tipp ebenfalls nichts.
Hat die Seite für das Feld einen eigenen Knopf, blendet die Erweiterung ihren Knopf „Sprechen“ im
Ruhezustand gar nicht erst ein. Während „Moment …“, „Hört zu …“, „Erkenne …“ und bei Fehlern erscheint er als
Anzeige in der Suchzeile, rechtsbündig an der linken Kante des Seitenknopfs und senkrecht mittig zu ihm, damit er
keinen Treffer verdeckt; ein Tipp darauf beendet die Aufnahme wie sonst. Endet das Diktat ohne Text, geht der
Stand auf „bereit“ zurück und der Knopf verschwindet. Auf anderen Seiten (Spotify) bleibt alles beim Alten.

Wer einen ganzen Satz sagt („spiel mir was von Queen“), bekommt nur den Suchbegriff ins Feld
(Florian, 15.11.2026). Ab vier Wörtern fragt der Dienst `gpt-6-luna`, was davon gesucht ist. Der
Code nimmt die Antwort nur, wenn sie kurz ist, einzeilig und mindestens ein Wort mit dem Gesagten
teilt. Sonst, und wenn das Modell nicht antwortet, kommt der erkannte Satz ins Feld. Bis drei Wörter
geht der Text ohne Modell durch, das ist dann schon ein Name. Die Anfrage läuft über OpenAIs Priority-Stufe, weil die Standardstufe
bei Messungen vom Pi bis 4,3 s brauchte, Priority höchstens 1,1 s. Sie kostet ungefähr 0,005 Cent.

Die Pause misst der Pegel: Der Boden ist das 10. Perzentil der Rahmen vor dem Sprechen. Sprache
heißt drei Rahmen (180 ms) mindestens 15 dB über dem Boden, Ruhe heißt unter Boden + 8 dB. Die
Werte stehen oben in `pi/dienst/diktat.py`. Zum Nachstellen schreibt der Dienst pro Diktat Dauer,
Grund fürs Ende, Boden und Spitze ins Journal:
`journalctl -u kuechen-dienst | grep Diktat`.

Der Küchen-Dienst nimmt dafür Kanal 0 des XVF3800 auf (`POST /diktat/start`, `/diktat/stopp`, `/diktat/ergebnis`,
`pi/dienst/diktat.py`) und schickt den Ton als WAV an die OpenAI-Transkription, Modell
`gpt-transcribe` (änderbar über `DIKTAT_MODELL`), Sprachen Deutsch und Englisch. Er braucht
`OPENAI_API_KEY` im 1Password-Environment `kuechen-display` (`docs/datenweg.md`). Ins Journal
schreibt er nur Längen und Zeiten, nicht was gesucht wurde. Kosten laut OpenAI 0,0045 $ pro Minute Ton.

Zum Prüfen ohne Finger: `wtype` ist auf dem Pi installiert. `wtype -M ctrl k -m ctrl` öffnet in
Spotify den Suchdialog (mit `XDG_RUNTIME_DIR` und `WAYLAND_DISPLAY=wayland-0`).

## Weckwort „Weiter“ und „Zurück“

Seit #89, Stand 18.11.2026. Ist ein Rezept von mise-en-place offen, hört das Display auf zwei Wörter. Der
Ton wird auf dem Pi ausgewertet, es verlässt kein Ton das Gerät.

| Lage | „Weiter“ / „Zurück“ |
|---|---|
| Rezept offen, Display an | blättert wie der Befehl `rezeptschritt` (`vor` bzw. `zurueck`), ohne Tipp und ohne Elektra |
| Rezept offen, Display dunkel | weckt nur, blättert nicht; das Display geht an und die 5 Minuten beginnen neu |
| Rezept offen, Zustand des Displays unbekannt | wie dunkel: wecken, nicht blättern |
| kein Rezept offen | nichts, der Ton wird nicht ausgewertet |
| Elektra hört zu, denkt oder spricht; ein Diktat läuft; Wiedergabe läuft | nichts, dazu noch 1,5 Sekunden danach |

„Rezept offen“ heißt: Auswahl, Übersicht oder Koch-Ansicht von mise-en-place, genau die Seiten, für die
`schrittTasten()` in `rueckweg.js` Tasten kennt. Auf der Übersicht blättert „Zurück“ nicht (dort gibt es nur
„vor“); es passiert nichts, im Journal steht „Hier geht es nur vor.“. „Zurück“ bei dunklem Display weckt nur,
wie „Weiter“ (Ergänzung zur Festlegung vom 18.11.2026).

### Wie es funktioniert

- Erkennung: Vosk (`pi/dienst/weckwort.py`) mit dem kleinen deutschen Modell `vosk-model-small-de-0.15` und
  einer Grammatik, die nur „weiter“, „zurück“ und „[unk]“ (alles andere) kennt. Sie liest dieselben Rahmen
  von Kanal 0 wie der Rest des Dienstes (`mikro_schleife`), in einem eigenen Faden, damit die
  Mikrofon-Schleife nie wartet.
- Es zählt nur ein Wort für sich allein, auch doppelt („weiter weiter“). „Wie geht es weiter“ erkennt die
  Grammatik als „[unk] [unk] [unk] weiter“ und löst nichts aus; ebenso eine Äußerung mit beiden Wörtern.
  Solche Fälle mit einem Wort darin stehen als „Verworfen, …“ im Journal. Das Wort allein ist die
  strengere Wahl; sie kostet vermutlich einige Treffer und lässt sich in `wort_lesen` lockern.
- Dasselbe Wort nicht zweimal innerhalb von 1,5 Sekunden.
- Rezept offen: Die Rückweg-Erweiterung meldet alle 2 Sekunden `POST /rezept {"offen": true}` (auch bei
  verborgener Seite, anders als die Abfrage von `/lage`). Der Dienst lässt die Meldung nach 8 Sekunden ohne
  Nachricht verfallen. Ist das Display seit der letzten Meldung dunkel geworden, verfällt sie nicht: Ein beim
  Einschlafen offenes Rezept bleibt offen, bis das Display wieder an ist oder die Kiosk-Seite sich meldet. Die
  Erweiterung meldet beim Verlassen der Seite „zu“, und der Dienst setzt „offen“ zurück, wenn die Kiosk-Seite
  sich verbindet.
- Display dunkel oder hell: Der Schlafwächter meldet es mit `GET /wach?dunkel=0|1` und dem Header `X-Kuechen: 1` (`docs/schlafen.md`; ohne Header antwortet der Dienst 403, das reine Lesen von `/wach` braucht ihn nicht). Schlägt die Meldung fehl, wiederholt der Wächter sie dreimal und schreibt jeden Fehlschlag ins Journal. Eine
  Meldung gilt 15 Sekunden. Davor und danach ist der Zustand unbekannt, und unbekannt heißt wecken, nicht
  blättern: Ein Wecken bei hellem Display schadet nicht, ein Blättern bei dunklem bliebe unbemerkt.
- Blättern bei hellem Display: Der Dienst legt in die Ablage (`Ablage`, wie ein Befehl der Bridge) einen lokalen
  Befehl `rezeptschritt` mit der Kennung `lokal-<n>`. Die Erweiterung holt ihn über `/lage` ab, löst die Taste
  aus und quittiert. Die Quittung eines lokalen Befehls geht nicht an die Bridge (sie kennt die Nummer nicht),
  sondern steht im Journal, ebenso ein Befehl, den niemand abgeholt hat.
- Ein erkanntes Wort hält das Display 6 Sekunden lang wach (Grund `weckwort` in `/wach`): Wer nur per Zuruf
  blättert, fasst es nicht an.

### Sichtbarkeit

Solange die Erkennung mithört (Rezept offen, kein Gespräch, kein Diktat), steht am Mikro-Knopf der
Rückweg-Leiste ein kleiner Punkt in Mintgrün. Er bewegt sich nicht. Nach einem erkannten Wort wächst er
0,7 Sekunden lang. Bei hellem Display ist das Blättern selbst die Rückmeldung, bei dunklem das Display, das
angeht.

### Einrichten

`pi/install-kiosk.sh` (aufgerufen von `pi/push.sh`) installiert `vosk` in `~/kuechen-venv` und holt das
Modell nach `~/kuechen-display/modelle/vosk-model-small-de-0.15`, aber nur, wenn es fehlt. Es lädt von
`https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip` (rund 45 MB) und prüft die SHA-256-Summe der
Zip-Datei, bevor es entpackt. Die Summe steht in `VOSK_SHA256` in `pi/install-kiosk.sh` (gemessen am 18.11.2026). Steht dort der Platzhalter
`HIER_PRUEFSUMME_EINTRAGEN`, lädt das Skript nichts und meldet das. Das Weckwort darf beim Einrichten ausfallen (Pi offline, Download oder
Prüfsumme schlägt fehl): Das Skript nennt den Grund, richtet Dienst, Wächter und Kiosk trotzdem ein und weist am
Ende noch einmal darauf hin. Ein erneuter Lauf mit Netz holt Vosk und das Modell nach.

Fehlt das Paket oder das Modell, läuft der Dienst unverändert weiter und schreibt einmal beim Start
`Weckwort nicht verfügbar: …` ins Journal. Die Tests und die CI brauchen kein Vosk
(`pi/requirements-test.txt` bleibt wie es ist).

### Abschalten

In `pi/dienst/kuechen-dienst.service` steht die Zeile `Environment=WECKWORT=an`. Auf `aus` setzen und
`pi/push.sh` ausführen; im Journal steht dann `Weckwort aus`. Ein anderer Wert ist ein Fehler im Journal, und
das Weckwort bleibt aus. Direkt auf dem Pi, bis der nächste `push.sh` die Datei zurücksetzt:

```bash
ssh kuechen-display.local 'sudo sed -i "s/^Environment=WECKWORT=.*/Environment=WECKWORT=aus/" /etc/systemd/system/kuechen-dienst.service && sudo systemctl daemon-reload && sudo systemctl restart kuechen-dienst'
```

### Nachsehen per SSH

```bash
# läuft es, hat es das Modell gefunden
ssh kuechen-display.local 'journalctl -u kuechen-dienst -n 40 --no-pager | grep -i -E "weckwort|rezept"'

# live mitlesen: erkannte Wörter, Rezept offen/zu, Wecken, Blättern
ssh kuechen-display.local 'journalctl -u kuechen-dienst -f | grep -i -E "weckwort|rezept"'

# Stand: hört die Erkennung (weckwort), wie viele Wörter, was hält wach, Zähler fürs Wecken
ssh kuechen-display.local 'curl -s -H 'X-Kuechen: 1' localhost:8080/lage; echo; curl -s localhost:8080/wach'

# Last der Erkennung
ssh kuechen-display.local 'top -b -n1 -H -p $(systemctl show -p MainPID --value kuechen-dienst) | head -15'
```

### Abnahme am Gerät

Mit Florian, in dieser Reihenfolge. Bis hierher ist nichts davon am Gerät gelaufen.

1. Nach `pi/push.sh`: Journal zeigt `Weckwort bereit (Modell vosk-model-small-de-0.15)`. Die Erweiterung ist neu
   zu laden (Version 17); sonst fehlt die Meldung „Rezept offen“.
2. Rezept öffnen (Koch-Ansicht), `curl -s -H 'X-Kuechen: 1' localhost:8080/lage` zeigt `"weckwort": true`, am Mikro-Knopf steht der
   Punkt. „Weiter“ sagen: Das Rezept blättert, der Punkt wächst kurz, das Journal zeigt `blättern vor`.
   Dasselbe mit „Zurück“. Auf der Übersicht: „Weiter“ startet das Kochen, „Zurück“ tut nichts.
3. Kein Rezept (Heute, Spotify): „Weiter“ sagen, nichts passiert, kein Punkt, kein Journaleintrag.
4. Rezept offen, `RUHE_S=20` setzen (`docs/schlafen.md`), das Display schlafen lassen. „Weiter“ sagen: Das
   Display geht an, das Rezept blättert nicht, im Journal steht `wecken (Display dunkel)`. Weckdauer mit der
   Uhr messen. Danach ein zweites „Weiter“: Es blättert.
5. Elektra: Gespräch beginnen und „Weiter“ sagen. Das Rezept blättert nicht. Beim Beenden des Gesprächs
   dauert es 1,5 Sekunden, bis die Erkennung wieder auswertet. Dasselbe beim Diktat.
6. Elektra spricht lange (Antwort mit „weiter“ im Text): löst nichts aus.
7. Küchengeräusche und Musik: Abzug, Wasserhahn, Spotify auf dem Evoke laufen lassen und mitzählen, wie oft das
   Rezept ungewollt blättert (Journal: `Weckwort „…“`).
8. Last: `top` wie oben, während gesprochen wird und während Ruhe ist.
9. Dienst von Hand beenden und starten: Im Journal steht kein Wecken beim Start eines schlafenden Displays.

### Nicht gemessen

Alles hier ist aus Quelltext und Handbuch, nicht aus einem Lauf am Gerät.

- Ob Vosk auf dem Pi 5 unter Python 3.13 läuft (das Rad `py3-none-manylinux2014_aarch64` für 0.3.45 gibt es
  auf PyPI) und wie hoch die Last der Erkennung ist.
- Ob „weiter“ und „zurück“ im Wörterbuch des Modells stehen (die Grammatik braucht beide) und wie viele Wörter
  die Erkennung trifft, vom Herd, vom Tisch, mit Küchengeräuschen und mit Musik.
- Wie oft „[unk]“ um ein echtes Wort steht und es als „nicht allein gesagt“ durchfällt. Zu viele Verluste:
  `wort_lesen` lockern.
- Die Wartezeit von „Weiter“ gesagt bis Blättern (Erkennung am Ende der Äußerung, Abholen über `/lage` jede
  Sekunde, Taste) und bis zum Einschalten des dunklen Displays (Erkennung, Frage jede Sekunde, `wlopm --on`).
- Ob die Seite bei dunklem Display als `hidden` gilt und ihre Zeitgeber gedrosselt werden. Der Dienst hält
  das Rezept dafür fest, aber ob es nötig ist, ist offen. Ebenso, ob die Rezept-Seite nach dem Einschlafen
  weiter ihre Tasten annimmt, wenn der Befehl beim Display an ankommt.
- Ob Elektras eigene Stimme (Bluetooth, ohne Echounterdrückung) trotz Sperre noch Wörter auslöst, die als
  Nachlauf nach 1,5 Sekunden ankommen.
- Ob Musik auf dem Evoke ungewollt „Weiter“ oder „Zurück“ auslöst.

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

`install-kiosk.sh` legt `~/kuechen-venv` (`websockets`, `vosk`) und `~/gesten-venv` (MediaPipe) an,
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
ssh kuechen-display.local 'curl -s -X POST -H "X-Kuechen: 1" -d "{\"text\": \"Hallo\"}" http://127.0.0.1:8080/hinweis'
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
