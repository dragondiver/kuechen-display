"""Geheimnisse des Küchen-Dienstes (kuechen-display#15).

Quelle ist das 1Password-Environment kuechen-display. Auf dem Pi liegt es als
~/kuechen-display/.env, die Unit lädt es per EnvironmentFile. Die früheren Token-Dateien
unter ~/.config/kuechen-display/ gelten weiter als Rückfall, bis sie abgelöst sind.
"""

from __future__ import annotations

import os
from pathlib import Path


def geheimnis(name: str, datei: Path, umgebung=os.environ) -> str | None:
    """Wert der Umgebungsvariable `name`, sonst der Inhalt von `datei`, sonst None.

    Leere Werte zählen nicht: In 1Password darf ein Name ohne Wert stehen, ohne dass
    der Dienst mit einem leeren Token losläuft.
    """
    wert = (umgebung.get(name) or "").strip()
    if wert:
        return wert
    try:
        return datei.read_text().strip() or None
    except OSError:
        return None
