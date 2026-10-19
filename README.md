# kuechen-display

Das Küchen-Display: ein 8-Zoll-Touch (Waveshare 8inch DSI LCD (C)) mit Raspberry Pi 5,
reSpeaker XVF3800 Flex und Kamera in einem Gehäuse im Braun-Stil (nach dem RT 20).
Es steht auf der Halbinsel in der offenen Küche, zeigt im Ruhebildschirm Termine und
Wetter, startet Apps und ist Sprachgerät wie Elektra.

Übersicht und alle Festlegungen: [#108](https://github.com/dragondiver/kuechen-display/issues/108)
und seine Unterkarten. Die Issues lagen bis zum 19.10.2026 in `rundfunk`.

## Was wo liegt

| Ordner | Inhalt |
|---|---|
| `gehaeuse/blender/` | Gehäuse als Blender-Skripte, `entwurf_o.py` ist der aktuelle Stand; ältere Buchstaben sind die Entwurfsgeschichte |
| `gehaeuse/referenz/` | Maßzeichnung des Displays, Vorbilder (Braun RT 20) |
| `docs/entwuerfe/` | Entwurfsseiten: Galerie, Entwurfsgeschichte, Hardware-Auswahl, Ruhebildschirm |
| `oberflaeche/` | *kommt:* Browser-App für den Chromium-Kiosk (1280 × 800), #127, #133 |
| `geraet/` | *kommt:* Einrichtung des Pi 5 (Kiosk, Dienste, Deploy) |

Gehäuse rendern (Blender im Hintergrund, Bilder landen in `gehaeuse/renders/`, nicht im Git):

```bash
blender -b -P gehaeuse/blender/entwurf_o.py -- w75 acht mantel skala
```

## Abgrenzung zu rundfunk

Das Sprach-Gehirn (GPT-Live, Werkzeuge, Home Assistant, Nachrichten) lebt in
[rundfunk](https://github.com/dragondiver/rundfunk). Wie das Display daran spricht,
entscheidet [rundfunk#128](https://github.com/dragondiver/rundfunk/issues/128); dort
bleiben auch #134 (Stimmung) und #135 (Gespräch wandert zwischen den Geräten).
