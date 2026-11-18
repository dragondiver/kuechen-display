"""Was das Display wach hält (kuechen-display#48).

Der Schlafwächter (pi/schlafen) fragt den Küchen-Dienst über GET /wach, ob er das Display
ausschalten darf. Zwei Dinge halten es wach:

- Elektra: solange ein Gespräch läuft, also Zustand zuhören, nachdenken oder sprechen.
- Ein Video: Die Rückweg-Erweiterung (pi/kiosk-rueckweg) meldet alle 5 s, was die `<video>`-Elemente
  der offenen Seite tun. Hier wird entschieden, ob das „ein laufendes Video“ ist.

- Ein Weckwort („Weiter“, „Zurück“, #89): Wer per Zuruf blättert, fasst das Display nicht an. Das
  Wort hält so lange wach, dass es der Schlafwächter bei seiner nächsten Frage sieht.

Musik allein (Spotify spielt auf dem Evoke) hält nicht wach. Reine Logik ohne Netz und Uhr
(test_wach.py).
"""

from __future__ import annotations

# So breit muss ein Video im Fenster sein, damit es als Video zählt. Spotify zeigt kleine,
# stumme Schleifen (Canvas) neben dem Titel; YouTube spielt auf der Startseite Vorschauen in
# Kachelgröße. Ein Film oder Kochvideo füllt dagegen das Fenster. Schätzwert, am Gerät zu prüfen.
MIN_FLAECHE = 0.2
# Meldet die Seite nichts mehr (Seite zu, Erweiterung weg), zählt das Video nach so vielen
# Sekunden nicht mehr. Die Erweiterung meldet alle 5 s.
VIDEO_FRIST_S = 20.0
# Der Wächter fragt bei hellem Display alle 5 s; das Wort muss länger gelten.
WORT_HALT_S = 6.0


def video_spielt(videos) -> tuple[bool, list[str]]:
    """Läuft unter den gemeldeten `<video>`-Elementen ein Film?

    Ein Eintrag zählt, wenn er spielt, ein Bild hat (Audio-Elemente von Spotify haben keins),
    nicht in Schleife läuft und mindestens MIN_FLAECHE des Fensters füllt. Unbrauchbare Einträge
    zählen nicht, kommen aber als Beanstandung zurück, damit der Dienst sie ins Journal schreibt.
    """
    if not isinstance(videos, list):
        return False, [f"videos ist keine Liste: {str(videos)[:80]}"]
    probleme: list[str] = []
    zaehlt = False
    for v in videos:
        if (
            not isinstance(v, dict)
            or not all(
                isinstance(v.get(k), bool) for k in ("spielt", "bild", "schleife")
            )
            or isinstance(v.get("flaeche"), bool)
            or not isinstance(v.get("flaeche"), (int, float))
        ):
            probleme.append(f"unbrauchbarer Video-Eintrag: {str(v)[:80]}")
            continue
        if (
            v["spielt"]
            and v["bild"]
            and not v["schleife"]
            and v["flaeche"] >= MIN_FLAECHE
        ):
            zaehlt = True
    return zaehlt, probleme


class Wach:
    def __init__(self) -> None:
        self.video_bis: float | None = None
        self.wort_bis: float | None = None

    def wort_gehoert(self, jetzt: float) -> None:
        self.wort_bis = jetzt + WORT_HALT_S

    def video_melden(self, videos, jetzt: float) -> list[str]:
        """Nimmt eine Meldung der Erweiterung an. Gibt Beanstandungen zurück."""
        spielt, probleme = video_spielt(videos)
        self.video_bis = jetzt + VIDEO_FRIST_S if spielt else None
        return probleme

    def video_laeuft(self, jetzt: float) -> bool:
        return self.video_bis is not None and jetzt < self.video_bis

    def gruende(self, elektra_zustand: str, jetzt: float) -> list[str]:
        gruende = []
        if elektra_zustand != "aus":
            gruende.append(f"elektra ({elektra_zustand})")
        if self.video_laeuft(jetzt):
            gruende.append("video")
        if self.wort_bis is not None and jetzt < self.wort_bis:
            gruende.append("weckwort")
        return gruende
