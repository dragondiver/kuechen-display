"""Termine sperren (sperre.py, hass.HomeAssistant.dienst, #82), ohne Netz."""

import json
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from hass import termine_karte
from sperre import HINWEIS_FEHLER, Sperre, als_sperre
from test_hass import FakeHA

HELFER = "input_boolean.termine_privat"
JETZT = datetime(2026, 11, 15, 14, 0, tzinfo=ZoneInfo("Europe/Berlin"))
KALENDER = ["calendar.family"]
GEHEIM = "Zahnarzt Dr. Müller"


def ha_mit(helfer_zustand=None, **extra):
    antworten = {
        "/api/states/calendar.family": {
            "state": "off",
            "attributes": {"friendly_name": "Family"},
        },
        "/api/services/calendar/get_events?return_response": {
            "service_response": {
                "calendar.family": {
                    "events": [
                        {
                            "start": "2026-11-15T16:00:00+01:00",
                            "end": "2026-11-15T17:00:00+01:00",
                            "summary": GEHEIM,
                        },
                        {
                            "start": "2026-11-16T08:00:00+01:00",
                            "end": "2026-11-16T09:00:00+01:00",
                            "summary": GEHEIM,
                        },
                    ]
                }
            }
        },
        "/api/services/input_boolean/turn_on": [],
        **extra,
    }
    if helfer_zustand is not None:
        antworten[f"/api/states/{HELFER}"] = {"state": helfer_zustand}
    return FakeHA(antworten)


class HaKaputt(FakeHA):
    """Home Assistant ist nicht erreichbar."""

    def _anfrage(self, methode, pfad, body=None):
        self.anfragen.append((methode, pfad, body))
        raise urllib.error.URLError("weg")


class Buehne:
    """Sammelt, was an die Seite ginge, und den Stand für neue Seiten."""

    def __init__(self):
        self.ereignisse, self.ablage, self.hinweise = [], {}, []

    def senden(self, art, daten):
        self.ereignisse.append((art, json.loads(json.dumps(daten))))

    def hinweis(self, text):
        self.hinweise.append(text)

    def alles_als_text(self):
        return json.dumps([self.ereignisse, self.ablage], ensure_ascii=False)


def zyklus(sperre, ha, buehne):
    return sperre.zyklus(
        ha,
        lambda: termine_karte(ha, KALENDER, JETZT),
        buehne.ablage,
        buehne.senden,
    )


@pytest.mark.parametrize(
    "zustand,erwartet",
    [
        ("on", True),
        ("off", False),
        ("unknown", False),
        ("unavailable", False),
        (None, False),
    ],
)
def test_helfer_lesen(zustand, erwartet):
    assert als_sperre(zustand) is erwartet


def test_helfer_an_sperrt_beim_abgleich():
    s = Sperre(HELFER)
    assert s.abgleichen(ha_mit("on")) is True
    assert s.gesperrt is True


def test_helfer_aus_entsperrt_beim_abgleich():
    s = Sperre(HELFER)
    s.gesperrt = True
    assert s.abgleichen(ha_mit("off")) is True
    assert s.gesperrt is False


@pytest.mark.parametrize("zustand", ["unknown", "unavailable"])
def test_unbekannt_und_nicht_verfuegbar_gilt_als_frei(zustand):
    s = Sperre(HELFER)
    s.abgleichen(ha_mit(zustand))
    assert s.gesperrt is False


def test_fehlender_helfer_gilt_als_frei_ohne_fehler():
    s = Sperre(HELFER)
    s.abgleichen(ha_mit(None))  # 404 für die Entität
    assert s.gesperrt is False


def test_ha_nicht_erreichbar_behaelt_gesperrt():
    s = Sperre(HELFER)
    s.gesperrt = True
    assert s.abgleichen(HaKaputt({})) is False
    assert s.gesperrt is True


def test_ha_nicht_erreichbar_behaelt_frei():
    s = Sperre(HELFER)
    s.abgleichen(HaKaputt({}))
    assert s.gesperrt is False


def test_leere_entitaet_schaltet_die_sperre_ab():
    s = Sperre("")
    ha = ha_mit("on")
    assert s.aktiv is False
    assert s.abgleichen(ha) is False
    assert s.gesperrt is False
    assert s.sperren(ha, {}, lambda *a: None, lambda t: None) is False
    assert not [a for a in ha.anfragen if "turn_on" in a[1]]


def test_sperren_ruft_turn_on_und_zeigt_das_schloss_sofort():
    s, b, ha = Sperre(HELFER), Buehne(), ha_mit("off")
    assert s.sperren(ha, b.ablage, b.senden, b.hinweis) is True
    assert (
        "POST",
        "/api/services/input_boolean/turn_on",
        {"entity_id": HELFER},
    ) in ha.anfragen
    assert s.gesperrt is True
    assert b.ereignisse == [("termine", {"gesperrt": True, "sperrbar": True})]
    assert b.ablage["termine"] == {"gesperrt": True, "sperrbar": True}
    assert b.hinweise == []


