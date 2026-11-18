from datetime import datetime
from zoneinfo import ZoneInfo

from daten import LAGEN, warnung_aufbereiten, wetter_aufbereiten

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
        "warnung": None,
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


# --- Wetterwarnung (#37) --------------------------------------------------------
BERLIN = ZoneInfo("Europe/Berlin")
JETZT = datetime(2026, 11, 18, 14, 0, tzinfo=BERLIN)


def sensor(*warnungen, state="2"):
    """Sensor wie die Integration dwd_weather_warnings: warning_N_name/_level/_end/_color."""
    attribute = {"warning_count": len(warnungen)}
    for n, w in enumerate(warnungen, 1):
        for schluessel, wert in w.items():
            attribute[f"warning_{n}_{schluessel}"] = wert
    return {"state": state, "attributes": attribute}


def warn(name="Sturmböen", level=2, end="2026-11-18T18:00:00+01:00", color="#ff9900"):
    return {"name": name, "level": level, "end": end, "color": color}


def test_warnung_stufe_2_wird_gezeigt_mit_farbe_und_ende():
    assert warnung_aufbereiten(sensor(warn()), JETZT) == {
        "text": "Sturmböen bis 18 Uhr",
        "farbe": "#ff9900",
        "mehr": 0,
    }


def test_warnung_stufe_1_wird_nicht_gezeigt():
    assert warnung_aufbereiten(sensor(warn(level=1), warn(level="1")), JETZT) is None


def test_warnung_hoechste_stufe_gewinnt_unabhaengig_von_der_reihenfolge():
    a, b = warn("Frost", 2, color="#ff9900"), warn("Unwetter", 3, color="#ff0000")
    for sens in (sensor(a, b), sensor(b, a)):
        k = warnung_aufbereiten(sens, JETZT)
        assert (k["text"], k["farbe"], k["mehr"]) == (
            "Unwetter bis 18 Uhr",
            "#ff0000",
            1,
        )


def test_warnung_gleiche_stufe_frueheres_ende_gewinnt():
    spaet = warn("Nebel", 2, end="2026-11-18T20:00:00+01:00")
    frueh = warn("Wind", 2, end="2026-11-18T16:30:00+01:00")
    for sens in (sensor(spaet, frueh), sensor(frueh, spaet)):
        k = warnung_aufbereiten(sens, JETZT)
        assert (k["text"], k["mehr"]) == ("Wind bis 16:30 Uhr", 1)


def test_warnung_vorbeigegangene_wird_ignoriert():
    vorbei = warn("Alt", 3, end="2026-11-18T13:59:00+01:00")
    k = warnung_aufbereiten(sensor(vorbei, warn("Wind", 2)), JETZT)
    assert (k["text"], k["mehr"]) == ("Wind bis 18 Uhr", 0)
    assert warnung_aufbereiten(sensor(vorbei), JETZT) is None


def test_warnung_mehrere_ab_stufe_2_zaehlen_nur_aktive_mit_stufe_2():
    sens = sensor(
        warn("A", 3),
        warn("B", 2),
        warn("C", 2),
        warn("D", 1),
        warn("E", 4, end="2026-11-18T10:00:00+01:00"),
    )
    assert warnung_aufbereiten(sens, JETZT)["mehr"] == 2


def test_warnung_ende_morgen_und_spaeter_steht_mit_tag():
    morgen = warnung_aufbereiten(sensor(warn(end="2026-11-19T06:00:00+01:00")), JETZT)
    assert morgen["text"] == "Sturmböen bis morgen 6 Uhr"
    freitag = warnung_aufbereiten(sensor(warn(end="2026-11-20T12:00:00+01:00")), JETZT)
    assert freitag["text"] == "Sturmböen bis Fr 12 Uhr"


def test_warnung_ende_in_utc_wird_in_die_lokale_zeit_umgerechnet():
    k = warnung_aufbereiten(sensor(warn(end="2026-11-18T17:00:00+00:00")), JETZT)
    assert k["text"] == "Sturmböen bis 18 Uhr"


def test_warnung_sensor_fehlt_oder_nicht_verfuegbar():
    assert warnung_aufbereiten(None, JETZT) is None
    assert (
        warnung_aufbereiten({"state": "unavailable", "attributes": {}}, JETZT) is None
    )
    assert warnung_aufbereiten({"state": "unknown", "attributes": {}}, JETZT) is None


def test_warnung_ohne_warnungen_oder_fehlende_attribute():
    assert warnung_aufbereiten(sensor(), JETZT) is None
    assert (
        warnung_aufbereiten({"state": "2", "attributes": {"warning_count": "x"}}, JETZT)
        is None
    )
    # warning_count verspricht zwei, aber Name, Stufe und Ende fehlen teilweise
    sens = {
        "state": "2",
        "attributes": {
            "warning_count": 3,
            "warning_1_name": "Wind",
            "warning_2_level": 2,
            "warning_3_name": "Frost",
            "warning_3_level": 2,
            "warning_3_end": "kein Datum",
        },
    }
    assert warnung_aufbereiten(sens, JETZT) is None


def test_warnung_ohne_brauchbare_farbe_nimmt_die_dwd_farbe_der_stufe():
    for farbe in (None, "", "orange", "#fff"):
        k = warnung_aufbereiten(sensor(warn(color=farbe)), JETZT)
        assert k["farbe"] == "#ff9900"
    assert (
        warnung_aufbereiten(sensor(warn(level=3, color=None)), JETZT)["farbe"]
        == "#ff0000"
    )


def test_wetterkarte_traegt_die_warnung():
    assert karte(warnung=None)["warnung"] is None
    assert (
        karte(warnung={"text": "x", "farbe": "#ff9900", "mehr": 0})["warnung"]["text"]
        == "x"
    )


def test_warnung_schwarz_gilt_als_keine_farbe():
    k = warnung_aufbereiten(sensor(warn(color="#000000")), JETZT)
    assert k["farbe"] == "#ff9900"


def test_warnung_unendliche_oder_keine_zahlen_werfen_nicht():
    assert (
        warnung_aufbereiten(
            {"state": "2", "attributes": {"warning_count": "inf"}}, JETZT
        )
        is None
    )
    assert (
        warnung_aufbereiten(
            {"state": "2", "attributes": {"warning_count": "nan"}}, JETZT
        )
        is None
    )
    k = warnung_aufbereiten(
        sensor(
            warn(level="inf"), warn(level="nan"), warn(level="hoch"), warn("Wind", 2)
        ),
        JETZT,
    )
    assert (k["text"], k["mehr"]) == ("Wind bis 18 Uhr", 0)
