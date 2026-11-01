# Modelle

Welche KI-Modelle dieses Repo nutzt, wofür, und was auf dem Gerät wirklich läuft.
Die monatliche Routine „Monatscheck KI-Modelle“ liest diese Datei zuerst und gleicht sie
gegen den Code ab. Wer ein Modell wechselt, ändert diese Datei im selben PR; wer einen
Gerätewert in 1Password ändert, trägt ihn hier mit Datum nach.

Spalten: **Code** = Wert oder Default im Code, **Gerät** = was tatsächlich läuft
(1Password/Unit, mit Prüfdatum), **Denken** = thinking bzw. reasoning.effort.

kuechen-display ruft im Betrieb kein KI-Modell auf. Die Bild-Skripte unter `werkzeuge/`
startet Florian von Hand, wenn neue Bilder gebraucht werden; den Schlüssel liefert
`../rundfunk/.env`.

| Stelle | Zweck | Anbieter | Code | Gerät | Denken |
|---|---|---|---|---|---|
| `werkzeuge/wetter_bilder.py` `MODELL` | Hintergrundbilder des Ruhebildschirms für sechs Wetterlagen (kein Laufzeitcode) | OpenAI Bild-API | `gpt-image-2.5-sunburst` | – | – |
| `werkzeuge/figur_bilder.py` `MODELL` | Elektras Figur in vier Zuständen für den Ruhebildschirm (kein Laufzeitcode) | OpenAI Bild-API | `gpt-image-2.5-sunburst` | – | – |

Die Preise in `werkzeuge/bildkosten.py` gelten für gpt-image-2.5; bei einem Modellwechsel mit anpassen.
