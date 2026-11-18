"""Weckwort „Weiter“ und „Zurück“ bei offenem Rezept (kuechen-display#89).

Ist ein Rezept von mise-en-place offen, hört der Küchen-Dienst auf das Mikrofon, das er ohnehin
liest (mikro_schleife), und wertet genau zwei Wörter aus. Die Erkennung läuft auf dem Pi (Vosk,
Grammatik auf zwei Wörter), kein Ton verlässt das Gerät.

- Display dunkel (oder Zustand unbekannt): „Weiter“ und „Zurück“ wecken nur.
- Display an: sie blättern, ohne Tipp und ohne Elektra (Befehl `rezeptschritt`).
- Kein Rezept offen, oder Elektra bzw. ein Diktat ist dran: der Ton wird nicht ausgewertet.

Alles Entscheidende ist reine Logik ohne Vosk, Uhr und Netz (test_weckwort.py). Vosk wird erst in
`erkenner_laden` importiert: Fehlt das Paket oder das Modell, läuft der Dienst weiter und schreibt
einen Fehler ins Journal.
"""

from __future__ import annotations

import json
import logging
import queue
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("weckwort")

NICHTS = "nichts"
WECKEN = "wecken"
VOR = "vor"
ZURUECK = "zurueck"

# Was erkannt werden soll. Die Grammatik lässt nur diese Wörter und [unk] („irgendwas anderes“) zu.
WOERTER = {"weiter": VOR, "zurück": ZURUECK, "zurueck": ZURUECK}
GRAMMATIK = '["weiter", "zurück", "[unk]"]'

# Dasselbe Wort nicht zweimal in dieser Zeit (Nachhall, doppelt erkannt, Zuruf und Echo).
ENTPRELL_S = 1.5
# So lange nach Elektra, Diktat oder Wiedergabe wird noch nichts ausgewertet: Das Ende ihrer
# Stimme klingt im Raum nach und steckt noch in der Erkennung.
NACHLAUF_S = 1.5
# Ohne neue Meldung der Erweiterung gilt ein Rezept nach so vielen Sekunden als zu. Sie meldet alle 2 s.
REZEPT_FRIST_S = 8.0
# So alt darf die Meldung des Schlafwächters sein. Er fragt bei hellem Display alle 5 s, bei
# dunklem jede Sekunde; ist sie älter (Wächter hängt oder ist aus), gilt der Zustand als unbekannt.
ANZEIGE_FRIST_S = 15.0
# So viele ungeprüfte Rahmen (60 ms) dürfen warten; mehr heißt, die Erkennung kommt nicht mit.
WARTESCHLANGE = 100


def wort_lesen(text: str) -> tuple[str | None, str | None]:
    """Aus dem Text einer Erkennung das Wort („weiter“ oder „zurueck“), oder keins.

    Zweiter Wert: warum ein Treffer trotzdem verworfen wurde (für das Journal), sonst None.
    Es zählt nur ein Wort für sich allein, auch mehrfach („weiter weiter“). Steht etwas anderes
    davor oder dahinter („wie geht es weiter“ erkennt die Grammatik als „[unk] [unk] [unk] weiter“)
    oder kommen beide Wörter vor, bleibt es dabei, dass nichts passiert: Im Gespräch fällt „weiter“
    oft, und ein Blättern nach Gefühl wäre schlimmer als ein überhörtes Wort.
    """
    teile = text.lower().split()
    bekannt = {WOERTER[t] for t in teile if t in WOERTER}
    if not bekannt:
        return None, None
    if len(bekannt) > 1:
        return None, f"beide Wörter in einer Äußerung: {text!r}"
    if any(t not in WOERTER for t in teile):
        return None, f"nicht allein gesagt: {text!r}"
    return bekannt.pop(), None


def entscheide(
    wort: str, rezept_offen: bool, gesperrt: bool, dunkel: bool | None
) -> str:
    """Was ein erkanntes Wort auslöst. `dunkel` None heißt: unbekannt.

    Bei unbekanntem Zustand wird geweckt und nicht geblättert: Ein Wecken bei hellem Display ist
    harmlos, ein Blättern bei dunklem Display bliebe unbemerkt.
    """
    if not rezept_offen or gesperrt:
        return NICHTS
    if dunkel is not False:
        return WECKEN
    return wort


