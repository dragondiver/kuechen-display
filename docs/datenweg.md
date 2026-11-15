# Datenweg: Wetter und Termine auf dem Ruhebildschirm

Stand 15.11.2026, zu #15. Wetter und Termine kommen aus Home Assistant.

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

## Einrichten

Der Dienst braucht ein eigenes Token für Home Assistant. Ohne `HA_TOKEN` läuft er weiter und
zeigt „Keine Wetterdaten“. Die Geheimnisse kommen aus dem 1Password-Environment
`kuechen-display`, wie bei den anderen Repos (heim-agent#87).

| Name | Wofür |
|---|---|
| `HA_TOKEN` | langlebiges Token für Home Assistant, nur dieses Gerät |
| `RUNDFUNK_GERAETE_TOKEN` | Token der rundfunk-Bridge, derselbe Wert wie in `rundfunk/.env` |

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
`WETTER_ENTITAET`, `TEMPERATUR_SENSOR`, `ORT`, für die Termine `KALENDER`. Sie sind keine
Geheimnisse und gehören nicht in 1Password: ändern über einen Drop-in der Unit `kuechen-dienst`.

## Termine

Die Termine kommen aus dem Familienkalender bei Apple über die CalDAV-Integration von Home
Assistant (Festlegung 15.11.2026 in #15). Der Küchen-Dienst fragt sie mit demselben Token ab
wie das Wetter, im selben Takt von zehn Minuten.

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
- Morgen zeigt die Uhrzeit von–bis, die Woche nur den Beginn. Die Woche beginnt heute und hat
  sieben Tage, Überschrift Wochentag, Datum und Kalenderwoche.
- Ein Termin über Mitternacht steht am Folgetag mit „bis 02:00“.
- Kennt Home Assistant einen eingestellten Kalender nicht, steht eine Warnung im Journal und
  die übrigen Kalender erscheinen trotzdem. Antwortet Home Assistant nicht, behält die Seite
  den letzten Stand.

Die iCloud-Integration in Home Assistant ist ebenfalls eingerichtet, sie ist für die
Anwesenheit da. Ihre Kalender (`calendar.florianhuber_icloud_com_…`) liest das Display nicht.

Prüfen:

```bash
ssh kuechen-display.local 'journalctl -u kuechen-dienst -n 30 --no-pager | grep Termine'
```

Dort steht eine Zeile wie `Termine: heute 2, morgen 1, Woche 6`.

Einstellungen (kein Geheimnis, Drop-in der Unit wie oben): `KALENDER` (Entitäten, durch Komma
getrennt), `ZEITZONE` (Vorgabe `Europe/Berlin`).
