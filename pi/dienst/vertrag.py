"""Netz-Gerät-Vertrag der rundfunk-Bridge, Seite des Küchen-Displays (rundfunk#128).

Der Vertrag selbst steht in rundfunk/src/rundfunk/netzgeraet.py. Hier liegt nur die Logik
ohne Netz und ohne Ton, damit sie sich ohne Pi testen lässt (test_vertrag.py):

- welcher Kanal des XVF3800 zur Bridge geht,
- wann das Mikrofon offen ist,
- was eine Nachricht der Bridge auf dem Display auslöst.
"""

from __future__ import annotations

import json
from array import array
from dataclasses import dataclass, field

RATE = 16000
RAHMEN_PROBEN = 960  # 60 ms, wie im Vertrag
RAHMEN_BYTES = RAHMEN_PROBEN * 2  # 1920, mono PCM16
# Der XVF3800 liefert über ALSA 6 Kanäle. Kanal 0 ist das aufbereitete Signal
# (Tischtest 8.11.2026: rund 30 dB über den rohen Mikrofonen 2–5).
XVF_KANAELE = 6
XVF_KANAL = 0
ROH_BYTES = RAHMEN_PROBEN * XVF_KANAELE * 2

ZUSTAENDE = ("zuhoeren", "nachdenken", "sprechen", "aus")


def kanal(roh: bytes, nummer: int = XVF_KANAL, kanaele: int = XVF_KANAELE) -> bytes:
    """Ein Kanal aus verschachteltem PCM16."""
    proben = array("h")
    proben.frombytes(roh)
    return proben[nummer::kanaele].tobytes()


@dataclass
class Aktion:
    """Was der Dienst nach einer Nachricht tun soll."""

    art: str  # "anzeige", "senden", "verwerfen", "lautstaerke"
    daten: dict = field(default_factory=dict)


class Leitung:
    """Zustand eines Netz-Geräts. Kennt weder WebSocket noch Lautsprecher."""

    def __init__(self) -> None:
        self.zustand = "aus"
        self.mikro_offen = False

    # --- vom Display ------------------------------------------------------
    def tipp(self) -> list[Aktion]:
        """Tipp auf die Figur: aus → Gespräch beginnt, sprechend → Elektra hört auf, sonst → Ende."""
        if self.zustand == "aus":
            # Bis die Bridge den ersten Zustand schickt, gilt das Mikrofon schon als offen,
            # sonst gingen die ersten Wörter verloren.
            self.mikro_offen = True
            return [
                Aktion("senden", {"type": "wort"}),
                Aktion("anzeige", {"ereignis": "zustand", "wert": "zuhoeren"}),
            ]
        if self.zustand == "sprechen":
            return self.stopp()
        # Zuhören oder Nachdenken: Gespräch am Display beenden (8.11.2026). Die Bridge kennt dafür
        # noch keine Nachricht; ohne Ton vom Mikrofon schläft sie nach ihrer Ruhezeit ein.
        return self.getrennt()

    def stopp(self) -> list[Aktion]:
        """Flache Hand oder Tipp beim Sprechen. Ohne Gespräch gibt es nichts anzuhalten."""
        if self.zustand == "aus":
            return []
        return [
            Aktion("verwerfen"),
            Aktion("senden", {"type": "geste", "name": "stopp"}),
        ]

    def getrennt(self) -> list[Aktion]:
        self.zustand = "aus"
        self.mikro_offen = False
        return [
            Aktion("verwerfen"),
            Aktion("anzeige", {"ereignis": "zustand", "wert": "aus"}),
        ]

    # --- von der Bridge ---------------------------------------------------
    def nachricht(self, roh: str) -> list[Aktion]:
        try:
            msg = json.loads(roh)
        except json.JSONDecodeError:
            return []
        if not isinstance(msg, dict):
            return []
        typ = msg.get("type")
        if typ == "zustand":
            wert = msg.get("wert")
            if wert not in ZUSTAENDE:
                return []
            aktionen = []
            # Ungespieltes weg, sobald Elektra nicht mehr spricht (Vertrag: höchstens 0,3 s Puffer).
            if wert != "sprechen":
                aktionen.append(Aktion("verwerfen"))
            self.zustand = wert
            self.mikro_offen = wert != "aus"
            aktionen.append(Aktion("anzeige", {"ereignis": "zustand", "wert": wert}))
            return aktionen
        if typ == "text":
            return [
                Aktion(
                    "anzeige",
                    {
                        "ereignis": "text",
                        "rolle": msg.get("rolle", ""),
                        "text": str(msg.get("text", "")),
                    },
                )
            ]
        if typ == "symbole":
            return [
                Aktion(
                    "anzeige",
                    {"ereignis": "symbole", "symbole": msg.get("symbole", [])},
                )
            ]
        if typ == "lautstaerke":
            wert = msg.get("wert")
            if isinstance(wert, (int, float)) and not isinstance(wert, bool):
                return [Aktion("lautstaerke", {"wert": max(0, min(100, int(wert)))})]
            return []
        if typ == "befehl":
            bid = msg.get("id")
            if type(bid) is not int:
                return []
            return [
                Aktion(
                    "anzeige",
                    {
                        "ereignis": "befehl",
                        "id": bid,
                        "name": msg.get("name", ""),
                        "argumente": msg.get("argumente") or {},
                    },
                )
            ]
        return []