class Rezept:
    """Ist ein Rezept offen? Die Erweiterung meldet es alle 2 s (POST /rezept).

    Ohne neue Meldung gilt es nach REZEPT_FRIST_S als zu. Ausnahme: Das Display ist dunkel. Die
    Seite läuft dann womöglich nicht mehr (hidden, Zeitgeber gedrosselt), und ein Rezept, das beim
    Einschlafen offen war, soll es bleiben. Dann zählt die Frist nur bis zum Dunkelwerden.
    """

    def __init__(self) -> None:
        self.offen = False
        self.zeit = 0.0

    def melden(self, offen: bool, jetzt: float) -> None:
        self.offen = offen
        self.zeit = jetzt

    def zuruecksetzen(self) -> None:
        """Die Kiosk-Seite ist wieder vorn (oder weg): kein Rezept."""
        self.offen = False

    def gilt(self, jetzt: float, dunkel_seit: float | None) -> bool:
        if not self.offen:
            return False
        if jetzt - self.zeit < REZEPT_FRIST_S:
            return True
        return dunkel_seit is not None and dunkel_seit - self.zeit < REZEPT_FRIST_S


class AnzeigeStand:
    """Ob das Display dunkel ist, wie der Schlafwächter es meldet (GET /wach?dunkel=0|1)."""

    def __init__(self) -> None:
        self.dunkel: bool | None = None
        self.zeit = 0.0
        self.dunkel_seit: float | None = None

    def melden(self, dunkel: bool, jetzt: float) -> None:
        if not dunkel:
            self.dunkel_seit = None
        elif self.dunkel is not True:
            self.dunkel_seit = jetzt  # gerade dunkel geworden
        self.dunkel = dunkel
        self.zeit = jetzt

    def stand(self, jetzt: float) -> bool | None:
        """True dunkel, False an, None unbekannt (nie gemeldet oder zu lange her)."""
        if self.dunkel is None or jetzt - self.zeit >= ANZEIGE_FRIST_S:
            return None
        return self.dunkel

    def seit(self, jetzt: float) -> float | None:
        return self.dunkel_seit if self.stand(jetzt) else None


@dataclass
class Treffer:
    aktion: str
    wort: str
    grund: str = ""  # nur fürs Journal


class Weckwort:
    """Zustand der Weckwort-Auswertung. Kennt weder Vosk noch Uhr noch Netz."""

    def __init__(self, start: int | None = None) -> None:
        self.rezept = Rezept()
        self.anzeige = AnzeigeStand()
        # Der Schlafwächter erkennt am Paar (start, wecken), ob ein neues Wecken dazukam. `start`
        # unterscheidet einen neu gestarteten Dienst (Zähler wieder bei 0) von einem neuen Wecken.
        self.start = start if start is not None else int(time.time() * 1000)
        self.wecken_zaehler = 0
        self.gehoert = 0  # zählt erkannte Wörter, für die Rückmeldung in der Leiste
        self.nachlauf_bis = 0.0
        self.letztes: tuple[str, float] | None = None

    def gesperrt(self, belegt: bool, jetzt: float) -> bool:
        """`belegt`: Elektra, Diktat oder Wiedergabe sind dran. Danach noch NACHLAUF_S."""
        if belegt:
            self.nachlauf_bis = jetzt + NACHLAUF_S
        return belegt or jetzt < self.nachlauf_bis

    def hoert(self, belegt: bool, jetzt: float) -> bool:
        """Soll die Erkennung jetzt Ton bekommen?"""
        return self.rezept.gilt(jetzt, self.anzeige.seit(jetzt)) and not self.gesperrt(
            belegt, jetzt
        )

    def wort(self, text: str, belegt: bool, jetzt: float) -> Treffer | None:
        """Ein Erkennungsergebnis. Gibt zurück, was zu tun ist, oder None, wenn nichts."""
        wort, verworfen = wort_lesen(text)
        if verworfen:
            log.info("Verworfen, %s", verworfen)
        if wort is None:
            return None
        gesperrt = self.gesperrt(belegt, jetzt)
        offen = self.rezept.gilt(jetzt, self.anzeige.seit(jetzt))
        if not offen or gesperrt:
            return None
        if (
            self.letztes
            and self.letztes[0] == wort
            and jetzt - self.letztes[1] < ENTPRELL_S
        ):
            return None
        self.letztes = (wort, jetzt)
        self.gehoert += 1
        dunkel = self.anzeige.stand(jetzt)
        aktion = entscheide(wort, offen, gesperrt, dunkel)
        if aktion == WECKEN:
            self.wecken_zaehler += 1
        grund = (
            "Display dunkel"
            if dunkel
            else "Zustand des Displays unbekannt, nicht geblättert"
            if dunkel is None
            else ""
        )
        return Treffer(aktion, wort, grund)


