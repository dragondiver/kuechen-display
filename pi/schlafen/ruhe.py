"""Entscheidungslogik fürs Schlafen des Küchen-Displays (kuechen-display#48).

Nur reine Funktionen und Zustandsautomaten, ohne Wayland, ohne /dev/input, ohne Uhr: Die Zeit
kommt als Argument. So lässt sich alles ohne Pi testen (test_ruhe.py). Was am Gerät passiert
(wlopm, Helligkeit, swayidle, Touch lesen), steht in schlafwaechter.py.

Drei Bausteine:
- konfig_lesen: schlafen.conf, mit lauten Rückfallwerten statt stillem Verwerfen
- Ruhe: Ist Ruhe erreicht, hält etwas wach, soll geweckt werden?
- WeckZaehler: Hat der Küchen-Dienst ein Weckwort gehört (#89)? Zählt, ob es ein neues gibt.
- WeckTipp: Wann beginnt der Tipp, der das Display weckt, und wann ist er zu Ende? Bis dahin
  bekommt ihn nur der Wächter, kein Fenster.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

SCHLAFEN = "schlafen"
WECKEN = "wecken"
NICHTS = "nichts"

# swayidle meldet nach so vielen Sekunden ohne Eingabe „ruhig“ (Schritt, nicht die Ruhezeit).
IDLE_SCHRITT_S = 1.0
# Nach einem misslungenen Einschlafen so lange nicht noch einmal versuchen.
NEUER_VERSUCH_S = 60.0

AUS_WEGE = ("beides", "backlight", "ausgang")
STANDARD_RUHE_S = 300
STANDARD_AUS_WEG = "beides"
MIN_RUHE_S = 10
MAX_RUHE_S = 24 * 3600


# --- Konfiguration -----------------------------------------------------------------------
@dataclass(frozen=True)
class Konfig:
    ruhe_s: int = STANDARD_RUHE_S
    aus_weg: str = STANDARD_AUS_WEG


def konfig_lesen(text: str) -> tuple[Konfig, list[str]]:
    """Liest schlafen.conf (SCHLUESSEL=Wert, # beginnt einen Kommentar).

    Gibt die Konfiguration und die Beanstandungen zurück. Ein unbekannter Schlüssel oder ein
    unbrauchbarer Wert bekommt den Standardwert und eine Meldung, die der Wächter ins Journal
    schreibt; nichts verschwindet still.
    """
    werte: dict[str, str] = {}
    probleme: list[str] = []
    for nr, roh in enumerate(text.splitlines(), 1):
        zeile = roh.split("#", 1)[0].strip()
        if not zeile:
            continue
        if "=" not in zeile:
            probleme.append(f"Zeile {nr}: '{zeile}' ist keine Zuweisung")
            continue
        schluessel, wert = (s.strip() for s in zeile.split("=", 1))
        if schluessel not in ("RUHE_S", "AUS_WEG"):
            probleme.append(f"Zeile {nr}: unbekannter Schlüssel '{schluessel}'")
            continue
        werte[schluessel] = wert

    ruhe_s = STANDARD_RUHE_S
    if "RUHE_S" in werte:
        try:
            wert = int(werte["RUHE_S"])
            if not MIN_RUHE_S <= wert <= MAX_RUHE_S:
                raise ValueError
            ruhe_s = wert
        except ValueError:
            probleme.append(
                f"RUHE_S='{werte['RUHE_S']}' geht nicht (ganze Sekunden, "
                f"{MIN_RUHE_S} bis {MAX_RUHE_S}), es gilt {STANDARD_RUHE_S}"
            )
    aus_weg = STANDARD_AUS_WEG
    if "AUS_WEG" in werte:
        if werte["AUS_WEG"] in AUS_WEGE:
            aus_weg = werte["AUS_WEG"]
        else:
            probleme.append(
                f"AUS_WEG='{werte['AUS_WEG']}' geht nicht ({', '.join(AUS_WEGE)}), "
                f"es gilt {STANDARD_AUS_WEG}"
            )
    return Konfig(ruhe_s, aus_weg), probleme


# --- Ruhe erreicht? ----------------------------------------------------------------------
class Ruhe:
    """Zustand des Wächters ohne Hardware.

    Eingaben von außen (alle mit Zeit in Sekunden, monoton):
    - aktiv(t): swayidle meldet Eingabe (Touch, Tastatur, VNC, alles, was labwc sieht)
    - ruhig(t): swayidle meldet, dass seit IDLE_SCHRITT_S nichts mehr kam
    - beruehrt(t): der Wächter selbst hat bei ausgeschaltetem Display eine Berührung gelesen
    - halt(t, haelt): Küchen-Dienst sagt, ob Video oder Elektra wach halten (True auch, wenn
      er nicht antwortet: im Zweifel an). Das verhindert das Einschlafen, weckt aber ein
      schlafendes Display nicht (Festlegung 16.11.2026: Elektra, auch mit Erinnerung, lässt es
      dunkel; nur Berührung oder andere Eingabe wecken)
    - weckwort(t): der Küchen-Dienst hat „Weiter“ oder „Zurück“ gehört und das Display war (oder
      galt als) dunkel. Weckt ein schlafendes Display wie eine Eingabe und startet die Ruhezeit neu,
      verschluckt aber keine Berührung, denn es gab keine
    - eingeschlafen(t) / aufgewacht(t): der Wächter hat das Display aus- bzw. eingeschaltet
    - tick(t): alle Sekunde; sagt SCHLAFEN, WECKEN oder NICHTS

    „Ruhe“ heißt: seit `ruhe_s` weder Eingabe noch etwas, das wach hält. Hat ein Video oder
    ein Gespräch bis eben gehalten, läuft die Zeit erst ab dessen Ende.
    """

    def __init__(self, ruhe_s: int, jetzt: float) -> None:
        self.ruhe_s = ruhe_s
        self.schlaeft = False
        # Bis swayidle „ruhig“ sagt, gilt Eingabe als laufend (auch wenn swayidle fehlt).
        self.eingabe_laeuft = True
        self.letzte_eingabe = jetzt
        self.letzter_halt: float | None = None
        self.haelt = False
        self.nicht_vor = 0.0

    def aktiv(self, jetzt: float) -> str:
        self.eingabe_laeuft = True
        self.letzte_eingabe = jetzt
        return WECKEN if self.schlaeft else NICHTS

    def ruhig(self, jetzt: float) -> None:
        self.eingabe_laeuft = False
        # Die letzte Eingabe lag IDLE_SCHRITT_S zurück; nie hinter eine spätere Berührung zurück.
        self.letzte_eingabe = max(self.letzte_eingabe, jetzt - IDLE_SCHRITT_S)

    def beruehrt(self, jetzt: float) -> None:
        """Berührung, die nur der Wächter sah (Display war aus, Touch war gesperrt). swayidle
        weiß davon nichts und bleibt „ruhig“."""
        self.letzte_eingabe = max(self.letzte_eingabe, jetzt)

    def weckwort(self, jetzt: float) -> str:
        self.letzte_eingabe = max(self.letzte_eingabe, jetzt)
        return WECKEN if self.schlaeft else NICHTS

    def eingabe_unbekannt(self) -> str:
        """swayidle fehlt: Ob jemand tippt, ist nicht zu sehen. Im Zweifel an."""
        self.eingabe_laeuft = True
        return WECKEN if self.schlaeft else NICHTS

    def halt(self, jetzt: float, haelt: bool) -> None:
        # Der Halt endet irgendwann zwischen zwei Abfragen; als Ende gilt die spätere, damit
        # die Ruhezeit eher zu lang als zu kurz ausfällt.
        if haelt or self.haelt:
            self.letzter_halt = jetzt
        self.haelt = haelt

    def eingeschlafen(self) -> None:
        self.schlaeft = True

    def aufgewacht(self, jetzt: float) -> None:
        self.schlaeft = False
        self.letzte_eingabe = max(self.letzte_eingabe, jetzt)

    def schlafen_misslungen(self, jetzt: float) -> None:
        self.nicht_vor = jetzt + NEUER_VERSUCH_S

    def tick(self, jetzt: float) -> str:
        if self.schlaeft:
            return WECKEN if self.eingabe_laeuft else NICHTS
        if self.haelt or self.eingabe_laeuft or jetzt < self.nicht_vor:
            return NICHTS
        letzte = self.letzte_eingabe
        if self.letzter_halt is not None:
            letzte = max(letzte, self.letzter_halt)
        return SCHLAFEN if jetzt - letzte >= self.ruhe_s else NICHTS


# --- Weckwort ----------------------------------------------------------------------------
class WeckZaehler:
    """Erkennt an der Antwort von GET /wach, ob der Küchen-Dienst ein neues Weckwort meldet.

    Die Antwort trägt `start` (ändert sich bei jedem Start des Küchen-Dienstes) und `wecken` (Zähler
    seit diesem Start). Beim ersten Mal und nach einem neuen `start` wird nur der Stand gemerkt:
    Ein Wecken, das vor dem Start des Wächters oder des Dienstes lag, soll nicht nachträglich
    das Display einschalten. Steigt der Zähler danach, ist es ein neues Wort.
    """

    def __init__(self) -> None:
        self.start = None
        self.zaehler = 0

    def neu(self, start, zaehler) -> bool:
        if not isinstance(start, int) or not isinstance(zaehler, int):
            return False  # alter Dienst oder unlesbare Antwort: nichts zu wecken
        if start != self.start:
            self.start, self.zaehler = start, zaehler
            return False
        gestiegen = zaehler > self.zaehler
        self.zaehler = zaehler
        return gestiegen


# --- Weck-Tipp ---------------------------------------------------------------------------
EV_KEY = 0x01
EV_ABS = 0x03
BTN_TOUCH = 0x14A
ABS_MT_SLOT = 0x2F
ABS_MT_TRACKING_ID = 0x39

EVENT_FORMAT = (
    "llHHi"  # struct input_event auf 64 Bit: Zeit (Sekunden, µs), Art, Code, Wert
)
EVENT_BYTES = struct.calcsize(EVENT_FORMAT)


def ereignisse_zerlegen(roh: bytes) -> tuple[list[tuple[int, int, int]], bytes]:
    """Zerlegt gelesene Bytes in (Art, Code, Wert) und gibt den unvollständigen Rest zurück."""
    ganz = len(roh) - len(roh) % EVENT_BYTES
    ereignisse = [
        (art, code, wert)
        for _s, _us, art, code, wert in struct.iter_unpack(EVENT_FORMAT, roh[:ganz])
    ]
    return ereignisse, roh[ganz:]


def touch_geraet_finden(geraete: str, name: str) -> str | None:
    """Pfad (/dev/input/eventN) des Eingabegeräts mit diesem Namen, aus /proc/bus/input/devices."""
    for block in geraete.split("\n\n"):
        if f'Name="{name}"' not in block:
            continue
        for zeile in block.splitlines():
            if zeile.startswith("H: Handlers="):
                for teil in zeile.split("=", 1)[1].split():
                    if teil.startswith("event") and teil[5:].isdigit():
                        return f"/dev/input/{teil}"
    return None


@dataclass(frozen=True)
class Tipp:
    weck: bool = False  # Berührung beginnt: Display einschalten
    frei: bool = False  # Berührung vorbei (oder zu lange): Touch wieder an labwc geben


class WeckTipp:
    """Folgt den Rohereignissen des Touchs, solange der Wächter ihn für sich allein hat.

    Die erste Berührung weckt (weck). Der Touch bleibt gesperrt, bis der Finger wieder oben
    ist (frei), damit weder das Aufsetzen noch das Loslassen als Klick in einem Fenster ankommt.
    Hängt eine Berührung länger als MAX_S, gibt tick() den Touch trotzdem frei: Ein Display, das
    dauerhaft keinen Touch annimmt, ist schlimmer als ein verirrter Klick.
    """

    MAX_S = 5.0

    def __init__(self) -> None:
        self.slot = 0
        self.aktiv: set[int] = set()
        self.beginn: float | None = None

    def ereignis(self, art: int, code: int, wert: int, jetzt: float) -> Tipp:
        unten = oben = False
        if art == EV_ABS and code == ABS_MT_SLOT:
            self.slot = wert
        elif art == EV_ABS and code == ABS_MT_TRACKING_ID:
            if wert >= 0:
                self.aktiv.add(self.slot)
                unten = True
            else:
                self.aktiv.discard(self.slot)
                oben = True
        elif art == EV_KEY and code == BTN_TOUCH:
            if wert:
                unten = True
            else:
                self.aktiv.clear()
                oben = True
        weck = unten and self.beginn is None
        if weck:
            self.beginn = jetzt
        frei = oben and self.beginn is not None and not self.aktiv
        return Tipp(weck=weck, frei=frei)

    def tick(self, jetzt: float) -> Tipp:
        if self.beginn is not None and jetzt - self.beginn >= self.MAX_S:
            return Tipp(frei=True)
        return Tipp()
