# kuechen-display

Das Küchen-Display: ein 8-Zoll-Touch (Waveshare 8inch DSI LCD (C)) mit Raspberry Pi 5,
reSpeaker XVF3800 Flex und Kamera in einem Gehäuse im Braun-Stil (nach dem RT 20).
Es steht auf der Halbinsel in der offenen Küche, zeigt im Ruhebildschirm Termine und
Wetter, startet Apps und ist Sprachgerät wie Elektra.

Übersicht und alle Festlegungen: [#1](https://github.com/dragondiver/kuechen-display/issues/1)
und seine Unterkarten. Die Issues lagen bis zum 19.10.2026 in `rundfunk`.

Wie es dazu kam: [Entwicklungsgeschichte](docs/geschichte.md).

Die Entwürfe als Website (GitHub Pages, Ordner `docs/`): <https://dragondiver.github.io/kuechen-display/>. Im Repo zeigt GitHub HTML-Dateien nur als Quelltext.

## Was wo liegt

| Ordner | Inhalt |
|---|---|
| `gehaeuse/blender/` | Gehäuse als Blender-Skripte, `entwurf_o.py` ist der aktuelle Stand; ältere Buchstaben sind die Entwurfsgeschichte |
| `gehaeuse/referenz/` | nur lokal, nicht im Git: Maßzeichnung des Displays ([Waveshare 8inch DSI LCD (C)](https://www.waveshare.com/wiki/8inch_DSI_LCD_(C))) und Fotos des Braun RT 20 als Vorbild |
| `docs/entwuerfe/` | Entwurfsseiten: Galerie, Entwurfsgeschichte, Hardware-Auswahl, Ruhebildschirm |
| `oberflaeche/` | *kommt:* Browser-App für den Chromium-Kiosk (1280 × 800), #10, #15 |
| `geraet/` | *kommt:* Einrichtung des Pi 5 (Kiosk, Dienste, Deploy) |
| `werkzeuge/` | Hilfsskripte, z. B. `figur_bilder.py`: Elektras Figur in vier Zuständen per OpenAI-Bild-API aus einer Vorlage erzeugen (#15); `wetter_bilder.py`: Hintergrundbilder für sechs Wetterlagen mit dem Fernsehturm in der Kartenlücke (#15). Anleitung: [docs/bilder-erzeugen.md](docs/bilder-erzeugen.md) |

Gehäuse rendern (Blender im Hintergrund, Bilder landen in `gehaeuse/renders/`, nicht im Git):

```bash
blender -b -P gehaeuse/blender/entwurf_o.py -- w75 acht mantel skala
```

## Abgrenzung zu rundfunk

Das Sprach-Gehirn (GPT-Live, Werkzeuge, Home Assistant, Nachrichten) lebt in
[rundfunk](https://github.com/dragondiver/rundfunk). Wie das Display daran spricht,
entscheidet [rundfunk#128](https://github.com/dragondiver/rundfunk/issues/128); dort
bleiben auch rundfunk#134 (Stimmung) und rundfunk#135 (Gespräch wandert zwischen den Geräten).

## Alte Nummern

Beim Umzug aus rundfunk haben die Issues neue Nummern bekommen; alte Links leiten weiter.

| rundfunk | hier | | rundfunk | hier |
|---|---|---|---|---|
| #108 | #1 Übersicht | | #129 | #11 |
| #109 | #2 | | #130 | #12 |
| #120 | #3 | | #131 | #13 |
| #121 | #4 | | #132 | #14 |
| #122 | #5 | | #133 | #15 Ruhebildschirm |
| #123 | #6 | | #144 | #16 |
| #124 | #7 | | #174 | #17 |
| #125 | #8 | | #175 | #18 Tischtest |
| #126 | #9 | | #182 | #19 |
| #127 | #10 Apps-Seiten | | | |
