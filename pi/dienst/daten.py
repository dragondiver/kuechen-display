"""Aufbereitung der Daten für den Ruhebildschirm (kuechen-display#15).

Reine Funktionen ohne Netz: Sie bekommen, was Home Assistant liefert, und geben zurück,
was die Kiosk-Seite anzeigt. Geholt wird in hass.py, verschickt in dienst.py.
Tests: test_daten.py. Anleitung: docs/datenweg.md
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

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
    warnung: dict | None = None,
) -> dict:
    """Macht aus der weather-Entität und der Tagesvorhersage die Wetterkarte.

    wetter      Antwort von /api/states/<weather-Entität> oder None, wenn HA sie nicht kennt
    vorhersage  Liste aus weather.get_forecasts (daily); [0] ist heute, [1] morgen
    temperatur  Zustand eines eigenen Temperatursensors; ohne ihn gilt die der Entität
    sonne       Zustand von sun.sun ("above_horizon" / "below_horizon")
    stand       Zeit des Abrufs als Unix-Sekunden; die Seite erkennt daran alte Daten
    warnung     Ergebnis von warnung_aufbereiten oder None (dann keine Zeile)

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
        "warnung": warnung,
    }


# --- Wetterwarnung --------------------------------------------------------------
# Festlegung 18.11.2026 in #37: ab Stufe 2 (wie beim Sprechen), eine Zeile unten in der
# Wetterkarte. Quelle ist der Sensor "aktuelle Warnstufe" der Integration dwd_weather_warnings.

WARNUNG_AB_STUFE = 2
WARNUNG_MAX = 20  # Obergrenze für warning_N, falls warning_count Unsinn liefert
# Rückfall, wenn die Farbe fehlt oder kein Hex ist: die DWD-Farben der Stufen 2 bis 4.
WARNUNG_FARBEN = {2: "#ff9900", 3: "#ff0000", 4: "#a50066"}
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def _warn_ende(wert, zone) -> datetime | None:
    try:
        ende = datetime.fromisoformat(str(wert))
    except ValueError:
        return None
    return ende.replace(tzinfo=zone) if ende.tzinfo is None else ende.astimezone(zone)


def _bis_text(ende: datetime, jetzt: datetime) -> str:
    uhr = (
        f"{ende.hour} Uhr" if ende.minute == 0 else f"{ende.hour}:{ende.minute:02d} Uhr"
    )
    tage = (ende.date() - jetzt.date()).days
    if tage <= 0:
        return f"bis {uhr}"
    if tage == 1:
        return f"bis morgen {uhr}"
    return f"bis {WOCHENTAGE[ende.weekday()][:2]} {uhr}"


def warnung_aufbereiten(sensor: dict | None, jetzt: datetime) -> dict | None:
    """Wählt aus dem Sensor "aktuelle Warnstufe" die eine Warnung für die Wetterkarte.

    sensor  Antwort von /api/states/<Entität> oder None; Attribute warning_count und je
            Warnung warning_N_name, _level, _end, _color (N ab 1)
    jetzt   lokale Zeit mit Zeitzone

    Die DWD liefert gleichzeitige Warnungen in wechselnder Reihenfolge. Es gewinnt die
    höchste Stufe, bei gleicher Stufe das früheste Ende. Vorbei gegangene Warnungen und
    Stufe 1 zählen nicht. Gibt es mehrere, hängt "mehr" die Zahl der übrigen an.
    Ergebnis {"text", "farbe", "mehr"} oder None, dann steht keine Zeile da.
    """
    if not sensor or sensor.get("state") == "unavailable":
        return None
    attribute = sensor.get("attributes") or {}
    anzahl = zahl(attribute.get("warning_count"))
    if anzahl is None:
        return None
    aktiv = []
    for n in range(1, min(int(anzahl), WARNUNG_MAX) + 1):
        stufe = zahl(attribute.get(f"warning_{n}_level"))
        name = str(attribute.get(f"warning_{n}_name") or "").strip()
        ende = _warn_ende(attribute.get(f"warning_{n}_end"), jetzt.tzinfo)
        if stufe is None or not name or ende is None:
            continue
        if stufe < WARNUNG_AB_STUFE or ende <= jetzt:
            continue
        farbe = str(attribute.get(f"warning_{n}_color") or "")
        if not _HEX.fullmatch(farbe):
            farbe = WARNUNG_FARBEN.get(int(stufe), WARNUNG_FARBEN[4])
        aktiv.append((-stufe, ende, n, name, farbe))
    if not aktiv:
        return None
    aktiv.sort()
    _, ende, _, name, farbe = aktiv[0]
    return {
        "text": f"{name} {_bis_text(ende, jetzt)}",
        "farbe": farbe,
        "mehr": len(aktiv) - 1,
    }


# --- Termine ------------------------------------------------------------------
# Festlegungen in #15 (18.10. und 15.11.2026): links „Noch heute“, dahinter Morgen mit
# Uhrzeit von–bis und die Woche ab heute. Ganztägige Termine stehen oben, statt der
# Uhrzeit steht „ganztägig“. Der Punkt neben dem Termin zeigt den Kalender.

