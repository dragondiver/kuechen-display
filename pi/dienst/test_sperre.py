"""Termine sperren (sperre.py, hass.HomeAssistant.dienst, #82), ohne Netz."""

import http.client
import json
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from hass import HomeAssistant, termine_karte
from sperre import HINWEIS_FEHLER, Sperre, neuer_stand
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
    "zustand,bisher,erwartet",
    [
        ("on", False, True),
        ("on", True, True),
        ("off", True, False),
        ("off", False, False),
        ("unknown", True, True),
        ("unavailable", True, True),
        (None, True, True),
        ("unknown", False, False),
        ("unavailable", False, False),
        (None, False, False),
    ],
)
def test_nur_off_hebt_auf(zustand, bisher, erwartet):
    assert neuer_stand(zustand, bisher) is erwartet


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
def test_unbekannt_und_nicht_verfuegbar_gilt_frei_wenn_frei(zustand):
    s = Sperre(HELFER)
    assert s.abgleichen(ha_mit(zustand)) is False
    assert s.gesperrt is False


@pytest.mark.parametrize("zustand", ["unknown", "unavailable"])
def test_unbekannt_und_nicht_verfuegbar_hebt_die_sperre_nicht_auf(zustand):
    s = Sperre(HELFER)
    s.gesperrt = True
    assert s.abgleichen(ha_mit(zustand)) is False
    assert s.gesperrt is True


def test_fehlender_helfer_gilt_als_frei_ohne_fehler():
    s = Sperre(HELFER)
    s.abgleichen(ha_mit(None))  # 404 für die Entität
    assert s.gesperrt is False


def test_fehlender_helfer_hebt_die_sperre_nicht_auf():
    s = Sperre(HELFER)
    s.gesperrt = True
    s.abgleichen(ha_mit(None))
    assert s.gesperrt is True


def test_gesperrt_ueberlebt_neustart_von_ha_und_sendet_nichts():
    # HA startet neu: erst fehlt der Helfer, dann ist er unavailable, dann wieder off.
    s, b = Sperre(HELFER), Buehne()
    zyklus(s, ha_mit("on"), b)
    for zwischen in (None, "unavailable", "unknown"):
        zyklus(s, ha_mit(zwischen), b)
        assert s.gesperrt is True
    assert GEHEIM not in b.alles_als_text()
    zyklus(s, ha_mit("off"), b)
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


# --- schnelles Lesen (#107) ----------------------------------------------------
TAKT = 3


class Uhr:
    """Ersetzte Uhr für `beobachten`: `warten` zählt nur, schläft nicht, und löst geplante Änderungen aus."""

    def __init__(self):
        self.jetzt = 0.0
        self.geplant = []  # (Zeitpunkt, Aufruf)

    def planen(self, zeit, aufruf):
        self.geplant.append((zeit, aufruf))

    def warten(self, sekunden):
        self.jetzt += sekunden
        for eintrag in list(self.geplant):
            if eintrag[0] <= self.jetzt:
                self.geplant.remove(eintrag)
                eintrag[1]()


class Helfer(FakeHA):
    """Home Assistant, dessen Helfer sich ändern lässt; `beim_lesen` läuft einmal nach dem Lesen."""

    beim_lesen = None

    def setzen(self, zustand):
        self.antworten[f"/api/states/{HELFER}"] = {"state": zustand}

    def _anfrage(self, methode, pfad, body=None):
        antwort = super()._anfrage(methode, pfad, body)
        if pfad.endswith(HELFER) and self.beim_lesen:
            aufruf, self.beim_lesen = self.beim_lesen, None
            aufruf()
        return antwort


def beobachten(s, ha, uhr, sekunden, wecken=None, b=None):
    """Lässt den Wächter `sekunden` virtuelle Sekunden laufen. Jedes Wecken läuft wie in dienst.py
    als Terminzyklus; gibt die Zeiten der Weckrufe zurück."""
    weckrufe = []
    b = b or Buehne()

    def geweckt():
        weckrufe.append(uhr.jetzt)
        zyklus(s, ha, b)

    s.beobachten(ha, wecken or geweckt, TAKT, uhr.warten, lambda: uhr.jetzt < sekunden)
    return weckrufe


