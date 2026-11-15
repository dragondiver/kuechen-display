from daten import LAGEN, wetter_aufbereiten

# Gekürzte Antworten von Home Assistant 2026.9 (dwd_weather).
WETTER = {
    "entity_id": "weather.stuttgart_schn",
    "state": "cloudy",
    "attributes": {"temperature": 11.4, "temperature_unit": "°C", "humidity": 82},
}
VORHERSAGE = [
    {
        "datetime": "2026-11-15T00:00:00+00:00",
        "condition": "cloudy",
        "temperature": 12.6,
        "templow": 4.6,
    },
    {
        "datetime": "2026-11-16T00:00:00+00:00",
        "condition": "rainy",
        "temperature": 9.4,
        "templow": 3.1,
    },
]


def karte(**kw):
    kw.setdefault("sonne", "above_horizon")
    return wetter_aufbereiten(
        kw.pop("wetter", WETTER), kw.pop("vorhersage", VORHERSAGE), **kw
    )


def test_tag_zeigt_lage_temperatur_und_nachtwert():
    k = karte(ort="Kornwestheim", stand=1763200000)
    assert k == {
        "ort": "Kornwestheim",
        "temperatur": "11°",
        "zustand": "Bedeckt",
        "zeile": "Nacht 5°",
        "bild": "gedaempft",
        "unbekannt": False,
        "stand": 1763200000,
    }


def test_eigener_temperatursensor_geht_vor():
    assert karte(temperatur="9.6")["temperatur"] == "10°"


def test_sensor_ohne_wert_faellt_auf_die_entitaet_zurueck():
    assert karte(temperatur="unavailable")["temperatur"] == "11°"


def test_minusgrade():
    assert karte(temperatur="-0.4")["temperatur"] == "0°"
    assert karte(temperatur="-3.2")["temperatur"] == "−3°"


def test_nachts_ersetzt_das_nachtbild_trockene_lagen():
    assert karte(sonne="below_horizon")["bild"] == "nacht"
    assert (
        karte(wetter={**WETTER, "state": "sunny"}, sonne="below_horizon")["bild"]
        == "nacht"
    )


def test_nachts_bleiben_regen_und_schnee():
    assert (
        karte(wetter={**WETTER, "state": "rainy"}, sonne="below_horizon")["bild"]
        == "regen"
    )
    assert (
        karte(wetter={**WETTER, "state": "snowy"}, sonne="below_horizon")["bild"]
        == "schnee"
    )


def test_nachts_steht_ebenfalls_der_tiefstwert():
    assert karte(sonne="below_horizon")["zeile"] == "Nacht 5°"


def test_ohne_vorhersage_bleibt_die_zeile_leer():
    assert karte(vorhersage=[])["zeile"] == ""
    assert karte(vorhersage=[{"condition": "cloudy"}])["zeile"] == ""


def test_unbekannte_lage_steht_im_klartext_und_wird_gemeldet():
    k = karte(wetter={**WETTER, "state": "sandsturm"})
    assert (k["zustand"], k["bild"], k["unbekannt"]) == ("sandsturm", "gedaempft", True)


def test_entitaet_nicht_verfuegbar():
    k = karte(wetter={**WETTER, "state": "unavailable", "attributes": {}})
    assert (k["zustand"], k["temperatur"], k["unbekannt"]) == (
        "Keine Wetterdaten",
        "–",
        True,
    )


def test_entitaet_fehlt_ganz():
    k = karte(wetter=None, vorhersage=[])
    assert (k["zustand"], k["temperatur"], k["zeile"]) == ("Keine Wetterdaten", "–", "")
    assert k["unbekannt"] is True


def test_jede_lage_hat_ein_vorhandenes_bild():
    assert {bild for _, bild in LAGEN.values()} <= {
        "sonnig",
        "wolkig",
        "gedaempft",
        "regen",
        "schnee",
        "nacht",
    }
