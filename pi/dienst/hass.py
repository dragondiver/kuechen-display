"""Kleiner Home-Assistant-Client für den Küchen-Dienst (kuechen-display#15).

Nur lesen, nur was der Ruhebildschirm braucht. Ohne Fremdpakete (urllib), damit das venv
auf dem Pi bei `websockets` bleibt. Die Antworten bereitet daten.py auf.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from daten import termine_aufbereiten, warnung_aufbereiten, wetter_aufbereiten

log = logging.getLogger("dienst")


class HomeAssistant:
    def __init__(self, url: str, token: str, timeout_s: float = 10.0) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._timeout = timeout_s

    def _anfrage(self, methode: str, pfad: str, body: dict | None = None):
        req = urllib.request.Request(
            self._url + pfad,
            data=json.dumps(body).encode() if body is not None else None,
            method=methode,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as antwort:
            roh = antwort.read()
        return json.loads(roh) if roh else None

    def entitaet(self, entity_id: str) -> dict | None:
        """Entität samt Attributen; None, wenn HA sie nicht kennt (404)."""
        try:
            return self._anfrage("GET", f"/api/states/{entity_id}")
        except urllib.error.HTTPError as fehler:
            if fehler.code == 404:
                return None
            raise

    def zustand(self, entity_id: str) -> str | None:
        z = self.entitaet(entity_id)
        return None if z is None else z.get("state")

    def vorhersage(self, entity_id: str, art: str = "daily") -> list[dict]:
        """Die Vorhersage gibt es nur über den Dienst weather.get_forecasts mit
        ?return_response, nicht über /api/states."""
        antwort = self._anfrage(
            "POST",
            "/api/services/weather/get_forecasts?return_response",
            {"entity_id": entity_id, "type": art},
        )
        eintrag = (antwort or {}).get("service_response", {}).get(entity_id) or {}
        return eintrag.get("forecast") or []

    def termine(
        self, entitaeten: list[str], von: datetime, bis: datetime
    ) -> dict[str, list[dict]]:
        """Termine aller Kalender in einem Abruf über den Dienst calendar.get_events.
        Ergebnis: {Entität: [Termin, …]}; ein Kalender ohne Termine fehlt oder ist leer."""
        antwort = self._anfrage(
            "POST",
            "/api/services/calendar/get_events?return_response",
            {
                "entity_id": entitaeten,
                "start_date_time": von.isoformat(),
                "end_date_time": bis.isoformat(),
            },
        )
        ergebnis = (antwort or {}).get("service_response") or {}
        return {e: (ergebnis.get(e) or {}).get("events") or [] for e in entitaeten}


def wetter_karte(
    ha,
    entitaet: str,
    sensor: str | None,
    ort: str,
    warnung_sensor: str | None = None,
    zone: ZoneInfo | None = None,
) -> dict:
    """Vier Abrufe, fünf mit Warnsensor, eine Wetterkarte. Netzfehler gehen als Ausnahme an
    den Aufrufer, außer beim Warnsensor: Ist er unbekannt oder nicht lesbar, fehlt nur die Warnzeile."""
    wetter = ha.entitaet(entitaet)
    stand = int(time.time())
    warnung = None
    if warnung_sensor:
        jetzt = datetime.fromtimestamp(stand, zone or ZoneInfo("Europe/Berlin"))
        # Die Warnung ist Beiwerk: Scheitert sie, kommt das Wetter trotzdem.
        try:
            warnung = warnung_aufbereiten(ha.entitaet(warnung_sensor), jetzt)
        except Exception as fehler:  # noqa: BLE001
            log.warning(
                "Wetter: Warnung von %s nicht lesbar: %s", warnung_sensor, fehler
            )
    return wetter_aufbereiten(
        wetter,
        ha.vorhersage(entitaet) if wetter else [],
        temperatur=ha.zustand(sensor) if sensor else None,
        sonne=ha.zustand("sun.sun"),
        ort=ort,
        stand=stand,
        warnung=warnung,
    )


def termine_karte(ha, kalender: list[str], jetzt: datetime, tage: int = 7) -> dict:
    """Termine von heute 0 Uhr bis zum Ende der Woche, dazu die Namen der Kalender.

    Ein Kalender, den HA nicht kennt, wird ausgelassen und steht unter "fehlt", damit der
    Dienst ihn ins Journal schreibt. Netzfehler gehen als Ausnahme an den Aufrufer."""
    namen, da, fehlt = {}, [], []
    for entitaet in kalender:
        zustand = ha.entitaet(entitaet)
        if zustand is None:
            fehlt.append(entitaet)
            continue
        da.append(entitaet)
        namen[entitaet] = (zustand.get("attributes") or {}).get("friendly_name") or ""
    von = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    antwort = ha.termine(da, von, von + timedelta(days=tage)) if da else {}
    karte = termine_aufbereiten(antwort, kalender, namen, jetzt, tage)
    karte["fehlt"] = fehlt
    return karte
