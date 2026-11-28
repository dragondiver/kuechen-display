import http.client
import io
import json
import urllib.error
from datetime import datetime

import pytest
from hass import HassFehler, HomeAssistant, wetter_karte


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


@pytest.mark.parametrize(
    "fehler",
    [
        TimeoutError("zu langsam"),
        urllib.error.HTTPError("/x", 503, "Unavailable", {}, io.BytesIO()),
        json.JSONDecodeError("kaputt", "", 0),
    ],
)
def test_warnsensor_scheitert_wetter_kommt_trotzdem(fehler, caplog):
    class Kaputt(FakeHA):
        def _anfrage(self, methode, pfad, body=None):
            if pfad == "/api/states/sensor.warnung":
                raise fehler
            return super()._anfrage(methode, pfad, body)

    karte = wetter_karte(
        Kaputt(ANTWORTEN), "weather.kueche", "sensor.aussen", "K", "sensor.warnung"
    )
    assert karte["warnung"] is None
    assert (karte["zustand"], karte["temperatur"]) == ("Regen", "7°")
    assert "sensor.warnung" in caplog.text


class Urlopen:
    """Ersetzt urllib.request.urlopen: liefert Bytes oder wirft."""

    def __init__(self, antwort):
        self.antwort = antwort

    def __call__(self, req, timeout=None):
        if isinstance(self.antwort, Exception):
            raise self.antwort
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.antwort


def ha_mit_antwort(monkeypatch, antwort):
    monkeypatch.setattr("hass.urllib.request.urlopen", Urlopen(antwort))
    return HomeAssistant("http://ha.test:8123", "geheim")


@pytest.mark.parametrize(
    "fehler",
    [http.client.IncompleteRead(b"{", 10), http.client.BadStatusLine("")],
)
def test_abgebrochene_antwort_wird_zur_hass_fehler(monkeypatch, fehler):
    # HTTPException ist keine OSError; die Aufrufer fangen aber (OSError, ValueError) (#109)
    ha = ha_mit_antwort(monkeypatch, fehler)
    with pytest.raises(HassFehler):
        ha.zustand("input_boolean.x")


@pytest.mark.parametrize("roh", [b"[]", b"1", b'"x"'])
def test_antwort_ohne_objekt_wird_zur_hass_fehler(monkeypatch, roh):
    ha = ha_mit_antwort(monkeypatch, roh)
    with pytest.raises(HassFehler):
        ha.zustand("input_boolean.x")
    with pytest.raises(HassFehler):
        ha.vorhersage("weather.kueche")
    with pytest.raises(HassFehler):
        ha.termine(["calendar.a"], datetime(2026, 1, 1), datetime(2026, 1, 8))


def test_geschachtelte_antwort_ohne_objekt_wird_zur_hass_fehler(monkeypatch):
    ha = ha_mit_antwort(monkeypatch, b'{"service_response": {"calendar.a": []}}')
    with pytest.raises(HassFehler):
        ha.termine(["calendar.a"], datetime(2026, 1, 1), datetime(2026, 1, 8))


def test_abruf_faengt_abgebrochene_antwort_und_meldet_einmal(monkeypatch, caplog):
    import dienst

    ha = ha_mit_antwort(monkeypatch, http.client.IncompleteRead(b"", 5))
    abruf = dienst.Abruf("Termine")
    with caplog.at_level("INFO", logger="dienst"):
        assert abruf(lambda: ha.zustand("x")) is None
        assert abruf(lambda: ha.zustand("x")) is None
    assert len([r for r in caplog.records if "antwortet nicht" in r.message]) == 1


def test_abruf_faengt_jede_ausnahme_und_gibt_none(caplog):
    import dienst

    def kaputt():
        raise AttributeError("'list' object has no attribute 'get'")

    abruf = dienst.Abruf("Termine")
    with caplog.at_level("INFO", logger="dienst"):
        assert abruf(kaputt) is None


def test_abruf_schreibt_dauerhaften_fehler_einmal_mit_traceback(caplog):
    import dienst

    def kaputt():
        raise TypeError("kaputt")

    abruf = dienst.Abruf("Termine")
    with caplog.at_level("INFO", logger="dienst"):
        for _ in range(3):
            assert abruf(kaputt) is None
    mit_traceback = [r for r in caplog.records if r.exc_info]
    assert len(mit_traceback) == 1
    assert "Termine" in mit_traceback[0].message


def test_abruf_meldet_nach_fehler_wieder_da_und_liefert_ergebnis(caplog):
    import dienst

    def kaputt():
        raise TypeError("kaputt")

    abruf = dienst.Abruf("Termine")
    with caplog.at_level("INFO", logger="dienst"):
        assert abruf(kaputt) is None
        assert abruf(lambda: {"ok": 1}) == {"ok": 1}
    assert len([r for r in caplog.records if "antwortet wieder" in r.message]) == 1
    assert abruf.gestoert is False


@pytest.mark.parametrize(
    "antwort",
    [
        {"state": "on", "attributes": ["kein", "Objekt"]},
        {"state": "on", "attributes": {"friendly_name": "A"}},
    ],
)
def test_abruf_mit_falsch_geformter_kalenderantwort_bleibt_im_abruf(antwort, caplog):
    import dienst
    from hass import termine_karte

    ereignisse = [
        {"service_response": {"calendar.a": {"events": "kein Array"}}},
        {"service_response": {"calendar.a": {"events": ["kein Objekt"]}}},
    ]
    for events in ereignisse:
        ha = FakeHA(
            {
                "/api/states/calendar.a": antwort,
                "/api/services/calendar/get_events?return_response": events,
            }
        )
        abruf = dienst.Abruf("Termine")
        with caplog.at_level("INFO", logger="dienst"):
            assert (
                abruf(
                    lambda ha=ha: termine_karte(
                        ha, ["calendar.a"], datetime(2026, 1, 1)
                    )
                )
                is None
            )
        assert abruf.gestoert
