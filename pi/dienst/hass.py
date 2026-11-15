"""Kleiner Home-Assistant-Client für den Küchen-Dienst (kuechen-display#15).

Nur lesen, nur was der Ruhebildschirm braucht. Ohne Fremdpakete (urllib), damit das venv
auf dem Pi bei `websockets` bleibt. Die Antworten bereitet daten.py auf.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from daten import wetter_aufbereiten


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


def wetter_karte(ha, entitaet: str, sensor: str | None, ort: str) -> dict:
    """Vier Abrufe, eine Wetterkarte. Netzfehler gehen als Ausnahme an den Aufrufer."""
    wetter = ha.entitaet(entitaet)
    return wetter_aufbereiten(
        wetter,
        ha.vorhersage(entitaet) if wetter else [],
        temperatur=ha.zustand(sensor) if sensor else None,
        sonne=ha.zustand("sun.sun"),
        ort=ort,
        stand=int(time.time()),
    )