# --- Vosk --------------------------------------------------------------------------------
class VoskErkenner:
    """Dünne Hülle um vosk.KaldiRecognizer; nicht Teil der Tests (braucht Paket und Modell)."""

    def __init__(self, vosk, modell, rate: int) -> None:
        self.erkenner = vosk.KaldiRecognizer(modell, rate, GRAMMATIK)

    def ton(self, daten: bytes) -> str | None:
        """Das Ergebnis, wenn eine Äußerung zu Ende ist, sonst None."""
        if self.erkenner.AcceptWaveform(daten):
            return json.loads(self.erkenner.Result()).get("text", "")
        return None

    def zuruecksetzen(self) -> None:
        self.erkenner.Reset()


def erkenner_laden(
    modell_pfad: Path, rate: int, importieren=None
) -> tuple[VoskErkenner | None, str | None]:
    """Lädt Vosk und das Modell. Gibt (Erkenner, None) oder (None, Fehlertext) zurück.

    Weder ein fehlendes Paket noch ein fehlendes Modell bricht den Dienst ab; der Fehler kommt
    als ein Satz zurück, den der Aufrufer einmal ins Journal schreibt.
    """
    try:
        vosk = importieren("vosk") if importieren else __import__("vosk")
    except ImportError as fehler:
        return None, (
            f"Paket vosk fehlt ({fehler}); Einrichtung: docs/stimme-und-geste.md, Abschnitt Weckwort"
        )
    if not modell_pfad.is_dir():
        return None, (
            f"Modell fehlt unter {modell_pfad}; Einrichtung: docs/stimme-und-geste.md, Abschnitt Weckwort"
        )
    try:
        vosk.SetLogLevel(-1)
        modell = vosk.Model(str(modell_pfad))
        return VoskErkenner(vosk, modell, rate), None
    except Exception as fehler:  # noqa: BLE001 - Vosk wirft eine nackte Exception bei kaputtem Modell
        return None, f"Modell unter {modell_pfad} nicht ladbar: {fehler}"


class Lauscher:
    """Nimmt Rahmen vom Mikrofon-Faden an und lässt Vosk in einem eigenen Faden arbeiten.

    `rahmen` kehrt sofort zurück, damit die Mikrofon-Schleife nie auf die Erkennung wartet. Hört
    die Erkennung eine Weile nicht zu (kein Rezept, Elektra dran), setzt sie sich zurück, damit kein
    Rest von vorhin ein Wort ergibt.
    """

    def __init__(self, erkenner, bei_text) -> None:
        self.erkenner = erkenner
        self.bei_text = bei_text  # (text) -> None, läuft im Faden der Erkennung
        self.schlange: queue.Queue = queue.Queue(maxsize=WARTESCHLANGE)
        self.bereit = True
        self.hoerte = False
        self.verworfen = 0
        self.verworfen_gemeldet = float("-inf")  # noch nie gemeldet

    def rahmen(self, ton: bytes, hoeren: bool) -> None:
        if not self.bereit:
            return
        if not hoeren:
            if self.hoerte:
                self.hoerte = False
                self._geben(None)
            return
        self.hoerte = True
        self._geben(ton)

    def _geben(self, element) -> None:
        try:
            self.schlange.put_nowait(element)
        except queue.Full:
            self.verworfen += 1
            jetzt = time.monotonic()
            if jetzt - self.verworfen_gemeldet > 60:
                self.verworfen_gemeldet = jetzt
                log.warning(
                    "Erkennung kommt nicht mit, %d Rahmen verworfen", self.verworfen
                )

    def schritt(self) -> bool:
        """Verarbeitet ein Element der Schlange. False, wenn die Erkennung ausgefallen ist."""
        element = self.schlange.get()
        try:
            if element is None:
                self.erkenner.zuruecksetzen()
            else:
                text = self.erkenner.ton(element)
                if text:
                    self.bei_text(text)
        except Exception:
            log.exception(
                "Erkennung ausgefallen, das Weckwort ist aus bis zum Neustart"
            )
            self.bereit = False
            return False
        return True

    def lauf(self) -> None:
        while self.schritt():
            pass
