# Datenweg: Wetter und Termine auf dem Ruhebildschirm

Stand 15.11.2026, zu #15. Das Wetter kommt aus Home Assistant. Die Termine sind noch
Platzhalter, ihr Weg ist nicht entschieden (siehe unten).

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
- Zweite Zeile: tagsüber „Nacht 5°“ (Tiefstwert heute), nachts „Morgen 12°“ (Höchstwert
  morgen). Ohne Vorhersage bleibt sie leer.
- Eine Lage, die die Tabelle nicht kennt, steht im Klartext auf der Karte, bekommt das Bild
  „gedämpft“ und eine Warnung im Journal.
- Antwortet Home Assistant nicht, behält die Seite den letzten Stand. Ist er älter als eine
  Stunde, wird die Wetterkarte blass. Ohne jeden Stand steht dort „Keine Wetterdaten“.

Die zweite Zeile bei Nacht und das Verblassen nach einer Stunde sind Annahmen aus dem Bau,
keine Festlegungen (#15, #50).

## Einrichten

Der Dienst braucht ein eigenes Token für Home Assistant. Ohne die Token-Datei läuft er weiter
und zeigt „Keine Wetterdaten“.

**1. Token anlegen.** In Home Assistant: Profil (unten links) → Sicherheit →
„Langlebige Zugangstoken“ → Token erstellen, Name `kuechen-display`. Das Token in die
Zwischenablage kopieren.

**2. Token auf den Pi legen.** Der Befehl schreibt die Zwischenablage in die Datei und zeigt
das Token nicht an:

```bash
pbpaste | ssh kuechen-display.local 'install -d -m 700 ~/.config/kuechen-display && umask 077 && cat > ~/.config/kuechen-display/ha-token'
```

Später soll das Token aus 1Password kommen wie die anderen Gerätewerte.

**3. Ausrollen.**

```bash
pi/push.sh
```

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
`HA_TOKEN_DATEI`, `WETTER_ENTITAET`, `TEMPERATUR_SENSOR`, `ORT`. Ändern über einen Drop-in
der Unit `kuechen-dienst`.

## Offen: Termine

Festgelegt ist die Quelle: der Familienkalender bei Apple (#15, 18.10.2026). In Home Assistant
gibt es bisher keinen Kalender (geprüft am 15.11.2026: keine `calendar.*`-Entität, keine
CalDAV-Integration). Zwei Wege:

- **Über Home Assistant.** Die CalDAV-Integration mit einem app-spezifischen Passwort von
  Apple einrichten. Der Küchen-Dienst fragt dann `calendar.get_events` über dasselbe Token ab
  wie das Wetter. Elektra könnte dieselben Termine ansagen.
- **Direkt vom Pi.** Der Küchen-Dienst spricht selbst CalDAV mit iCloud. Das Passwort läge
  dann auf dem Küchen-Pi, und Elektra hätte nichts davon.

Danach offen: ob der Punkt mit dem Namen neben einem Termin (Entwurf C) aus getrennten
Kalendern je Person kommt, und wie ganztägige Termine aussehen.
