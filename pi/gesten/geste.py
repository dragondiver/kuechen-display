"""Aus einer Folge von Handbeobachtungen werden Gesten (kuechen-display#2).

Reine Logik ohne Kamera und ohne MediaPipe, damit sie sich ohne Pi testen lässt.
Festgelegter Umfang (19.10.2026): flache Hand zeigen = Stopp, zur Seite wischen = Blättern.
Bewusst wenige Gesten, damit zufällige Handbewegungen beim Kochen nichts auslösen.

Koordinaten sind normiert (0..1) im aufrechten, nicht gespiegelten Kamerabild. Die Kamera
schaut den Menschen an: Bewegt er die Hand nach *seiner* linken Seite, wandert sie im Bild
nach rechts (x wird größer). Die Richtung im Ereignis ist immer aus Sicht des Menschen.
"""

from collections import deque
from dataclasses import dataclass

# Wischen: so weit muss die Hand quer laufen, in höchstens dieser Zeit, und dabei flach bleiben.
# Tischtest 8.11.2026: Das Ausholen vor dem Wischen lief mit 0,3–0,8 Bildbreiten/s, der echte
# Wischer mit 1,7–2,5. Mit 0,8 s Zeitfenster zählte das Ausholen schon als Wischen in die
# Gegenrichtung; 0,25 s verlangen gut 1,1 Bildbreiten/s.
WISCH_WEG = 0.28
WISCH_ZEIT_S = 0.25
WISCH_STEIGUNG = 0.6  # |dy| / |dx| höchstens
# Stopp: flache Hand so lange ruhig zeigen.
STOPP_HALTEN_S = 0.6
STOPP_RUHE = 0.06  # höchstens so viel Bewegung während des Haltens
STOPP_SICHER = 0.5  # Tischtest 8.11.2026: echte flache Hand 0,50–0,64
# Bei schnellen Bewegungen verliert die Erkennung die Hand für einzelne Bilder; so lange überbrücken.
LUECKE_S = 0.3
# Nach jeder Geste eine Pause, damit das Zurückführen der Hand nicht gleich wieder blättert.
PAUSE_S = 1.2


# Handmitte: Handgelenk und die Grundgelenke der Finger (MediaPipe-Nummern).
MITTE = (0, 5, 9, 13, 17)


def handmitte(punkte) -> tuple[float, float]:
    mitte = [punkte[i] for i in MITTE]
    return sum(p.x for p in mitte) / len(mitte), sum(p.y for p in mitte) / len(mitte)


# Flache Hand aus den Punkten: Für jeden der vier Finger der Abstand Handgelenk–Fingerspitze geteilt
# durch Handgelenk–Fingeransatz. Tischtest 8.11.2026 (kleinster der vier Werte): flache Hand
# 1,57–1,86, Faust 0,57, halb offene Hand 0,17, Hände in normaler Bewegung im Median 1,36.
# MediaPipes eigenes "Open_Palm" erkannte die seitlich gehaltene flache Hand nur in 7 von 47 Bildern.
FLACH_AB = 1.45
SEITENVERHAELTNIS = 16 / 9  # Bild 640x360, x und y sind getrennt normiert
FINGER = ((5, 8), (9, 12), (13, 16), (17, 20))  # Ansatz, Spitze
# Und die Finger müssen nach oben zeigen: Anteil der Richtung Handgelenk → Mittelfingerspitze, der im
# Bild nach oben weist. Tischtest 8.11.2026: erhobene flache Hand 0,95–1,0 (seitlich vereinzelt 0,74),
# flach auf dem Tisch liegende Hand -0,8, normal bewegte Hände höchstens 0,61.
AUFRECHT_AB = 0.7


def _abstand(a, b) -> float:
    return ((a.x - b.x) * SEITENVERHAELTNIS) ** 2 + (a.y - b.y) ** 2


def flache_hand(punkte) -> bool:
    w, spitze = punkte[0], punkte[12]
    dx, dy = (spitze.x - w.x) * SEITENVERHAELTNIS, spitze.y - w.y
    laenge = (dx * dx + dy * dy) ** 0.5
    if laenge == 0 or -dy / laenge < AUFRECHT_AB:
        return False
    return all(
        _abstand(punkte[spitze], w) >= FLACH_AB**2 * _abstand(punkte[ansatz], w)
        for ansatz, spitze in FINGER
    )


def gestenhand(haende) -> int:
    """Welche der erkannten Hände zählt: die am höchsten gehaltene.

    Tischtest 8.11.2026: Mit nur einer gesuchten Hand blieb die Erkennung an der Hand hängen,
    die unten am Bildrand auf dem Tisch lag, und übersah die erhobene.
    """
    return min(range(len(haende)), key=lambda i: handmitte(haende[i])[1])


@dataclass(frozen=True)
class Beobachtung:
    t: float  # Sekunden, monoton
    x: float  # Handmitte
    y: float
    geste: str = ""  # Kategorie von MediaPipe, z. B. "Open_Palm"
    sicherheit: float = 0.0


class Gestenerkenner:
    def __init__(self):
        self.verlauf: deque[Beobachtung] = deque()
        self.gesperrt_bis = 0.0

    def keine_hand(self, t: float) -> None:
        """Keine Hand in diesem Bild. Erst nach einer längeren Lücke zählt die Bewegung davor nicht mehr."""
        if self.verlauf and t - self.verlauf[-1].t > LUECKE_S:
            self.verlauf.clear()

    def beobachte(self, b: Beobachtung) -> dict | None:
        """Nimmt eine Beobachtung auf und gibt höchstens ein Ereignis zurück."""
        if self.verlauf and b.t - self.verlauf[-1].t > LUECKE_S:
            self.verlauf.clear()
        self.verlauf.append(b)
        while self.verlauf and b.t - self.verlauf[0].t > max(
            WISCH_ZEIT_S, STOPP_HALTEN_S
        ):
            self.verlauf.popleft()
        if b.t < self.gesperrt_bis:
            return None

        ereignis = self._wischen(b) or self._stopp(b)
        if ereignis:
            self.gesperrt_bis = b.t + PAUSE_S
            self.verlauf.clear()
        return ereignis

    def _wischen(self, b: Beobachtung) -> dict | None:
        for alt in self.verlauf:
            if b.t - alt.t > WISCH_ZEIT_S:
                continue
            dx, dy = b.x - alt.x, b.y - alt.y
            if abs(dx) >= WISCH_WEG and abs(dy) <= WISCH_STEIGUNG * abs(dx):
                return {"art": "wischen", "richtung": "links" if dx > 0 else "rechts"}
            break  # nur gegen die älteste Beobachtung im Zeitfenster messen
        return None

    def _stopp(self, b: Beobachtung) -> dict | None:
        fenster = [a for a in self.verlauf if b.t - a.t <= STOPP_HALTEN_S]
        if not fenster or b.t - fenster[0].t < STOPP_HALTEN_S * 0.9:
            return None
        if not all(
            a.geste == "Open_Palm" and a.sicherheit >= STOPP_SICHER for a in fenster
        ):
            return None
        xs, ys = [a.x for a in fenster], [a.y for a in fenster]
        if max(xs) - min(xs) > STOPP_RUHE or max(ys) - min(ys) > STOPP_RUHE:
            return None
        return {"art": "stopp"}
