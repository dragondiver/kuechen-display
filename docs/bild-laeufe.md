# Läufe der Bild-API

Wird von `werkzeuge/figur_bilder.py` und `werkzeuge/wetter_bilder.py` fortgeschrieben.
Kosten aus den Tokens der API-Antwort und den Preisen in `werkzeuge/bildkosten.py`.

| Zeit | Skript | Bild | Modell | Qualität | Bild ein | Text ein | Bild aus | Kosten |
|---|---|---|---|---|---:|---:|---:|---:|
| 2026-10-19 22:57 | wetter_bilder | regen-ton | gpt-image-2.5-sunburst | medium | 1024 | 334 | 343 | 0.020 $ |
| 2026-10-19 22:57 | wetter_bilder | regen-flach | gpt-image-2.5-sunburst | medium | 1024 | 320 | 343 | 0.020 $ |
| 2026-10-19 22:58 | wetter_bilder | regen-bilderbuch | gpt-image-2.5-sunburst | medium | 1024 | 324 | 343 | 0.020 $ |
| 2026-10-19 23:05 | wetter_bilder | flach/gedaempft | gpt-image-2.5-sunburst | medium | 2560 | 123 | 343 | 0.031 $ |
| 2026-10-19 23:05 | wetter_bilder | flach/sonnig | gpt-image-2.5-sunburst | medium | 2560 | 136 | 343 | 0.031 $ |
| 2026-10-19 23:06 | wetter_bilder | flach/wolkig | gpt-image-2.5-sunburst | medium | 2560 | 134 | 343 | 0.031 $ |
| 2026-10-19 23:06 | wetter_bilder | flach/nacht | gpt-image-2.5-sunburst | medium | 2560 | 147 | 343 | 0.032 $ |
| 2026-10-19 23:06 | wetter_bilder | flach/schnee | gpt-image-2.5-sunburst | medium | 2560 | 133 | 343 | 0.031 $ |
