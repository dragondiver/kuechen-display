import io
import json
import urllib.error

import pytest
from hass import HomeAssistant, wetter_karte


class FakeHA(HomeAssistant):
    """HomeAssistant ohne Netz: beantwortet Pfade aus einer Tabelle und merkt sich die Anfragen."""

    def __init__(self, antworten):
        super().__init__("http://ha.test:8123/", "geheim")
        self.antworten = antworten
        self.anfragen = []

    def _anfrage(self, methode, pfad, body=None):
        self.anfragen.append((methode, pfad, body))
        if pfad not in self.antworten:
            raise urllib.error.HTTPError(pfad, 404, "Not Found", {}, io.BytesIO())
        return json.loads(json.dumps(self.antworten[pfad]))


ANTWORTEN = {
    "/api/states/weather.kueche": {
        "state": "rainy",
        "attributes": {"temperature": 8.2},
    },
    "/api/states/sensor.aussen": {"state": "7.4"},
    "/api/states/sun.sun": {"state": "above_horizon"},
    "/api/services/weather/get_forecasts?return_response": {
        "service_response": {
            "weather.kueche": {"forecast": [{"temperature": 9.0, "templow": 2.6}]}
        }
    },
}


def test_wetter_karte_fragt_entitaet_vorhersage_sensor_und_sonne():
    ha = FakeHA(ANTWORTEN)
    karte = wetter_karte(ha, "weather.kueche", "sensor.aussen", "Kornwestheim")
    assert (karte["temperatur"], karte["zustand"], karte["zeile"], karte["bild"]) == (
        "7°",
        "Regen",
        "Nacht 3°",
        "regen",
    )
    assert karte["stand"] > 0
    assert (
        "POST",
        "/api/services/weather/get_forecasts?return_response",
        {"entity_id": "weather.kueche", "type": "daily"},
    ) in ha.anfragen


def test_unbekannte_entitaet_gibt_keine_wetterdaten_statt_absturz():
    ha = FakeHA({"/api/states/sun.sun": {"state": "above_horizon"}})
    karte = wetter_karte(ha, "weather.gibt_es_nicht", None, "Kornwestheim")
    assert (karte["zustand"], karte["unbekannt"]) == ("Keine Wetterdaten", True)
    # Ohne Entität wird die Vorhersage gar nicht erst abgefragt.
    assert not any(p.startswith("/api/services") for _, p, _ in ha.anfragen)


def test_andere_fehler_gehen_an_den_aufrufer():
    class Kaputt(HomeAssistant):
        def _anfrage(self, methode, pfad, body=None):
            raise urllib.error.HTTPError(pfad, 401, "Unauthorized", {}, io.BytesIO())

    with pytest.raises(urllib.error.HTTPError):
        wetter_karte(Kaputt("http://ha.test", "falsch"), "weather.kueche", None, "")


def test_vorhersage_ohne_eintrag_ist_leer():
    ha = FakeHA(
        {
            "/api/services/weather/get_forecasts?return_response": {
                "service_response": {}
            }
        }
    )
    assert ha.vorhersage("weather.kueche") == []


def test_wetter_karte_schickt_die_warnung_mit():
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    ende = (datetime.now(ZoneInfo("Europe/Berlin")) + timedelta(hours=2)).replace(
        minute=0, second=0, microsecond=0
    )
    antworten = {
        **ANTWORTEN,
        "/api/states/sensor.warnung": {
            "state": "2",
            "attributes": {
                "warning_count": 1,
                "warning_1_name": "Sturmböen",
                "warning_1_level": 2,
                "warning_1_end": ende.isoformat(),
                "warning_1_color": "#ff9900",
            },
        },
    }
    ha = FakeHA(antworten)
    karte = wetter_karte(ha, "weather.kueche", "sensor.aussen", "K", "sensor.warnung")
    assert karte["warnung"] == {
        "text": f"Sturmböen bis {ende.hour} Uhr",
        "farbe": "#ff9900",
        "mehr": 0,
    }


def test_wetter_karte_ohne_warnsensor_oder_unbekanntem_sensor_keine_warnung():
    ha = FakeHA(ANTWORTEN)
    assert wetter_karte(ha, "weather.kueche", None, "K")["warnung"] is None
    assert not any("warnung" in a[1] for a in ha.anfragen)
    karte = wetter_karte(ha, "weather.kueche", None, "K", "sensor.gibt_es_nicht")
    assert karte["warnung"] is None and karte["zustand"] == "Regen"
