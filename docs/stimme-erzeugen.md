# Sprachproben mit Elektras Stimme erzeugen

Stand 8.11.2026. Die Projektseite (`docs/projekt/`) spielt kurze Sprachproben ab, wenn
jemand dort eine Erinnerung auslöst oder Elektra fragt. Gesprochen werden sie mit
**Marin**, der Stimme, mit der Elektra auch auf dem Gerät spricht. Fehlt eine Datei,
nimmt die Seite die Sprachausgabe des Browsers.

| Skript | erzeugt | Ziel |
|---|---|---|
| `werkzeuge/stimme_proben.py` | vier Sätze, je Deutsch und Englisch | `docs/projekt/ton/*.mp3` |

## Voraussetzungen

- `uv` ist installiert. Das Skript bringt seine Abhängigkeit (`openai`) selbst mit.
- Für einen echten Lauf: der OpenAI-Schlüssel als `OPENAI_API_KEY` aus der von
  1Password eingebundenen `.env` von rundfunk (1Password-App entsperrt).
- Alle Befehle im Repo-Wurzelverzeichnis: `cd ~/Development/kuechen-display`.
- Ein echter Lauf kostet Geld, bei vier kurzen Sätzen wenige Cent.

## Schritte

1. Probelauf, kostet nichts und zeigt die Sätze:
   ```bash
   uv run werkzeuge/stimme_proben.py --probe
   ```
2. Echter Lauf, dauert einige Sekunden:
   ```bash
   uv run --env-file ../rundfunk/.env werkzeuge/stimme_proben.py
   ```
3. Anhören: die vier Dateien unter `docs/projekt/ton/` öffnen, zum Beispiel
   ```bash
   afplay docs/projekt/ton/antwort-de.mp3
   ```
4. Einen einzelnen Satz neu erzeugen, wenn er nicht gefällt:
   ```bash
   uv run --env-file ../rundfunk/.env werkzeuge/stimme_proben.py --nur antwort-de
   ```
5. Claude Bescheid geben: Die Dateien kommen mit der Projektseite ins Repo und ins Artefakt.

**Optionen:** `--nur <name>` (mehrfach möglich), `--modell <name>` (Standard
`gpt-4o-mini-tts`), `--stimme <name>` (Standard `marin`).

## Wenn etwas nicht klappt

| Meldung | Ursache |
|---|---|
| `OPENAI_API_KEY fehlt …` | `--env-file ../rundfunk/.env` vergessen oder 1Password gesperrt |
| `FEHLER …: … voice …` | Stimme an diesem Modell nicht verfügbar; mit `--stimme cedar` gegenhören oder Claude fragen |

## Hinweise

- Die Sätze im Skript (`SAETZE`) müssen zu `SAETZE` in `docs/projekt/index.html` passen.
  Wer einen Satz ändert, ändert beide Stellen und erzeugt die Probe neu.
- OpenAI verlangt, dass Hörer erfahren, dass die Stimme KI-generiert ist. Die Seite sagt es
  unter dem Knopf „Elektra fragen“.
- Das Modell `gpt-4o-mini-tts` ist laut OpenAI abgekündigt (Abschaltung 6.1.2027). Die
  erzeugten Dateien bleiben gültig; nur ein Neuerzeugen braucht danach einen anderen Weg.
