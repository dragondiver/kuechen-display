"""Lautstärke des Küchen-Displays (kuechen-display#99).

Eine Stellung von 0 bis 100 gilt für jeden Weg: den Schieber in der Rückweg-Leiste und den
Bridge-Befehl `lautstaerke` (rundfunk). 0 ist stumm, 1 bis 100 laufen linear auf 35 bis 100 %
PipeWire. Grund (Tischtest 22.11.2026, #18): PipeWire rechnet den Wert kubisch auf den ALSA-Regler
um. Bei 15 % ist es stumm, bei 30 % -31 dB, bei 60 % -13 dB, bei 100 % 0 dB. Unter 35 % gibt es
also nichts Hörbares, und ein linearer Schieber hätte sein erstes Drittel verschenkt.

Der Dienst merkt sich die Stellung in einer Datei und stellt sie beim Start wieder ein.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

log = logging.getLogger("dienst")

MIN_STELLUNG = 0
MAX_STELLUNG = 100
STANDARD = 60  # gilt, wenn nichts oder Unbrauchbares gemerkt ist; entspricht etwa dem Stand vor #99
UNTERGRENZE = 0.35  # PipeWire-Anteil bei Stellung 1 (kleinste hörbare Lautstärke)


def pruefen(wert: object) -> int | None:
    """Stellung als int, wenn `wert` eine ganze Zahl von 0 bis 100 ist, sonst None.

    Keine Zahl (Text, None, bool, nan) und Werte außerhalb des Bereichs gelten als ungültig; ein
    Wert wie 55.0 ist ganzzahlig und wird angenommen, 55.5 nicht.
    """
    if isinstance(wert, bool) or not isinstance(wert, (int, float)):
        return None
    if isinstance(wert, float) and not wert.is_integer():
        return None
    stellung = int(wert)
    if MIN_STELLUNG <= stellung <= MAX_STELLUNG:
        return stellung
    return None


def pipewire_anteil(stellung: int) -> float:
    """PipeWire-Lautstärke (0.0 bis 1.0) zur Stellung: 0 -> 0.0, 1 -> 0.35, 100 -> 1.0, dazwischen linear."""
    if stellung <= MIN_STELLUNG:
        return 0.0
    stellung = min(stellung, MAX_STELLUNG)
    return UNTERGRENZE + (1 - UNTERGRENZE) * (stellung - 1) / (MAX_STELLUNG - 1)


class Lautstaerke:
    """Die gemerkte Stellung, mit Datei. Alle Wege laufen über `setzen`."""

    def __init__(self, datei: Path):
        self.datei = datei
        self.stellung = STANDARD
        self.sperre = threading.Lock()

    def laden(self) -> int:
        """Liest die gemerkte Stellung; fehlt die Datei oder ist sie unlesbar, gilt STANDARD."""
        try:
            text = self.datei.read_text().strip()
            stellung = pruefen(int(text))
        except (OSError, ValueError):
            stellung = None
        if stellung is None:
            log.info("Lautstärke: nichts Brauchbares gemerkt, Stellung %d", STANDARD)
            stellung = STANDARD
        self.stellung = stellung
        return stellung

    def setzen(self, stellung: int) -> None:
        """Merkt sich die Stellung (im Speicher und in der Datei). Ein Schreibfehler stört nicht."""
        self.stellung = stellung
        try:
            self.datei.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.datei.with_name(self.datei.name + ".tmp")
            tmp.write_text(f"{stellung}\n")
            os.replace(tmp, self.datei)
        except OSError as e:
            log.warning("Lautstärke: %s nicht geschrieben: %s", self.datei, e)
