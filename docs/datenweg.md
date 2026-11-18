# Datenweg: Wetter und Termine auf dem Ruhebildschirm

Stand 18.11.2026, zu #15. Wetter und Termine kommen aus Home Assistant.

## Wie das Wetter auf die Seite kommt

```
Home Assistant (raspi-agent:8123)
   │  alle 10 Minuten, nur lesen
   ▼
Küchen-Dienst  pi/dienst/hass.py   holt Entität, Vorhersage, Temperatur, Sonnenstand
               pi/dienst/daten.py  macht daraus die Wetterkarte (reine Funktion, getestet)
   │  Ereignis „wetter“ über /ereignisse
   ▼
Kiosk-Seite    setzt Ort, Temperatur, Lage, zweite Zeile und das Hintergrundbild
```

Der Dienst fragt vier Dinge ab:

| Was | Woher | Wofür |
|---|---|---|
| Wetterlage | `weather.stuttgart_schn` | Text („Bedeckt“) und Wahl des Bildes |
| Tagesvorhersage | Dienst `weather.get_forecasts`, `daily` | zweite Zeile |
| Temperatur | `sensor.stuttgart_schn_temperatur` | große Zahl; fehlt der Sensor, gilt die Temperatur der Wetter-Entität |
| Sonnenstand | `sun.sun` | Nachtbild |

Die Temperaturquelle ist dieselbe wie bei den Rollladen-Regeln (DWD Stuttgart-Schnarrenberg,
Festlegung vom 18.9.2026).

## Regeln

- Jede Wetterlage von Home Assistant hat einen Text und eines der sechs Bilder. Die Tabelle
  steht oben in `pi/dienst/daten.py` (`LAGEN`).
- Steht die Sonne unter dem Horizont, ersetzt das Nachtbild die trockenen Bilder. Regen und
  Schnee bleiben, davon gibt es kein Nachtbild.
- Zweite Zeile: immer „Nacht 5°“, der Tiefstwert aus der Tagesvorhersage, tags wie nachts.
  Ohne Vorhersage bleibt sie leer.
- Eine Lage, die die Tabelle nicht kennt, steht im Klartext auf der Karte, bekommt das Bild
  „gedämpft“ und eine Warnung im Journal.
- Antwortet Home Assistant nicht, behält die Seite den letzten Stand. Ist er älter als eine
  Stunde, wird die Wetterkarte blass. Ohne jeden Stand steht dort „Keine Wetterdaten“.

