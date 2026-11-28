"""Termine sperren, wenn Besuch kommt (kuechen-display#82).

Gesperrt wird am Display durch langes Drücken auf die Terminkarte, entsperrt nur übers Handy:
Der Helfer `input_boolean.termine_privat` in Home Assistant ist die einzige Wahrheit ("on" =
gesperrt). Der Dienst liest ihn alle drei Sekunden (und bei jedem Terminabruf) und setzt ihn beim Sperren.

Wichtig ist, was *nicht* geschieht: Solange gesperrt ist, verlässt keine Terminangabe den
Dienst, weder Titel noch Zeiten noch eine Anzahl. Die Seite bekommt dann nur `gesperrt: true`
und wirft ihren Stand weg. Alle Wege zur Seite laufen deshalb durch `veroeffentlichen`.
"""

from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger("dienst")

HINWEIS_FEHLER = "Sperren hat nicht geklappt"


def neuer_stand(zustand: str | None, bisher: bool) -> bool:
    """„on“ sperrt, nur ein ausdrückliches „off“ hebt auf. Alles andere („unknown“, „unavailable“,
    ein Helfer, den Home Assistant nicht kennt) lässt den Stand, wie er ist: Ein gesperrtes Display
    bleibt gesperrt (nach einem Neustart von Home Assistant fehlt der Helfer kurz), ein freies bleibt
    frei, ohne Fehler auf der Seite."""
    if zustand == "on":
        return True
    if zustand == "off":
        return False
    return bisher


class Sperre:
    def __init__(self, entitaet: str) -> None:
        self.entitaet = entitaet.strip()
        self.gesperrt = False
        self._lock = threading.Lock()
        # Zählt jede Änderung. Ein Lesen, das vor einem Sperren begann, darf dessen Ergebnis
        # nicht mehr überschreiben (sonst entsperrt ein veralteter Zustand „off“ das Display).
        self._lauf = 0
        # Nur für das Protokoll: Beim schnellen Lesen alle paar Sekunden soll ein Ausfall von
        # Home Assistant einmal ins Journal, nicht zwanzigmal je Minute.
        self._lesefehler = False

    @property
    def aktiv(self) -> bool:
        return bool(self.entitaet)

    def ereignis(self) -> dict:
        """Was die Seite im Ereignis „termine“ bekommt, solange gesperrt ist: nichts außer dem Schloss."""
        return {"gesperrt": True, "sperrbar": True}

    def abgleichen(self, ha) -> bool:
        """Liest den Helfer und übernimmt ihn. Antwortet Home Assistant nicht, bleibt der letzte Stand
        (ein gesperrtes Display bleibt gesperrt); „unknown“, „unavailable“ und ein fehlender
        Helfer lassen den Stand ebenfalls. Gibt zurück, ob sich etwas geändert hat."""
        if not self.aktiv:
            return False
        with self._lock:
            lauf = self._lauf
        try:
            zustand = ha.zustand(self.entitaet)
        except (OSError, ValueError) as fehler:
            if not self._lesefehler:
                log.warning(
                    "Sperre: %s nicht lesbar, Stand bleibt: %s", self.entitaet, fehler
                )
            self._lesefehler = True
            return False
        if self._lesefehler:
            log.info("Sperre: %s wieder lesbar", self.entitaet)
        self._lesefehler = False
        with self._lock:
            neu = neuer_stand(zustand, self.gesperrt)
            if lauf != self._lauf or neu == self.gesperrt:
                return False
            self.gesperrt = neu
            self._lauf += 1
        log.info("Sperre: Termine %s (vom Handy)", "gesperrt" if neu else "wieder frei")
        return True

    def beobachten(
        self, ha, wecken, takt_s, warten=time.sleep, weiter=lambda: True
    ) -> None:
        """Fragt den Helfer alle `takt_s` Sekunden ab (eine leichte Zustandsabfrage, kein Kalender).
        Ändert sich der Stand, ruft sie `wecken()` auf, und die Terminschleife läuft sofort, statt
        bis zu zwei Minuten zu warten. Gelesen und übernommen wird über `abgleichen`, also mit
        denselben Regeln und demselben Zähler wie im Terminzyklus. Ohne Entität passiert nichts."""
        if not self.aktiv:
            return
        gemeldet = False
        while weiter():
            try:
                if self.abgleichen(ha):
                    wecken()
                if gemeldet:
                    log.info("Sperre: Abgleich läuft wieder")
                gemeldet = False
            except Exception:
                # Der Wächter darf nicht sterben; der Terminzyklus liest weiter. Der Traceback
                # kommt einmal ins Journal, nicht alle drei Sekunden, bis es wieder geht (#109).
                if not gemeldet:
                    log.exception("Sperre: Abgleich fehlgeschlagen")
                gemeldet = True
            warten(takt_s)

    def sperren(self, ha, ablage: dict, senden, hinweis) -> bool:
        """Lange gedrückt: Helfer in Home Assistant einschalten. Erst wenn das klappt, gilt die Sperre,
        und die Seite bekommt sie sofort. Sonst bleibt alles offen, und die Seite bekommt einen Hinweis."""
        if not self.aktiv:
            return False
        try:
            ha.dienst("input_boolean", "turn_on", {"entity_id": self.entitaet})
        except (OSError, ValueError) as fehler:
            log.warning("Sperre: %s nicht gesetzt: %s", self.entitaet, fehler)
            hinweis(HINWEIS_FEHLER)
            return False
        with self._lock:
            self.gesperrt = True
            self._lauf += 1
            ablage["termine"] = self.ereignis()
            senden("termine", self.ereignis())
        log.info("Sperre: Termine gesperrt (am Display)")
        return True

    def veroeffentlichen(self, karte: dict, ablage: dict, senden) -> bool:
        """Termine an die Seite und in den Stand für neue Seiten, aber nur, wenn nicht gesperrt ist.
        Gesperrt: die Karte wird verworfen, die Seite bekommt das Schloss."""
        with self._lock:
            if self.gesperrt:
                ablage["termine"] = self.ereignis()
                senden("termine", self.ereignis())
                return False
            karte = {**karte, "gesperrt": False, "sperrbar": self.aktiv}
            ablage["termine"] = karte
            senden("termine", karte)
            return True

    def schloss_zeigen(self, ablage: dict, senden) -> None:
        """Gesperrt, kein Abruf nötig: nur sicherstellen, dass die Seite das Schloss hat."""
        with self._lock:
            if self.gesperrt and ablage.get("termine") != self.ereignis():
                ablage["termine"] = self.ereignis()
                senden("termine", self.ereignis())

    def zyklus(self, ha, holen, ablage: dict, senden) -> dict | None:
        """Ein Durchlauf der Terminschleife: Helfer lesen, dann entweder das Schloss halten (ohne
        irgendetwas abzurufen) oder `holen()` aufrufen und veröffentlichen. Gibt die abgerufene Karte
        zurück (für das Journal), None bei Sperre oder Fehler."""
        self.abgleichen(ha)
        if self.gesperrt:
            self.schloss_zeigen(ablage, senden)
            return None
        karte = holen()
        if karte is not None:
            self.veroeffentlichen(karte, ablage, senden)
        return karte
