# Tischständer für den Tischtest

Ein gedruckter Helfer für den Tischtest ([#18](https://github.com/dragondiver/kuechen-display/issues/18)):
Display, Kamera, Mikrofonleiste und die zwei Lautsprecher stehen damit ungefähr so zueinander wie
später im Gehäuse, ohne dass etwas verschraubt wird. Das Modell entsteht aus
`gehaeuse/blender/tischstaender.py`.

## Die zwei Teile

**Sockel** (240 × 165 × 129 mm). Das Display steht in einer 8 mm breiten Rinne und lehnt mit 75°
an zwei Stützen. Dahinter sitzen zwei Becher für die Visaton FRS 7, Membran nach oben. Jeder Becher
ist nach außen auf 120° offen, damit Krokodilklemmen an die Lötfahnen passen; nach innen gibt es
einen 10 mm breiten Kabelschlitz. Zwischen den Bechern bleibt Platz für den Pi-Turm.

**Leiste** (200 × 44 mm). Sie wird oben auf die zwei Zapfen der Stützen gesteckt. Vorn sitzt die
Tasche für das Camera Module 3: Platine von oben einschieben, das Kabel läuft durch den Schlitz
nach unten. Die Tasche ist 15° nach hinten geneigt. Dahinter sitzt die Mikrofonleiste mit ihren
Enden in zwei Taschen, 5 mm über der Leiste, und liegt dort nur mit den Rändern auf. Die Mitte bleibt frei, weil das Flachbandkabel quer
über die lange Kante abgeht.

Die Lautsprecher strahlen hier nach oben, im Gehäuse später zur Seite. Für die Echounterdrückung
ist der Ständer damit der härtere Fall.

## STL erzeugen

```bash
blender -b -P gehaeuse/blender/tischstaender.py
```

Das Skript schreibt `sockel.stl`, `leiste.stl` und drei Vorschaubilder nach
`gehaeuse/renders/tischstaender/` (nicht im Git). In der Ausgabe steht je Teil eine Zeile
`PRUEF …` mit Außenmaßen, Volumen und der Zahl offener Kanten. Die muss 0 sein.

## Drucken

1. Beide STL in Bambu Studio laden, Drucker A1, Düse 0,4 mm.
2. Die Teile so liegen lassen, wie sie kommen: Sockel auf der Bodenplatte, Leiste auf der flachen
   Unterseite. Den Sockel quer aufs Bett legen (240 mm entlang einer Bettkante).
3. PLA, Schichthöhe 0,2 mm, 15 % Füllung, keine Stützen.
4. Wer erst probieren will, druckt die Leiste allein. Sie braucht wenig Material, und an ihr sitzen
   die zwei engsten Passungen (Kameratasche, Taschen der Mikrofonleiste).

## Maße ändern

Oben im Skript steht der Block `MASSE`. Gemessen am 19.11.2026:

| Teil | Maß |
|---|---|
| Display, Dicke an der Kante | 5,3 mm |
| Glasüberstand über den Körper | oben, unten, rechts 3 mm; links (von vorn) 8 mm |
| Mikrofonleiste | 110,6 × 11,1 mm |
| FRS 7, Flansch | 66,4 mm im Quadrat, 2,87 mm dick |
| FRS 7, Korb hinter dem Flansch | Ø 61,7 mm |

Die Breite der Kameraplatine (25 mm) stammt aus dem Datenblatt von Raspberry Pi.

## Noch nicht geprüft

Die erste Leiste ist am 19.11.2026 gedruckt: Die Kamera passt in die Tasche. Die Mikrofonablage
mit zwei durchgehenden Schienen passte nicht (kein Platz fürs Kabel, Platine lag lose) und ist
durch die Endtaschen ersetzt; die sind noch nicht gedruckt. Der Sockel ist auch noch nicht gedruckt,
damit ist offen, ob Zapfen und Löcher mit 0,35 mm Luft gut sitzen.
