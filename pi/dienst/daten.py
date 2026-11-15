"""Aufbereitung der Daten für den Ruhebildschirm (kuechen-display#15).

Reine Funktionen ohne Netz: Sie bekommen, was Home Assistant liefert, und geben zurück,
was die Kiosk-Seite anzeigt. Geholt wird in hass.py, verschickt in dienst.py.
Tests: test_daten.py. Anleitung: docs/datenweg.md
"""

from __future__ import annotations

# Wetterlage aus Home Assistant → Text auf der Wetterkarte und eines der sechs Bilder
# (docs/entwuerfe/wetter/flach). Die Liste der Lagen stammt aus der HA-Dokumentation
# zur weather-Entität.
LAGEN: dict[str, tuple[str, str]] = {
    "sunny": ("Sonnig", "sonnig"),
    "clear-night": ("Klar", "nacht"),
    "partlycloudy": ("Wolkig", "wolkig"),
    "cloudy": ("Bedeckt", "gedaempft"),
    "fog": ("Nebel", "gedaempft"),
    "windy": ("Windig", "wolkig"),
    "windy-variant": ("Windig", "gedaempft"),
    "rainy": ("Regen", "regen"),
    "pouring": ("Starker Regen", "regen"),
    "lightning": ("Gewitter", "regen"),
    "lightning-rainy": ("Gewitter", "regen"),
    "hail": ("Hagel", "regen"),
    "snowy": ("Schnee", "schnee"),
    "snowy-rainy": ("Schneeregen", "schnee"),
    "exceptional": ("Unwetter", "gedaempft"),
}
# Bilder ohne Niederschlag werden nachts durch das Nachtbild ersetzt. Regen und Schnee
# bleiben, weil es davon kein Nachtbild gibt.
TROCKEN = {"sonnig", "wolkig", "gedaempft"}
RUECKFALL_BILD = "gedaempft"


def zahl(wert) -> float | None:
    """Zustände kommen aus HA als Text; 'unknown' und 'unavailable' sind keine Zahl."""
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def grad(wert) -> str:
    z = zahl(wert)
    if z is None:
        return "–"
    # Echtes Minuszeichen statt Bindestrich; round(-0.4) ist 0, also kein „−0°“.
    return f"{round(z)}°".replace("-", "−")


def wetter_aufbereiten(
    wetter: dict | None,
    vorhersage: list[dict],
    *,
    temperatur=None,
    sonne: str | None = None,
    ort: str = "",
    stand: int = 0,
) -> dict:
    """Macht aus der weather-Entität und der Tagesvorhersage die Wetterkarte.

    wetter      Antwort von /api/states/<weather-Entität> oder None, wenn HA sie nicht kennt
    vorhersage  Liste aus weather.get_forecasts (daily); [0] ist heute, [1] morgen
    temperatur  Zustand eines eigenen Temperatursensors; ohne ihn gilt die der Entität
    sonne       Zustand von sun.sun ("above_horizon" / "below_horizon")
    stand       Zeit des Abrufs als Unix-Sekunden; die Seite erkennt daran alte Daten

    Eine unbekannte Wetterlage wird nicht verschluckt: Sie steht im Klartext auf der Karte,
    bekommt das Rückfallbild und "unbekannt": True, damit der Dienst sie ins Journal schreibt.
    """
    lage = (wetter or {}).get("state")
    attribute = (wetter or {}).get("attributes", {})
    nacht = sonne == "below_horizon"

    if lage in LAGEN:
        text, bild = LAGEN[lage]
        unbekannt = False
    elif lage in (None, "unknown", "unavailable"):
        text, bild, unbekannt = "Keine Wetterdaten", RUECKFALL_BILD, True
    else:
        text, bild, unbekannt = str(lage), RUECKFALL_BILD, True
    if nacht and bild in TROCKEN:
        bild = "nacht"

    temp = zahl(temperatur)
    if temp is None:
        temp = zahl(attribute.get("temperature"))

    # Zweite Zeile: der Tiefstwert aus der Tagesvorhersage, tags wie nachts (Festlegung
    # 15.11.2026 in #15). Fehlt die Vorhersage, bleibt die Zeile leer.
    zeile = ""
    if vorhersage and zahl(vorhersage[0].get("templow")) is not None:
        zeile = f"Nacht {grad(vorhersage[0]['templow'])}"

    return {
        "ort": ort,
        "temperatur": grad(temp),
        "zustand": text,
        "zeile": zeile,
        "bild": bild,
        "unbekannt": unbekannt,
        "stand": stand,
    }