def test_sperren_scheitert_bleibt_frei_und_meldet_hinweis():
    s, b = Sperre(HELFER), Buehne()
    assert s.sperren(HaKaputt({}), b.ablage, b.senden, b.hinweis) is False
    assert s.gesperrt is False
    assert b.ereignisse == []
    assert b.ablage == {}
    assert b.hinweise == [HINWEIS_FEHLER] == ["Sperren hat nicht geklappt"]


def test_sperren_scheitert_mit_http_fehler_von_ha():
    # HA antwortet 401/500: HTTPError ist ein OSError
    s, b = Sperre(HELFER), Buehne()
    ha = FakeHA({})  # turn_on unbekannt: 404
    assert s.sperren(ha, b.ablage, b.senden, b.hinweis) is False
    assert s.gesperrt is False
    assert b.hinweise == [HINWEIS_FEHLER]


def test_frei_geht_die_karte_mit_feldern_an_die_seite():
    s, b, ha = Sperre(HELFER), Buehne(), ha_mit("off")
    karte = zyklus(s, ha, b)
    assert karte is not None
    ((art, daten),) = b.ereignisse
    assert art == "termine"
    assert daten["gesperrt"] is False and daten["sperrbar"] is True
    assert GEHEIM in b.alles_als_text()


def test_gesperrt_verlaesst_keine_terminangabe_den_dienst():
    s, b, ha = Sperre(HELFER), Buehne(), ha_mit("on")
    assert zyklus(s, ha, b) is None
    assert b.ereignisse == [("termine", {"gesperrt": True, "sperrbar": True})]
    text = b.alles_als_text()
    for verboten in (
        GEHEIM,
        "Zahnarzt",
        "heute",
        "morgen",
        "woche",
        "zeit",
        "titel",
        "bis",
    ):
        assert verboten not in text
    # gesperrt wird nicht einmal abgerufen
    assert not [a for a in ha.anfragen if "get_events" in a[1]]


def test_sperren_verwirft_den_stand_fuer_neue_seiten():
    s, b, ha = Sperre(HELFER), Buehne(), ha_mit("off")
    zyklus(s, ha, b)
    assert GEHEIM in b.alles_als_text()
    s.sperren(ha, b.ablage, b.senden, b.hinweis)
    assert GEHEIM not in json.dumps(b.ablage, ensure_ascii=False)
    assert b.ablage["termine"] == {"gesperrt": True, "sperrbar": True}


def test_spaeter_eintreffende_karte_wird_bei_sperre_verworfen():
    # Der Abruf läuft, während am Display gesperrt wird: Die Karte darf nicht mehr hinaus.
    s, b, ha = Sperre(HELFER), Buehne(), ha_mit("off")
    karte = termine_karte(ha, KALENDER, JETZT)
    s.sperren(ha, b.ablage, b.senden, b.hinweis)
    b.ereignisse.clear()
    assert s.veroeffentlichen(karte, b.ablage, b.senden) is False
    assert GEHEIM not in b.alles_als_text()


def test_veraltetes_lesen_entsperrt_nicht_nach_dem_sperren():
    class Lesen(FakeHA):
        def __init__(self, *a):
            super().__init__(*a)
            self.beim_lesen = None

        def _anfrage(self, methode, pfad, body=None):
            antwort = super()._anfrage(methode, pfad, body)
            if pfad.endswith(HELFER) and self.beim_lesen:
                self.beim_lesen()  # in der Zwischenzeit sperrt das Display
            return antwort

    b = Buehne()
    s = Sperre(HELFER)
    ha = Lesen(ha_mit("off").antworten)
    ha.beim_lesen = lambda: s.sperren(ha_mit("off"), b.ablage, b.senden, b.hinweis)
    s.abgleichen(ha)
    assert s.gesperrt is True


def test_entsperren_vom_handy_zeigt_beim_naechsten_abruf_wieder_termine():
    s, b = Sperre(HELFER), Buehne()
    zyklus(s, ha_mit("on"), b)
    assert s.gesperrt is True
    zyklus(s, ha_mit("off"), b)
    assert s.gesperrt is False
    art, daten = b.ereignisse[-1]
    assert art == "termine" and daten["gesperrt"] is False and daten["heute"]


def test_gesperrt_und_ha_weg_bleibt_gesperrt_und_sendet_keine_termine():
    s, b = Sperre(HELFER), Buehne()
    zyklus(s, ha_mit("on"), b)
    zyklus(s, HaKaputt({}), b)
    assert s.gesperrt is True
    assert GEHEIM not in b.alles_als_text()
    assert b.ablage["termine"] == {"gesperrt": True, "sperrbar": True}


def test_gesperrter_zyklus_sendet_das_schloss_nur_einmal():
    s, b, ha = Sperre(HELFER), Buehne(), ha_mit("on")
    zyklus(s, ha, b)
    zyklus(s, ha, b)
    assert len(b.ereignisse) == 1


def test_ohne_sperre_gilt_sperrbar_nein():
    s, b, ha = Sperre(""), Buehne(), ha_mit("on")
    zyklus(s, ha, b)
    ((_, daten),) = b.ereignisse
    assert daten["gesperrt"] is False and daten["sperrbar"] is False