Zweite Zeile, Nachtbild und Verblassen nach einer Stunde hat Florian am 15.11.2026 so
festgelegt (#15).

## Wetterwarnung

Ab Stufe 2 steht unten in der Wetterkarte eine Zeile: Punkt in der DWD-Farbe, Name und Ende,
etwa „Sturmböen bis 18 Uhr“. Festlegung 18.11.2026 in #37. Kein Band, kein Blinken, Antippen tut
nichts, die Vorwarnstufe (`sensor.kreis_ludwigsburg_vorwarnstufe`) steht nicht auf dem Display.

Dieselbe Verbindung, ein Abruf mehr: Der Dienst liest `sensor.kreis_ludwigsburg_aktuelle_warnstufe`
(Kern-Integration `dwd_weather_warnings`) und legt das Ergebnis als Feld `warnung` ins Ereignis
„wetter“. Die Warnung altert damit wie das Wetter: Sie bleibt beim letzten Stand stehen, nach
einer Stunde wird die ganze Karte blass.

Der Sensor hat die Attribute `warning_count` und je Warnung `warning_N_name`, `_level`, `_end`,
`_color` (N ab 1). Die Auswahl steht in `warnung_aufbereiten` (`pi/dienst/daten.py`, getestet):

- Stufe 1 zählt nicht, Warnungen mit Ende in der Vergangenheit auch nicht.
- Es gewinnt die höchste Stufe, bei gleicher Stufe das früheste Ende. Die DWD liefert gleichzeitige
  Warnungen in wechselnder Reihenfolge, die Reihenfolge der Attribute spielt keine Rolle.
- Gibt es mehr als eine, steht hinter der Zeile „+1“ (oder „+2“ …): die Zahl der übrigen Warnungen
  ab Stufe 2, die noch laufen. Die Zeile bleibt einzeilig, ein langer Name wird mit „…“ gekürzt.
- Ende heute: „bis 18 Uhr“ (mit Minuten „bis 16:30 Uhr“), morgen „bis morgen 6 Uhr“, später
  „bis Fr 12 Uhr“.
- Farbe aus `warning_N_color`. Ist sie kein Hex-Wert wie `#ff9900`, gilt die DWD-Farbe der Stufe
  (2 orange, 3 rot, 4 violett).
- Sensor nicht verfügbar, unbekannt, ohne Attribute oder ohne passende Warnung: keine Zeile, die
  Karte sieht aus wie ohne Warnung. Kennt Home Assistant den Sensor nicht, fehlt nur die Zeile.

Der Sensor ist über `WARNUNG_SENSOR` einstellbar (Drop-in der Unit wie unten). Leer heißt: keine
Warnung abfragen. Der Dienst prüft das Ende nur beim Abruf alle zehn Minuten; eine abgelaufene
Warnung kann bis dahin stehen bleiben.

Prüfen: Im Ereignis „wetter“ (`curl` wie oben) steht `"warnung": null` oder `{"text": …, "farbe": …,
"mehr": …}`.

## Wenn etwas fehlt

Festlegung 18.11.2026 in #50. Die Seite hat drei Zeichen dafür, jedes ohne Dialog und ohne Ton.

| Was fehlt | Was die Seite zeigt |
|---|---|
| Home Assistant antwortet länger als eine Stunde nicht | Wetterkarte und Termine blass, mit dem letzten Stand |
| Die Bridge ist nicht erreichbar | Mikrofon blass; ein Tipp darauf zeigt vier Sekunden lang „Elektra ist gerade nicht erreichbar“ |
| Der Pi hat kein Netz | Karten blass, unten links „Kein Netz“ |

**Alter.** Wetter und Termine tragen `stand`, die Zeit ihres letzten erfolgreichen Abrufs. Die
Seite vergleicht jede Minute: Ist `stand` mehr als eine Stunde her, wird blass (`istAlt` in
`pi/kiosk/regeln.js`, getestet in `pi/dienst/test_regeln.py`). Genau eine Stunde gilt noch als frisch,
ohne Stand wird nichts blass. Bei den Terminen bleiben Uhr, Datum und die Seitenüberschriften
„Morgen“ und „Die Woche“ stehen, blass werden Überschrift der Liste, Einträge und „Morgen ›“.

**Tipp ohne Bridge.** Der Dienst nimmt den Tipp dann gar nicht erst als Gesprächsbeginn: Er schickt
das Ereignis `hinweis` mit dem Text, der Zustand bleibt „aus“, das Mikrofon geschlossen
(`Leitung.tipp(verbunden=False)` in `pi/dienst/vertrag.py`). Die Seite zeigt den Text in der Zeile,
in der sonst Elektras Worte stehen, und nimmt ihn nach vier Sekunden wieder weg. Mit Bridge ändert
sich am Tipp nichts.

**Kein Netz.** Der Dienst kann nicht sehen, ob das WLAN da ist, aber ob das System noch eine
Standardroute hat: Fällt das WLAN aus, nimmt der Netzwerkdienst sie aus `/proc/net/route`. Alle
fünf Sekunden liest `netz_schleife` (`pi/dienst/dienst.py`, Logik in `pi/dienst/netz.py`) die Datei.
Fehlt die Route zweimal hintereinander, schickt der Dienst das Ereignis `netz` mit `da: false`, bei
der Rückkehr mit `da: true`; neue Seiten bekommen den Stand sofort. Die Seite macht dann beide
Karten sofort blass (ohne eine Stunde zu warten) und zeigt „Kein Netz“. Beim Zurückkommen
verschwindet die Zeile, und das Blasse hängt wieder nur am Alter.

Warum nicht „Home Assistant und Bridge beide weg“: Beide laufen auf raspi-agent. Ein abgeschalteter
raspi-agent bei gesundem WLAN wäre dann auch „Kein Netz“, und ohne `HA_TOKEN` gäbe es kein Signal.
Home Assistant allein ist nie „Kein Netz“, dann gilt nur die Alters-Regel. Die Route sagt nichts
über eine Störung hinter dem Router; dann steht kein „Kein Netz“, und die Alters-Regel greift.

Prüfen: Im Strom von `/ereignisse` (`curl` wie oben) steht nach dem Verbinden ein Ereignis `netz`
nur dann, wenn es sich geändert hat.

## Einrichten

Der Dienst braucht ein eigenes Token für Home Assistant. Ohne `HA_TOKEN` läuft er weiter und
zeigt „Keine Wetterdaten“. Die Geheimnisse kommen aus dem 1Password-Environment
`kuechen-display`, wie bei den anderen Repos (heim-agent#87).

| Name | Wofür |
|---|---|
| `HA_TOKEN` | langlebiges Token für Home Assistant, nur dieses Gerät |
| `RUNDFUNK_GERAETE_TOKEN` | Token der rundfunk-Bridge, derselbe Wert wie in `rundfunk/.env` |
| `OPENAI_API_KEY` | Diktat ins Suchfeld (#70, `docs/stimme-und-geste.md`): Transkription und Suchbegriff (`MODELLE.md`); ohne Schlüssel meldet der Knopf „Kein OpenAI-Schlüssel auf dem Display“ |

**1. Token anlegen.** In Home Assistant: Profil (unten links) → Sicherheit →
„Langlebige Zugangstoken“ → Token erstellen, Name `kuechen-display`. Kopieren.

**2. In 1Password eintragen.** In der App unter Developer → View Environments das Environment
`kuechen-display` anlegen oder öffnen und beide Namen mit Wert eintragen. Dann als
`~/Development/kuechen-display/.env` einhängen.

**3. Auf den Pi bringen.** Erst ohne `--ja` laufen lassen und die Namen lesen:

```bash
~/Development/heim-agent/deploy/pi-env-push.sh kuechen-display
```

Das Skript schreibt `~/kuechen-display/.env` auf dem Pi (Rechte 600) und zeigt nur Namen, nie
Werte. Die Unit `kuechen-dienst` lädt die Datei per `EnvironmentFile`.

**4. Ausrollen.** Startet den Dienst neu, damit er die neuen Werte sieht:

```bash
pi/push.sh
```

Die früheren Token-Dateien unter `~/.config/kuechen-display/` (`geraete-token`, `ha-token`)
gelten weiter als Rückfall: Steht ein Name nicht in der `.env`, nimmt der Dienst die Datei.
Läuft alles über die `.env`, kann `geraete-token` auf dem Pi gelöscht werden.

## Prüfen

```bash
ssh kuechen-display.local 'journalctl -u kuechen-dienst -n 30 --no-pager | grep Wetter'
```

Dort steht nach dem Start eine Zeile wie `Wetter: 11°, Bedeckt, Bild gedaempft`, danach nur
noch, wenn sich etwas ändert. Was die Seite bekommt:

```bash
ssh kuechen-display.local 'curl -sN --max-time 3 http://127.0.0.1:8080/ereignisse'
```

## Andere Quelle oder anderer Ort

Die Werte stehen als Umgebungsvariablen im Dienst (`pi/dienst/dienst.py`): `HA_URL`,
`WETTER_ENTITAET`, `TEMPERATUR_SENSOR`, `WARNUNG_SENSOR`, `ORT`, für die Termine `KALENDER` und `SPERRE_ENTITAET`. Sie sind keine
Geheimnisse und gehören nicht in 1Password: ändern über einen Drop-in der Unit `kuechen-dienst`.

## Termine

Die Termine kommen aus dem Familienkalender bei Apple über die CalDAV-Integration von Home
Assistant (Festlegung 15.11.2026 in #15). Der Küchen-Dienst fragt sie mit demselben Token ab
wie das Wetter, alle zwei Minuten (das Wetter alle zehn).

```
iCloud ──CalDAV──▶ Home Assistant  calendar.family, calendar.abfall
                      │  Dienst calendar.get_events, heute 0 Uhr bis in sieben Tagen
                      ▼
Küchen-Dienst  pi/dienst/hass.py   termine_karte: Namen der Kalender, ein Abruf für alle
               pi/dienst/daten.py  termine_aufbereiten: heute, morgen, Woche (reine Funktion)
                      │  Ereignis „termine“ über /ereignisse
                      ▼
Kiosk-Seite    „Noch heute“, „Morgen … ›“, Seite Morgen/Woche
```

Regeln:

- Am Display stehen nur die Kalender Family und Abfall. Die Reihenfolge in `KALENDER` gibt die
  Farbe des Punkts: der erste gelb (Family), der zweite rot (Abfall), weitere grau. Neben dem
  Punkt steht der Name des Kalenders aus Home Assistant.
- Ganztägige Termine stehen oben, statt der Uhrzeit steht „ganztägig“. Sie bleiben bis
  Mitternacht stehen, mehrtägige an jedem ihrer Tage.
- „Noch heute“ zeigt, was noch nicht vorbei ist. Ein laufender Termin bleibt bis zu seinem
  Ende. Die Seite blendet vorbei gegangene Termine jede Minute selbst aus.
  Passen nicht alle Termine auf die Karte, rollt die Liste per Wischen nach oben und unten,
  ein weicher unterer Rand zeigt, dass noch etwas kommt. Morgen und Woche rollen ebenso.
- Morgen zeigt die Uhrzeit von–bis, die Woche nur den Beginn. Die Woche beginnt heute und hat
  sieben Tage, Überschrift Wochentag, Datum und Kalenderwoche.
- Ein Termin über Mitternacht steht am Folgetag mit „bis 02:00“.
- Kennt Home Assistant einen eingestellten Kalender nicht, steht eine Warnung im Journal und
  die übrigen Kalender erscheinen trotzdem. Antwortet Home Assistant nicht, behält die Seite
  den letzten Stand. Ist er älter als eine Stunde, werden die Termine blass, wie das Wetter
  (siehe „Wenn etwas fehlt“).

Die iCloud-Integration in Home Assistant ist ebenfalls eingerichtet, sie ist für die
Anwesenheit da. Ihre Kalender (`calendar.florianhuber_icloud_com_…`) liest das Display nicht.

Prüfen:

```bash
ssh kuechen-display.local 'journalctl -u kuechen-dienst -n 30 --no-pager | grep Termine'
```

Dort steht eine Zeile wie `Termine: heute 2, morgen 1, Woche 6`.

Einstellungen (kein Geheimnis, Drop-in der Unit wie oben): `KALENDER` (Entitäten, durch Komma
getrennt), `ZEITZONE` (Vorgabe `Europe/Berlin`), `SPERRE_ENTITAET` (siehe unten).

## Termine sperren

Festlegung 17. und 18.11.2026 in #82. Kommt Besuch, sollen die Termine nicht auf dem Display stehen.

**Sperren** geht nur am Display: etwa 0,8 Sekunden auf eine Terminkarte drücken (Heute, Morgen oder
Woche), mit ruhigem Finger. Wischen, Rollen und das Antippen von „Morgen ›“ lösen nichts aus. Die
Karte dunkelt kurz nach, dann steht dort ein Schloss mit „Termine ausgeblendet“, auf allen Seiten
mit Terminen, ohne Zahl (auch „Morgen ›“ trägt keine mehr). Per Stimme und über Elektra geht es nicht.

**Entsperren** geht nur am Handy. In der Home-Assistant-App den Schalter
„Termine privat“ (`input_boolean.termine_privat`, Symbol Kalender mit Schloss) ausschalten, zu finden unter Einstellungen → Geräte & Dienste →
Helfer oder auf dem Dashboard, wenn er dort liegt. Spätestens zwei Minuten später (so oft fragt der
Dienst die Termine ab) stehen sie wieder da. Am Display gibt es keinen Weg zurück, auch keinen Code.
Jeden Morgen um 6 Uhr schaltet die Automation „Termine privat morgens aus“ in Home Assistant den Helfer aus (nicht Teil dieses
Repos).

```
langes Drücken ─▶ Seite: POST /sperren ─▶ Dienst: input_boolean/turn_on in HA
                                              │ klappt: Schloss sofort (Ereignis „termine“)
                                              │ klappt nicht: Hinweis „Sperren hat nicht geklappt“,
                                              ▼            das Display bleibt entsperrt
Handy: Helfer aus ─▶ HA ─▶ Dienst liest den Helfer bei jedem Terminabruf (alle 2 Minuten)
```

Der Helfer in Home Assistant ist die einzige Wahrheit (`pi/dienst/sperre.py`, getestet):

- „on“ heißt gesperrt, nur ein ausdrückliches „off“ hebt die Sperre auf. „unknown“, „unavailable“
  und ein Helfer, den Home Assistant nicht kennt, lassen den Stand, wie er ist: Ein gesperrtes
  Display bleibt gesperrt (nach einem Neustart von Home Assistant fehlt der Helfer kurz, und der
  Besuch soll dann keine Termine sehen). Ist das Display nicht gesperrt, zählt das als frei, ohne
  Fehler auf der Seite. Ein Neustart des Küchen-Dienstes beginnt frei und übernimmt den ersten
  lesbaren Stand.
- Gesperrt schickt der Dienst gar keine Termine an die Seite, weder Titel noch Zeiten noch eine
  Anzahl, und ruft sie auch nicht ab. Das Ereignis „termine“ lautet dann nur
  `{"gesperrt": true, "sperrbar": true}`. Die Seite wirft ihren Stand weg und zeigt das Schloss,
  auch eine neu geöffnete Seite bekommt nichts anderes. Ein Abruf, der beim Sperren gerade läuft,
  wird verworfen.
- Nach dem langen Drücken gilt die Sperre erst, wenn Home Assistant den Helfer eingeschaltet hat; dann
  zeigt die Seite das Schloss sofort, ohne den nächsten Abruf abzuwarten. Scheitert das (Home Assistant
  nicht erreichbar, kein `HA_TOKEN`), bleibt das Display entsperrt und zeigt vier Sekunden lang
  „Sperren hat nicht geklappt“ in der Zeile für Hinweise.
- Antwortet Home Assistant nicht, bleibt der letzte Stand: Ein gesperrtes Display bleibt gesperrt.
  Beim Entsperren vom Handy bleibt das Schloss stehen, bis der Abruf der Termine klappt.
- `SPERRE_ENTITAET` (Vorgabe `input_boolean.termine_privat`): leer schaltet die Funktion ab, das
  lange Drücken tut dann nichts.

Prüfen: Im Strom von `/ereignisse` (`curl` wie oben) steht beim Ereignis „termine“ `"gesperrt": false`
oder `{"gesperrt": true, "sperrbar": true}`. Im Journal steht „Sperre: Termine gesperrt (am Display)“
bzw. „… wieder frei (vom Handy)“.