# Farbklasse des Punkts je Kalender, in der Reihenfolge der Einstellung KALENDER.
FARBEN = ("p1", "p2")
FARBE_SONST = "pa"
GANZTAEGIG = "ganztägig"
WOCHENTAGE = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)


def _zeitpunkt(wert: str, zone) -> tuple[datetime, bool]:
    """HA liefert ganztägige Termine als Datum ('2026-11-15'), alle anderen mit Uhrzeit
    und Zeitzone. Gibt den Zeitpunkt in der lokalen Zone und 'ganztägig' zurück."""
    if len(wert) == 10:
        return datetime.combine(date.fromisoformat(wert), time(), tzinfo=zone), True
    punkt = datetime.fromisoformat(wert)
    if punkt.tzinfo is None:
        punkt = punkt.replace(tzinfo=zone)
    return punkt.astimezone(zone), False


def _uhr(punkt: datetime) -> str:
    return punkt.strftime("%H:%M")


def termine_aufbereiten(
    antwort: dict[str, list[dict]],
    kalender: list[str],
    namen: dict[str, str],
    jetzt: datetime,
    tage: int = 7,
) -> dict:
    """Macht aus der Antwort von calendar.get_events die Listen der Kiosk-Seite.

    antwort   {Entität: [Termin, …]} wie in service_response, Termin mit start, end, summary
    kalender  die eingestellten Entitäten; ihre Reihenfolge bestimmt die Farbe des Punkts
    namen     {Entität: Anzeigename}; fehlt einer, gilt der Teil hinter „calendar.“
    jetzt     lokale Zeit mit Zeitzone (ZoneInfo), danach richten sich die Tage

    Jeder Eintrag hat "bis" (Unix-Sekunden): Die Seite blendet damit vorbei gegangene Termine
    von selbst aus, ohne auf den nächsten Abruf zu warten. "heute" enthält nur, was noch nicht
    vorbei ist; ganztägige Termine bleiben bis Mitternacht.
    """
    zone = jetzt.tzinfo
    heute = jetzt.date()
    tagesanfang = [
        datetime.combine(heute + timedelta(days=n), time(), tzinfo=zone)
        for n in range(tage + 1)
    ]

    termine = []
    for entitaet in kalender:
        name = namen.get(entitaet) or entitaet.removeprefix("calendar.").capitalize()
        rang = kalender.index(entitaet)
        farbe = FARBEN[rang] if rang < len(FARBEN) else FARBE_SONST
        for t in antwort.get(entitaet) or []:
            try:
                start, ganz = _zeitpunkt(str(t["start"]), zone)
                ende, _ = _zeitpunkt(str(t.get("end") or t["start"]), zone)
            except (KeyError, ValueError):
                continue
            termine.append(
                {
                    "start": start,
                    "ende": max(ende, start),
                    "ganz": ganz,
                    "titel": str(t.get("summary") or "").strip() or "(ohne Titel)",
                    "kalender": name,
                    "farbe": farbe,
                }
            )
    termine.sort(key=lambda t: (not t["ganz"], t["start"], t["titel"]))

    def tag(n: int, spanne: bool) -> list[dict]:
        von, bis = tagesanfang[n], tagesanfang[n + 1]
        liste = []
        for t in termine:
            # Ein Termin gehört zu jedem Tag, den er berührt; ein Termin ohne Dauer zu
            # dem Tag, an dem er beginnt.
            if not (t["start"] < bis and (t["ende"] > von or t["start"] >= von)):
                continue
            ende = min(t["ende"], bis) if t["ganz"] else t["ende"]
            if t["ganz"]:
                zeit = GANZTAEGIG
            elif t["start"] < von:
                zeit = f"bis {_uhr(t['ende'])}" if t["ende"] < bis else GANZTAEGIG
            elif spanne and t["ende"] > t["start"]:
                zeit = f"{_uhr(t['start'])}–{_uhr(t['ende'])}"
            else:
                zeit = _uhr(t["start"])
            liste.append(
                {
                    "zeit": zeit,
                    "titel": t["titel"],
                    "kalender": t["kalender"],
                    "farbe": t["farbe"],
                    "bis": int(max(ende, t["start"]).timestamp()),
                }
            )
        return liste

    jetzt_s = jetzt.timestamp()
    woche = []
    for n in range(tage):
        datum = heute + timedelta(days=n)
        woche.append(
            {
                "tag": "Heute"
                if n == 0
                else "Morgen"
                if n == 1
                else WOCHENTAGE[datum.weekday()],
                "datum": f"{datum.day}.{datum.month}. · KW {datum.isocalendar().week}",
                "termine": tag(n, spanne=False),
            }
        )
    woche[0]["termine"] = [t for t in woche[0]["termine"] if t["bis"] > jetzt_s]
    return {
        "heute": [t for t in tag(0, spanne=False) if t["bis"] > jetzt_s],
        "morgen": tag(1, spanne=True) if tage > 1 else [],
        "woche": woche,
        "stand": int(jetzt_s),
    }
