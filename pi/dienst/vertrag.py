"""Netz-Gerät-Vertrag der rundfunk-Bridge, Seite des Küchen-Displays (rundfunk#128).

Der Vertrag selbst steht in rundfunk/src/rundfunk/netzgeraet.py. Hier liegt nur die Logik
ohne Netz und ohne Ton, damit sie sich ohne Pi testen lässt (test_vertrag.py):

- welcher Kanal des XVF3800 zur Bridge geht,
- wann das Mikrofon offen ist,
- was eine Nachricht der Bridge auf dem Display auslöst.
"""

from __future__ import annotations

import json
import logging
from array import array
from dataclasses import dataclass, field

log = logging.getLogger("dienst")

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
        # Zuhören oder Nachdenken: Gespräch beenden (8.11.2026). Seit rundfunk#238 schließt "ende"
        # die Live-Sitzung sofort, statt bis zur Ruhezeit der Bridge zu warten.
        return [Aktion("senden", {"type": "ende"}), *self.getrennt()]

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


LOKAL = "lokal-"


def ist_lokal(kennung) -> bool:
    """Ein Befehl, den der Dienst selbst ablegt (Weckwort, #89). Die Bridge kennt seine Nummer
    nicht: Seine Quittung darf nicht zu ihr, und eine Fehler-Quittung für ihn auch nicht."""
    return isinstance(kennung, str) and kennung.startswith(LOKAL)


def quittung_leiten(daten: dict) -> tuple[dict | None, str | None]:
    """Quittung der Rückweg-Erweiterung: (Nachricht an die Bridge, Journalzeile).

    Für einen Befehl der Bridge geht die Quittung weiter an sie und ins Journal nur ein Fehler.
    Für einen lokalen Befehl (Weckwort) kennt die Bridge die Nummer nicht: Es geht nichts zu ihr,
    und das Ergebnis steht im Journal.
    """
    kennung = daten.get("id")
    if ist_lokal(kennung):
        if daten.get("ok") is True:
            return None, f"Weckwort: {kennung} ausgeführt"
        grund = str(daten.get("fehler", "kein Grund gemeldet"))[:120]
        return None, f"Weckwort: {kennung} ohne Wirkung: {grund}"
    return {
        "type": "quittung",
        **{k: daten[k] for k in ("id", "ok", "fehler") if k in daten},
    }, None


def abgelaufene_melden(alt: list[dict]) -> tuple[list[dict], list[str]]:
    """Befehle, die niemand abgeholt hat: (Fehler-Quittungen für die Bridge, Journalzeilen für die
    lokalen unter ihnen)."""
    bridge: list[dict] = []
    journal: list[str] = []
    for befehl in alt:
        if ist_lokal(befehl["id"]):
            journal.append(
                f"Weckwort: Befehl {befehl['id']} hat niemand abgeholt (Rückweg-Erweiterung weg?)"
            )
        else:
            bridge.append(
                {
                    "type": "quittung",
                    "id": befehl["id"],
                    "ok": False,
                    "fehler": "Die Anzeige ist nicht offen.",
                }
            )
    return bridge, journal


class Ablage:
    """Befehle für eine App ohne Kiosk-Seite (kuechen-display#70).

    Ist Spotify offen, gibt es keine Kiosk-Seite, die einen Befehl der Bridge annimmt. Die
    Rückweg-Erweiterung fragt dann jede Sekunde `GET /lage` ab und holt ihn sich hier. Holt ihn
    niemand innerhalb von FRIST_S, bekommt die Bridge eine Fehler-Quittung.
    """

    # Unter der Frist der Bridge (rundfunk BEFEHL_FRIST_S = 3 s), sonst führt die App einen
    # Befehl aus, für den Elektra schon „keine Antwort“ gesagt hat (verifier zu #71).
    FRIST_S = 2.5
    # So lange nach der letzten Abfrage gilt eine App als vorn. Die Erweiterung fragt jede
    # Sekunde; die Kiosk-Seite meldet ihr Kommen über /ereignisse (kiosk_vorn).
    APP_WEG_S = 2.5

    def __init__(self) -> None:
        self.befehle: list[tuple[float, dict]] = []
        self.app_zuletzt: float | None = None
        # Die Kiosk-Seite meldet beim Verlassen /weg. Ihr SSE-Abonnent gilt sonst noch bis zu 15 s
        # als lebendig, und ein Befehl ginge an eine Seite, die es nicht mehr gibt.
        self.kiosk_weg = False

    def app_meldet(self, jetzt: float) -> None:
        self.app_zuletzt = jetzt

    def kiosk_vorn(self, jetzt: float) -> list[dict]:
        """Eine Kiosk-Seite hat sich verbunden. Gibt die Befehle zurück, die noch gelten; die
        bekommt sie gleich (Neuladen, Rückkehr aus einer App)."""
        self.app_zuletzt = None
        self.kiosk_weg = False
        offen = [
            b
            for zeit, b in self.befehle
            if jetzt - zeit < self.FRIST_S and not ist_lokal(b.get("id"))
        ]
        # Lokale Befehle gehören der Erweiterung; die Kiosk-Seite bekommt sie nicht. Wartet einer
        # gerade, weil die Seite neu lädt, geht er verloren: das kommt ins Journal.
        for _, b in self.befehle:
            if ist_lokal(b.get("id")):
                log.warning(
                    "Weckwort: Befehl %s verworfen, die Kiosk-Seite hat sich neu verbunden",
                    b.get("id"),
                )
        self.befehle = [
            (z, b)
            for z, b in self.befehle
            if jetzt - z >= self.FRIST_S and not ist_lokal(b.get("id"))
        ]
        return offen

    def kiosk_geht(self) -> None:
        self.kiosk_weg = True

    def app_vorn(self, jetzt: float) -> bool:
        if self.kiosk_weg:
            return True
        return (
            self.app_zuletzt is not None and jetzt - self.app_zuletzt < self.APP_WEG_S
        )

    def ablegen(self, befehl: dict, jetzt: float) -> None:
        self.befehle.append((jetzt, befehl))

    def abholen(self, jetzt: float) -> dict | None:
        """Den ältesten Befehl, der noch nicht abgelaufen ist, oder None."""
        for i, (zeit, befehl) in enumerate(self.befehle):
            if jetzt - zeit < self.FRIST_S:
                del self.befehle[i]
                return befehl
        return None

    def abgelaufen(self, jetzt: float) -> list[dict]:
        """Nimmt die abgelaufenen Befehle heraus; für sie geht eine Fehler-Quittung raus."""
        alt = [b for zeit, b in self.befehle if jetzt - zeit >= self.FRIST_S]
        self.befehle = [(z, b) for z, b in self.befehle if jetzt - z < self.FRIST_S]
        return alt
