"""Termine für den Ruhebildschirm (daten.termine_aufbereiten, hass.termine_karte), ohne Netz."""

from datetime import datetime
from zoneinfo import ZoneInfo

from daten import termine_aufbereiten
from hass import termine_karte
from test_hass import FakeHA

BERLIN = ZoneInfo("Europe/Berlin")
# Sonntag, 15.11.2026, 14:00 Uhr
JETZT = datetime(2026, 11, 15, 14, 0, tzinfo=BERLIN)
KALENDER = ["calendar.family", "calendar.abfall"]
NAMEN = {"calendar.family": "Family", "calendar.abfall": "Abfall"}

# So sieht die Antwort der CalDAV-Integration aus (HA 2026.11, calendar.get_events).
FAMILY = [
    {
        "start": "2026-11-15T09:00:00+01:00",
        "end": "2026-11-15T10:00:00+01:00",
        "summary": "Frühstück",
    },
    {
        "start": "2026-11-15T18:30:00+01:00",
        "end": "2026-11-15T20:00:00+01:00",
        "summary": "Probe Chor",
    },
    {
        "start": "2026-11-15T13:30:00+01:00",
        "end": "2026-11-15T15:00:00+01:00",
        "summary": "Kaffee",
    },
    {
        "start": "2026-11-16T08:00:00+01:00",
        "end": "2026-11-16T09:00:00+01:00",
        "summary": "Zahnarzt",
    },
    {"start": "2026-11-16", "end": "2026-11-17", "summary": "Geburtstag Oma"},
]
ABFALL = [{"start": "2026-11-15", "end": "2026-11-16", "summary": "Gelber Sack"}]


def aufbereiten(antwort=None, jetzt=JETZT, **kw):
    if antwort is None:
        antwort = {"calendar.family": FAMILY, "calendar.abfall": ABFALL}
    return termine_aufbereiten(antwort, KALENDER, NAMEN, jetzt, **kw)


def zeilen(liste):
    return [(t["zeit"], t["titel"]) for t in liste]


def test_heute_ganztaegig_oben_dann_was_noch_kommt():
    k = aufbereiten()
    # Frühstück ist vorbei, Kaffee läuft noch und bleibt.
    assert zeilen(k["heute"]) == [
        ("ganztägig", "Gelber Sack"),
        ("13:30", "Kaffee"),
        ("18:30", "Probe Chor"),
    ]


def test_punkt_zeigt_kalendername_und_farbe_nach_reihenfolge():
    k = aufbereiten()
    assert [(t["kalender"], t["farbe"]) for t in k["heute"]] == [
        ("Abfall", "p2"),
        ("Family", "p1"),
        ("Family", "p1"),
    ]


def test_morgen_mit_uhrzeit_von_bis():
    assert zeilen(aufbereiten()["morgen"]) == [
        ("ganztägig", "Geburtstag Oma"),
        ("08:00–09:00", "Zahnarzt"),
    ]


def test_woche_ab_heute_sieben_tage_mit_ueberschrift():
    w = aufbereiten()["woche"]
    assert [(t["tag"], t["datum"]) for t in w] == [
        ("Heute", "15.11. · KW 46"),
        ("Morgen", "16.11. · KW 47"),
        ("Dienstag", "17.11. · KW 47"),
        ("Mittwoch", "18.11. · KW 47"),
        ("Donnerstag", "19.11. · KW 47"),
        ("Freitag", "20.11. · KW 47"),
        ("Samstag", "21.11. · KW 47"),
    ]
    assert len(w[0]["termine"]) == 3  # wie „Noch heute“
    assert zeilen(w[1]["termine"]) == [
        ("ganztägig", "Geburtstag Oma"),
        ("08:00", "Zahnarzt"),
    ]
    assert w[2]["termine"] == []


def test_bis_laesst_die_seite_vergangenes_ausblenden():
    k = aufbereiten()
    probe = next(t for t in k["heute"] if t["titel"] == "Probe Chor")
    assert probe["bis"] == int(datetime(2026, 11, 15, 20, 0, tzinfo=BERLIN).timestamp())
    sack = k["heute"][0]
    assert sack["bis"] == int(datetime(2026, 11, 16, tzinfo=BERLIN).timestamp())


