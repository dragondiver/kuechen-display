# kuechen-display

Siehe README. Ergänzend für die Arbeit hier:

- **Festlegungen stehen in den Issues**, nicht im Code. #1 ist die Übersicht, #15 enthält
  die Zusammenfassung zur Oberfläche (18.10.2026), #10 die Apps-Seiten. Vor dem Bauen dort lesen.
- **Entwürfe vor Code:** Oberflächen werden erst als Entwurf (HTML im Artefakt oder in
  `docs/entwuerfe/`) besprochen. Screenshots von Florian sind Vorbild für den *Inhalt*,
  das Aussehen folgt dem gewählten Design (C · Glaskarten).
- **Keine dauernde Bewegung** auf dem Bildschirm (Küche). Bewegung nur bei Erinnerung und beim Blättern.
- **Blender:** `transform_apply` immer mit `location=False, rotation=False`; Area-Lights 10–30 W.
  Renders gehören nicht ins Git.
- **Sprache** gehört nach rundfunk (rundfunk#128). Hier nur, was auf dem Pi 5 läuft.
- **Drucker:** Bambu Lab A1 ohne AMS, eine Farbe pro Teil, Bett ca. 256 mm.
- **Abläufe dokumentieren:** Was Florian selbst ausführt (Skripte, Einrichtung), bekommt im selben PR
  eine Markdown-Anleitung unter `docs/` mit Schritten und genauen Befehlen (Beispiel: `docs/bilder-erzeugen.md`).
- **GitHub Pages** veröffentlicht `docs/` unter https://dragondiver.github.io/kuechen-display/ (seit 19.10.2026).
  HTML-Seiten in `docs/` brauchen einen vollständigen Kopf (`<!doctype html>`, charset, viewport); `docs/index.md` ist die Startseite.