def test_entsperren_vom_handy_wirkt_innerhalb_eines_takts():
    s, b, uhr = Sperre(HELFER), Buehne(), Uhr()
    ha = Helfer(ha_mit("on").antworten)
    zyklus(s, ha, b)  # Stand: gesperrt, wie nach dem Sperren am Display
    assert s.gesperrt is True
    uhr.planen(10, lambda: ha.setzen("off"))
    weckrufe = beobachten(s, ha, uhr, 30, b=b)
    assert len(weckrufe) == 1 and 10 < weckrufe[0] <= 10 + TAKT
    assert s.gesperrt is False
    art, daten = b.ereignisse[-1]
    assert art == "termine" and daten["gesperrt"] is False and daten["heute"]


def test_sperren_vom_handy_wirkt_innerhalb_eines_takts_und_danach_geht_nichts_raus():
    s, b, uhr = Sperre(HELFER), Buehne(), Uhr()
    ha = Helfer(ha_mit("off").antworten)
    zyklus(s, ha, b)
    assert GEHEIM in b.alles_als_text()
    b.ereignisse.clear()
    uhr.planen(7, lambda: ha.setzen("on"))
    weckrufe = beobachten(s, ha, uhr, 60, b=b)
    assert len(weckrufe) == 1 and 7 < weckrufe[0] <= 7 + TAKT
    assert s.gesperrt is True
    assert GEHEIM not in b.alles_als_text()
    assert b.ablage["termine"] == {"gesperrt": True, "sperrbar": True}


@pytest.mark.parametrize("zustand", ["unknown", "unavailable"])
def test_nicht_lesbarer_helfer_aendert_beim_beobachten_nichts(zustand):
    s, b, uhr = Sperre(HELFER), Buehne(), Uhr()
    ha = Helfer(ha_mit("on").antworten)
    zyklus(s, ha, b)
    uhr.planen(5, lambda: ha.setzen(zustand))
    assert beobachten(s, ha, uhr, 30, b=b) == []
    assert s.gesperrt is True


def test_ha_nicht_erreichbar_beim_beobachten_haelt_die_sperre(caplog):
    s, b, uhr = Sperre(HELFER), Buehne(), Uhr()
    zyklus(s, ha_mit("on"), b)
    with caplog.at_level("INFO", logger="dienst"):
        assert beobachten(s, HaKaputt({}), uhr, 30, b=b) == []
    assert s.gesperrt is True
    assert GEHEIM not in b.alles_als_text()
    # zehn Versuche, aber nur eine Warnung im Journal
    assert len([r for r in caplog.records if "nicht lesbar" in r.message]) == 1


def test_schnelles_lesen_von_vor_dem_sperren_am_display_entsperrt_nicht():
    s, b, uhr = Sperre(HELFER), Buehne(), Uhr()
    ha = Helfer(ha_mit("on").antworten)
    zyklus(s, ha, b)  # gesperrt
    ha.setzen("off")  # Handy entsperrt, der Wächter liest „off“ ...
    ha.beim_lesen = lambda: s.sperren(  # ... während das Display erneut sperrt
        Helfer(ha_mit().antworten), b.ablage, b.senden, b.hinweis
    )
    weckrufe = beobachten(s, ha, uhr, TAKT, b=b)  # genau ein Durchlauf
    assert weckrufe == [] and s.gesperrt is True
    assert b.ablage["termine"] == {"gesperrt": True, "sperrbar": True}


def test_waechter_und_terminzyklus_ueberschreiben_sich_nicht():
    """Der Terminzyklus liest „off“, der Wächter liest dazwischen „on“ und sperrt: kein Entsperren."""
    s, b = Sperre(HELFER), Buehne()
    ha = Helfer(ha_mit("off").antworten)
    zyklus(s, ha, b)

    def waechter_liest_on():
        ha.setzen("on")
        s.abgleichen(ha)

    ha.beim_lesen = waechter_liest_on  # mitten im Zyklus, nach dessen Lesen von „off“
    b.ereignisse.clear()
    zyklus(s, ha, b)
    assert s.gesperrt is True
    assert GEHEIM not in b.alles_als_text()
    zyklus(s, ha, b)
    assert b.ablage["termine"] == {"gesperrt": True, "sperrbar": True}


