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
WISCH_WEG = 0.28
WISCH_ZEIT_S = 0.8
WISCH_STEIGUNG = 0.6  # |dy| / |dx| höchstens
# Stopp: flache Hand so lange ruhig zeigen.
STOPP_HALTEN_S = 0.6
STOPP_RUHE = 0.06  # höchstens so viel Bewegung während des Haltens
STOPP_SICHER = 0.6
# Bei schnellen Bewegungen verliert die Erkennung die Hand für einzelne Bilder; so lange überbrücken.
LUECKE_S = 0.3
# Nach jeder Geste eine Pause, damit das Zurückführen der Hand nicht gleich wieder blättert.
PAUSE_S = 1.2


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
