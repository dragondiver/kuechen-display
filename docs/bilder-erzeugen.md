# Bilder erzeugen: Elektras Figur und die Wetterbilder

Stand 19.10.2026. Festlegungen dazu stehen in [#15](https://github.com/dragondiver/kuechen-display/issues/15).

Zwei Skripte erzeugen die Bilder des Ruhebildschirms über die OpenAI-Bild-API:

| Skript | erzeugt | Ziel |
|---|---|---|
| `werkzeuge/figur_bilder.py` | Elektras Figur in vier Zuständen | `docs/entwuerfe/figur/` |
| `werkzeuge/wetter_bilder.py` | Hintergrund für sechs Wetterlagen | `docs/entwuerfe/wetter/` |

Beide arbeiten gleich: Erst entsteht ein **Grundbild**, die übrigen Bilder werden
aus diesem Grundbild abgeleitet. So sieht die Figur in allen Zuständen gleich aus,
und Landschaft und Fernsehturm bleiben in allen Wetterlagen an derselben Stelle.

## Voraussetzungen

- `uv` ist installiert. Die Skripte bringen ihre Abhängigkeiten (`openai`, `pillow`) selbst mit.
- Für einen echten Lauf: der OpenAI-Schlüssel als `OPENAI_API_KEY`. Er steht in der
  von 1Password eingebundenen `.env` von rundfunk und wird mit `--env-file` übergeben.
  Er wird nie ins Repo geschrieben.
- Alle Befehle im Repo-Wurzelverzeichnis: `cd ~/Development/kuechen-display`.
- Ein echter Lauf **kostet Geld** (Bild-API, Qualität `medium` als Standard).

## Figur (`figur_bilder.py`)

**Vorlage:** `docs/entwuerfe/figur/vorlage-pferdeschwanz.png`, Florians ChatGPT-Bild
mit zwei Figuren. Das Skript schneidet die linke Figur („Agent hört zu“) aus
(Ausschnitt `30, 250, 610, 830`).

**Zustände:** `zuhoeren` (Grundbild, aus der Vorlage), `sprechen-halb`, `sprechen-offen`,
`nachdenken` (aus dem Grundbild). Jedes Bild transparent, ohne Kreis, Schallbögen,
Mikrofon und Text: Diese Teile zeichnet die Oberfläche selbst.

**Schritte:**

1. Probelauf, kostet nichts und zeigt Ablauf und Prompts:
   ```bash
   uv run werkzeuge/figur_bilder.py --probe
   ```
2. Echter Lauf, dauert gut eine Minute:
   ```bash
   uv run --env-file ../rundfunk/.env werkzeuge/figur_bilder.py
   ```
3. Ergebnis ansehen: `docs/entwuerfe/figur/<zustand>.png` (1024 px) und
   `<zustand>-klein.png` (256 px, so groß kommt die Figur aufs Display).
4. Ein einzelnes Bild neu erzeugen, z. B. weil der Blick beim Nachdenken nicht passt
   (braucht ein vorhandenes `zuhoeren.png`):
   ```bash
   uv run --env-file ../rundfunk/.env werkzeuge/figur_bilder.py --nur nachdenken
   ```
5. Bilder per PR ins Repo bringen (main ist geschützt).

**Optionen:** `--qualitaet low|medium|high`, `--modell <name>` (Standard
`gpt-image-2.5-sunburst`), `--vorlage <datei>`, `--ohne-ausschnitt`.

**Erster Lauf:** 19.10.2026, Ergebnis ist Entwurf F2, von Florian als Elektras Figur gewählt.

## Wetterbilder (`wetter_bilder.py`)

**Lagen:** `gedaempft` (Grundbild, nur aus Text), `sonnig`, `wolkig`, `nacht`,
`schnee`, `regen` (aus dem Grundbild).

**Stil:** W3, eine illustrierte Landschaft mit dem Stuttgarter Fernsehturm. Der
Turm muss im Startbild (Heute) in der **Lücke zwischen linker und rechter Glaskarte**
stehen, bei **x = 730 von 1280 px** (57 %). Auf den Seiten Apps und Morgen/Woche
darf er verdeckt sein.

**Format:** Die API liefert 1536 × 1024. Das Modell hält die Turmposition aus dem
Prompt nicht zuverlässig ein. Deshalb misst das Skript im Grundbild, wo der Turm
steht, und schneidet aus jedem Rohbild einen 16:10-Ausschnitt so aus, dass der Turm
bei x = 730 landet. Danach wird auf 1280 × 800 skaliert, meist leicht vergrößert.
Steht der Turm zu nah am Rand, bricht das Skript mit einer Meldung ab. Die unbeschnittenen Originale liegen in
`docs/entwuerfe/wetter/roh/` und werden für die Ableitungen gebraucht. Sie bleiben
lokal und sind nicht im Git.

**Schritte:**

1. Probelauf:
   ```bash
   uv run werkzeuge/wetter_bilder.py --probe
   ```
2. Echter Lauf (sechs Bilder):
   ```bash
   uv run --env-file ../rundfunk/.env werkzeuge/wetter_bilder.py
   ```
3. **Prüfen, ob der Turm in der Lücke steht.** Der Lauf legt Prüfbilder in
   `docs/entwuerfe/wetter/pruefung/` an: die Glaskarten als dunkle Flächen, die
   Sollposition des Turms als rote Linie.
   Steht der Turm daneben, weil die Messung einen falschen Strich erwischt hat,
   kostenlos neu zuschneiden, bei Bedarf mit der Turmposition im Rohbild von Hand.
   Die Rohbilder liegen in `wetter/roh/`.
   ```bash
   uv run werkzeuge/wetter_bilder.py --neu-zuschneiden
   uv run werkzeuge/wetter_bilder.py --neu-zuschneiden --turm-x 1078
   ```
   Passt das Grundbild selbst nicht, etwa weil der Turm am Rand steht oder fehlt,
   zuerst das Grundbild neu erzeugen, danach die anderen Lagen:
   ```bash
   uv run --env-file ../rundfunk/.env werkzeuge/wetter_bilder.py --nur gedaempft
   uv run --env-file ../rundfunk/.env werkzeuge/wetter_bilder.py --nur sonnig wolkig nacht schnee regen
   ```
   Nur die Prüfbilder neu zeichnen, ohne API: `uv run werkzeuge/wetter_bilder.py --pruefen`
4. Einzelne Lage nachbessern, z. B. `--nur nacht`.

**Erster Lauf:** 19.10.2026. Der Turm stand im Rohbild bei 70 % statt 57 % und wurde
per Zuschnitt in die Lücke gesetzt (Turm im Rohbild bei x = 1078). Der Stil ist eher
gemalt als flach illustriert. Im Ruhebildschirm-Entwurf als W4 zu sehen.
5. Die sechs Bilder in `docs/entwuerfe/wetter/` per PR ins Repo bringen.

## Stilideen für die Wetterbilder

Damit die Landschaft zur Figur F2 passt, gibt es einen Ideen-Lauf: Für **eine** Lage,
standardmäßig Regen, entstehen drei Bilder in drei Stilrichtungen: `ton` (weiche
Ton-Welt), `flach` (flache Illustration) und `bilderbuch`. Das Bild der Frau
(`docs/entwuerfe/figur/zuhoeren.png`) geht als **Stilhinweis** mit. Übernommen werden
nur Machart und Licht, **nicht ihre Farben**. Die Landschaft bleibt natürlich (grüne
Hügel, grauer Regenhimmel), die Frau wird nicht ins Bild gesetzt.

1. Probelauf: `uv run werkzeuge/wetter_bilder.py --ideen --probe`
2. Ideen erzeugen (drei Bilder):
   ```bash
   uv run --env-file ../rundfunk/.env werkzeuge/wetter_bilder.py --ideen
   ```
   Andere Lage: `--lage nacht`. Andere Stilvorlage: `--stil-vorlage <datei>`.
3. Ergebnis in `docs/entwuerfe/wetter/ideen/<lage>-<stil>.png`, Prüfbilder daneben in
   `ideen/pruefung/`. Die bisherigen sechs Wetterbilder bleiben unverändert.
4. Ist ein Stil gewählt, entsteht daraus die ganze Serie (nächster Abschnitt).

**Erster Ideen-Lauf:** 19.10.2026, Regen in allen drei Stilen, je 2 Cent. Florian
wählte `flach`.

## Serie in einem gewählten Stil

Die Serie nimmt das Rohbild der gewählten Idee als Grundbild, z. B.
`ideen/roh/regen-flach.png`, und leitet jede andere Lage daraus ab. Landschaft,
Turm und Stil bleiben damit genau wie in der Idee. Die Lage der Idee selbst wird
nur zugeschnitten und kostet nichts. Ziel ist ein eigener Ordner
`docs/entwuerfe/wetter/<stil>/`, die älteren Bilder bleiben unberührt.

1. Probelauf: `uv run werkzeuge/wetter_bilder.py --serie flach --probe`
2. Serie erzeugen (fünf Bilder, Regen ist schon da):
   ```bash
   uv run --env-file ../rundfunk/.env werkzeuge/wetter_bilder.py --serie flach
   ```
3. Prüfbilder in `docs/entwuerfe/wetter/flach/pruefung/` ansehen; einzelne Lage
   nachbessern mit `--nur nacht`.
4. Wurde die Idee für eine andere Lage erzeugt, z. B. `--ideen --lage nacht`, dann
   `--serie <stil> --lage nacht`.

**Erster Serien-Lauf:** 19.10.2026, `--serie flach`. Fünf Bilder je etwa 3 Cent (zwei
Bilder als Eingabe: Grundbild und Stilvorlage). Der Turm steht in allen sechs in der
Lücke. „Gedämpft“ zeigt noch feine Regenstriche aus dem Grundbild. Im Entwurf als W5.

## Kosten

Beide Skripte schreiben nach jedem Bild die verbrauchten Tokens und die Kosten in
[`docs/bild-laeufe.md`](bild-laeufe.md) und geben sie aus. Grundlage sind die Tokens aus
der API-Antwort und die Preise in `werkzeuge/bildkosten.py` (gpt-image-2.5, Stand
Oktober 2026: Bild ein 8 $, Text ein 5 $, Bild aus 30 $ je Million Tokens). Die
ersten beiden Läufe am 19.10.2026 sind dort nicht drin, weil das Protokoll erst danach
kam. Geschätzt kosteten sie zusammen unter einen Euro.

## Wenn etwas schiefgeht

| Meldung | Ursache, Abhilfe |
|---|---|
| `OPENAI_API_KEY fehlt …` | `--env-file ../rundfunk/.env` vergessen, oder die `.env` ist nicht eingebunden (1Password-App entsperren) |
| `Turm bei x = … steht zu nah am Rand` | Grundbild mit `--nur gedaempft` neu erzeugen, danach die anderen Lagen |
| `Grundbild … fehlt` | `--nur` ohne vorhandenes Grundbild: erst einmal ohne `--nur` laufen lassen |
| `Unbekannte Zustände/Lagen` | Tippfehler bei `--nur`; gültige Namen siehe oben |
| Figur sieht in einem Zustand anders aus | nur diesen Zustand mit `--nur` neu erzeugen; hilft das nicht, `--qualitaet high` |
| `git pull` scheitert mit `Permission denied (publickey)` | 1Password ist gesperrt, der SSH-Agent antwortet nicht: entsperren, dann erneut |