def test_leere_entitaet_fragt_beim_beobachten_nichts_ab():
    s, uhr = Sperre(""), Uhr()
    ha = Helfer(ha_mit("on").antworten)
    assert beobachten(s, ha, uhr, 30, wecken=lambda: pytest.fail("geweckt")) == []
    assert ha.anfragen == [] and uhr.jetzt == 0


def test_beobachten_fragt_nur_den_helfer_und_keinen_kalender():
    s, uhr = Sperre(HELFER), Uhr()
    ha = Helfer(ha_mit("off").antworten)
    beobachten(s, ha, uhr, 30, wecken=lambda: None)
    assert len(ha.anfragen) == 10
    assert {p for _, p, _ in ha.anfragen} == {f"/api/states/{HELFER}"}


@pytest.mark.parametrize(
    "fehler", [http.client.IncompleteRead(b"{", 5), http.client.BadStatusLine("")]
)
def test_abgebrochene_antwort_entsperrt_nicht_und_wird_einmal_gemeldet(
    monkeypatch, caplog, fehler
):
    # fail closed (#109): Ein Lesefehler lässt „gesperrt“ stehen
    s, b, uhr = Sperre(HELFER), Buehne(), Uhr()
    zyklus(s, ha_mit("on"), b)
    assert s.gesperrt is True
    ha = HomeAssistant("http://ha.test:8123", "geheim")
    monkeypatch.setattr("hass.urllib.request.urlopen", _wirft(fehler))
    with caplog.at_level("INFO", logger="dienst"):
        assert beobachten(s, ha, uhr, 30, b=b) == []
    assert s.gesperrt is True
    assert GEHEIM not in b.alles_als_text()
    assert len([r for r in caplog.records if "nicht lesbar" in r.message]) == 1
    assert not [r for r in caplog.records if r.exc_info]


@pytest.mark.parametrize("roh", [b"[]", b"1", b'"x"'])
def test_antwort_ohne_objekt_entsperrt_nicht(monkeypatch, roh):
    s, b = Sperre(HELFER), Buehne()
    zyklus(s, ha_mit("on"), b)
    ha = HomeAssistant("http://ha.test:8123", "geheim")
    monkeypatch.setattr("hass.urllib.request.urlopen", _Antwort(roh))
    assert s.abgleichen(ha) is False
    assert s.gesperrt is True


def _wirft(fehler):
    def urlopen(req, timeout=None):
        raise fehler

    return urlopen


class _Antwort:
    def __init__(self, roh):
        self.roh = roh

    def __call__(self, req, timeout=None):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.roh


def test_unerwarteter_fehler_beim_beobachten_steht_einmal_mit_traceback_im_journal(
    caplog,
):
    class Kaputt(FakeHA):
        def zustand(self, entity_id):
            raise RuntimeError("unerwartet")

    s, b, uhr = Sperre(HELFER), Buehne(), Uhr()
    zyklus(s, ha_mit("on"), b)
    with caplog.at_level("INFO", logger="dienst"):
        assert beobachten(s, Kaputt({}), uhr, 30, b=b) == []  # zehn Durchläufe
    assert s.gesperrt is True
    assert len([r for r in caplog.records if r.exc_info]) == 1


def test_beobachter_meldet_erneut_nach_zwischenzeitlicher_besserung(caplog):
    class Wackelig(FakeHA):
        aufrufe = 0

        def zustand(self, entity_id):
            Wackelig.aufrufe += 1
            if Wackelig.aufrufe in (1, 2, 5, 6):
                raise RuntimeError("unerwartet")
            return "on"

    s, uhr = Sperre(HELFER), Uhr()
    with caplog.at_level("INFO", logger="dienst"):
        s.beobachten(
            Wackelig({}), lambda: None, TAKT, uhr.warten, lambda: uhr.jetzt < 8 * TAKT
        )
    assert len([r for r in caplog.records if r.exc_info]) == 2