def test_mehrtaegig_ganztaegig_steht_an_jedem_tag():
    urlaub = [{"start": "2026-11-16", "end": "2026-11-19", "summary": "Urlaub"}]
    w = aufbereiten({"calendar.family": urlaub})["woche"]
    assert [len(t["termine"]) for t in w] == [0, 1, 1, 1, 0, 0, 0]


def test_ueber_mitternacht():
    nacht = [
        {
            "start": "2026-11-15T22:00:00+01:00",
            "end": "2026-11-16T02:00:00+01:00",
            "summary": "Nachtschicht",
        }
    ]
    k = aufbereiten({"calendar.family": nacht})
    assert zeilen(k["heute"]) == [("22:00", "Nachtschicht")]
    assert zeilen(k["morgen"]) == [("bis 02:00", "Nachtschicht")]


def test_utc_zeiten_werden_lokal():
    t = [
        {"start": "2026-11-15T17:30:00Z", "end": "2026-11-15T18:00:00Z", "summary": "X"}
    ]
    assert zeilen(aufbereiten({"calendar.family": t})["heute"]) == [("18:30", "X")]


def test_sommerzeit_wechsel_in_der_woche():
    jetzt = datetime(2026, 3, 27, 12, 0, tzinfo=BERLIN)
    t = [
        {
            "start": "2026-03-30T08:00:00+02:00",
            "end": "2026-03-30T09:00:00+02:00",
            "summary": "Nach der Umstellung",
        }
    ]
    w = aufbereiten({"calendar.family": t}, jetzt=jetzt)["woche"]
    assert zeilen(w[3]["termine"]) == [("08:00", "Nach der Umstellung")]


def test_kaputte_eintraege_und_leere_titel():
    t = [
        {"summary": "ohne Start"},
        {"start": "kein Datum", "summary": "Unsinn"},
        {"start": "2026-11-15T16:00:00+01:00", "end": "2026-11-15T17:00:00+01:00"},
    ]
    assert zeilen(aufbereiten({"calendar.family": t})["heute"]) == [
        ("16:00", "(ohne Titel)")
    ]


def test_ohne_namen_gilt_die_entitaet():
    k = termine_aufbereiten({"calendar.abfall": ABFALL}, KALENDER, {}, JETZT)
    assert k["heute"][0]["kalender"] == "Abfall"


def test_termine_karte_fragt_alle_kalender_in_einem_abruf():
    ha = FakeHA(
        {
            "/api/states/calendar.family": {
                "state": "off",
                "attributes": {"friendly_name": "Family"},
            },
            "/api/states/calendar.abfall": {
                "state": "on",
                "attributes": {"friendly_name": "Abfall"},
            },
            "/api/services/calendar/get_events?return_response": {
                "service_response": {
                    "calendar.family": {"events": FAMILY},
                    "calendar.abfall": {"events": ABFALL},
                }
            },
        }
    )
    k = termine_karte(ha, KALENDER, JETZT)
    assert len(k["heute"]) == 3 and k["fehlt"] == []
    assert (
        "POST",
        "/api/services/calendar/get_events?return_response",
        {
            "entity_id": KALENDER,
            "start_date_time": "2026-11-15T00:00:00+01:00",
            "end_date_time": "2026-11-22T00:00:00+01:00",
        },
    ) in ha.anfragen


def test_unbekannter_kalender_steht_unter_fehlt_und_behaelt_die_farben():
    ha = FakeHA(
        {
            "/api/states/calendar.abfall": {"state": "on", "attributes": {}},
            "/api/services/calendar/get_events?return_response": {
                "service_response": {"calendar.abfall": {"events": ABFALL}}
            },
        }
    )
    k = termine_karte(ha, KALENDER, JETZT)
    assert k["fehlt"] == ["calendar.family"]
    assert k["heute"][0]["farbe"] == "p2"


def test_ohne_bekannten_kalender_kein_abruf():
    ha = FakeHA({})
    k = termine_karte(ha, ["calendar.gibt_es_nicht"], JETZT)
    assert k["heute"] == [] and k["fehlt"] == ["calendar.gibt_es_nicht"]
    assert not any(p.startswith("/api/services") for _, p, _ in ha.anfragen)
