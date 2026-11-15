# Modelle

Welche KI-Modelle dieses Repo nutzt, wofür, und was auf dem Gerät wirklich läuft.
Die monatliche Routine „Monatscheck KI-Modelle“ liest diese Datei zuerst und gleicht sie
gegen den Code ab. Wer ein Modell wechselt, ändert diese Datei im selben PR; wer einen
Gerätewert in 1Password ändert, trägt ihn hier mit Datum nach.

Spalten: **Code** = Wert oder Default im Code, **Gerät** = was tatsächlich läuft
(1Password/Unit, mit Prüfdatum), **Denken** = thinking bzw. reasoning.effort.

Im Betrieb ruft kuechen-display seit 15.11.2026 zwei Modelle auf, beide nur für das Diktat ins
Suchfeld (#70, `docs/stimme-und-geste.md`). Den Schlüssel liefert `OPENAI_API_KEY` aus dem
1Password-Environment `kuechen-display`. Elektras Gespräch läuft über die rundfunk-Bridge und steht
in deren `MODELLE.md`. Die Bild- und Ton-Skripte unter `werkzeuge/` startet Florian von Hand, wenn
neue Bilder gebraucht werden; den Schlüssel dafür liefert `../rundfunk/.env`.

| Stelle | Zweck | Anbieter | Code | Gerät | Denken |
|---|---|---|---|---|---|
| `pi/dienst/diktat.py` `MODELL` | Diktat ins Suchfeld: Ton zu Text, Sprachen Deutsch und Englisch | OpenAI Transkription (`/v1/audio/transcriptions`) | `gpt-transcribe` (Unit-Variable `DIKTAT_MODELL`) | Default, nicht gesetzt (15.11.2026) | – |
| `pi/dienst/diktat.py` `TEXT_MODELL` | Suchbegriff aus einem gesprochenen Satz („spiel mir was von Queen“ → „Queen“); nur ab vier Wörtern, der Code prüft das Ergebnis | OpenAI Responses (`/v1/responses`) | `gpt-6-luna` (Unit-Variable `DIKTAT_TEXT_MODELL`) | Default, nicht gesetzt (15.11.2026) | `none` (`TEXT_DENKEN`) |
| `werkzeuge/wetter_bilder.py` `MODELL` | Hintergrundbilder des Ruhebildschirms für sechs Wetterlagen (kein Laufzeitcode) | OpenAI Bild-API | `gpt-image-2.6-sunburst` | – | – |
| `werkzeuge/figur_bilder.py` `MODELL` | Elektras Figur in vier Zuständen für den Ruhebildschirm (kein Laufzeitcode) | OpenAI Bild-API | `gpt-image-2.6-sunburst` | – | – |
| `werkzeuge/stimme_proben.py` `MODELL` | Sprachproben mit Elektras Stimme für die Projektseite `docs/projekt/` (kein Laufzeitcode) | OpenAI Sprachausgabe (`/v1/audio/speech`) | `gpt-4o-mini-tts`, Stimme `marin` | – | – |

Die Preise in `werkzeuge/bildkosten.py` gelten für gpt-image-2.6 (gleich wie 2.5); bei einem Modellwechsel mit anpassen.

Seit 15.11.2026 erzeugen die Skripte mit gpt-image-2.6. Die vorhandenen Bilder stammen noch von 2.5. Wer neu erzeugt, sollte einen ganzen Satz (alle Wetterlagen bzw. alle Figurzustände) auf einmal machen, damit der Stil zusammenpasst.

`gpt-4o-mini-tts` schaltet OpenAI am 06.01.2027 ab (Ersatz `gpt-realtime-2.1-mini`, andere API). `stimme_proben.py` wird erst beim nächsten Lauf umgebaut. Die erzeugten MP3-Dateien bleiben.
