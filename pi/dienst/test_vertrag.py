import json
import logging
from array import array

import pytest
from vertrag import RAHMEN_BYTES, ROH_BYTES, Ablage, Leitung, kanal


def arten(aktionen):
    return [a.art for a in aktionen]


def test_kanal_null_aus_sechs_kanaelen():
    roh = array("h", [k * 10 + i for i in range(960) for k in range(6)]).tobytes()
    assert len(roh) == ROH_BYTES
    k0 = array("h")
    k0.frombytes(kanal(roh))
    assert len(k0.tobytes()) == RAHMEN_BYTES
    assert list(k0[:3]) == [0, 1, 2]


def test_tipp_im_ruhezustand_beginnt_gespraech_und_oeffnet_mikro():
    l = Leitung()
    a = l.tipp()
    assert a[0].daten == {"type": "wort"}
    assert l.mikro_offen


def test_tipp_beim_sprechen_ist_stopp():
    l = Leitung()
    l.nachricht(json.dumps({"type": "zustand", "wert": "sprechen"}))
    assert arten(l.tipp()) == ["verwerfen", "senden"]


def test_tipp_beim_zuhoeren_beendet_gespraech_auch_an_der_bridge():
    # 8.11.2026: Ein zweiter Tipp schaltet Elektras Mikrofon wieder aus. Seit rundfunk#238 erfährt
    # es die Bridge über "ende" und schließt Live sofort.
    l = Leitung()
    l.nachricht(json.dumps({"type": "zustand", "wert": "zuhoeren"}))
    a = l.tipp()
    assert not l.mikro_offen and l.zustand == "aus"
    assert [x.daten for x in a if x.art == "anzeige"] == [
        {"ereignis": "zustand", "wert": "aus"}
    ]
    assert [x.daten for x in a if x.art == "senden"] == [{"type": "ende"}]


def test_tipp_beim_nachdenken_beendet_auch():
    l = Leitung()
    l.nachricht(json.dumps({"type": "zustand", "wert": "nachdenken"}))
    a = l.tipp()
    assert not l.mikro_offen
    assert [x.daten for x in a if x.art == "senden"] == [{"type": "ende"}]


def test_getrennt_schickt_kein_ende():
    # Ohne Leitung gibt es niemanden, dem man "ende" schicken könnte.
    l = Leitung()
    l.nachricht(json.dumps({"type": "zustand", "wert": "zuhoeren"}))
    assert [x for x in l.getrennt() if x.art == "senden"] == []


def test_bridge_spricht_danach_weiter_oeffnet_wieder():
    # Kommt von der Bridge doch noch ein Zustand, gilt der (z. B. Antwort war schon unterwegs).
    l = Leitung()
    l.nachricht(json.dumps({"type": "zustand", "wert": "zuhoeren"}))
    l.tipp()
    l.nachricht(json.dumps({"type": "zustand", "wert": "sprechen"}))
    assert l.mikro_offen and l.zustand == "sprechen"


def test_stopp_ohne_gespraech_schickt_nichts():
    assert Leitung().stopp() == []


def test_zustand_ausser_sprechen_verwirft_wiedergabe():
    l = Leitung()
    assert arten(l.nachricht(json.dumps({"type": "zustand", "wert": "sprechen"}))) == [
        "anzeige"
    ]
    assert arten(l.nachricht(json.dumps({"type": "zustand", "wert": "zuhoeren"}))) == [
        "verwerfen",
        "anzeige",
    ]


def test_aus_schliesst_mikro():
    l = Leitung()
    l.tipp()
    l.nachricht(json.dumps({"type": "zustand", "wert": "aus"}))
    assert not l.mikro_offen and l.zustand == "aus"


def test_jeder_andere_zustand_oeffnet_mikro_auch_ohne_wort():
    # Verleih an telefon-ai und Warnungen beginnen ohne "wort".
    l = Leitung()
    l.nachricht(json.dumps({"type": "zustand", "wert": "sprechen"}))
    assert l.mikro_offen


def test_unbekannter_zustand_wird_ignoriert():
    l = Leitung()
    assert l.nachricht(json.dumps({"type": "zustand", "wert": "tanzen"})) == []
    assert l.zustand == "aus"


def test_befehl_geht_an_die_anzeige():
    a = Leitung().nachricht(
        json.dumps(
            {
                "type": "befehl",
                "id": 3,
                "name": "seite_zeigen",
                "argumente": {"seite": "morgen"},
            }
        )
    )
    assert a[0].daten == {
        "ereignis": "befehl",
        "id": 3,
        "name": "seite_zeigen",
        "argumente": {"seite": "morgen"},
    }


def test_befehl_ohne_ganzzahlige_id_wird_verworfen():
    assert (
        Leitung().nachricht(json.dumps({"type": "befehl", "id": True, "name": "x"}))
        == []
    )


def test_lautstaerke_wird_begrenzt():
    assert Leitung().nachricht(json.dumps({"type": "lautstaerke", "wert": 140}))[
        0
    ].daten == {"wert": 100}


def test_kaputtes_json_tut_nichts():
    assert Leitung().nachricht("{kaputt") == []


def test_getrennt_setzt_alles_zurueck():
    l = Leitung()
    l.tipp()
    assert arten(l.getrennt()) == ["verwerfen", "anzeige"]
    assert not l.mikro_offen


# --- Ablage für Apps ohne Kiosk-Seite (#70) -------------------------------------
def test_ablage_gibt_befehl_einmal_heraus():
    a = Ablage()
    a.ablegen({"id": 1}, 10.0)
    assert a.abholen(11.0) == {"id": 1}
    assert a.abholen(11.5) is None


def test_ablage_der_aelteste_zuerst():
    a = Ablage()
    a.ablegen({"id": 1}, 10.0)
    a.ablegen({"id": 2}, 10.5)
    assert [a.abholen(11.0)["id"], a.abholen(11.0)["id"]] == [1, 2]


def test_abgelaufener_befehl_wird_nicht_mehr_ausgefuehrt():
    a = Ablage()
    a.ablegen({"id": 1}, 10.0)
    assert a.abholen(10.0 + Ablage.FRIST_S) is None
    assert a.abgelaufen(10.0 + Ablage.FRIST_S) == [{"id": 1}]
    assert a.abgelaufen(20.0) == []


def test_abgeholter_befehl_bekommt_keine_fehler_quittung():
    a = Ablage()
    a.ablegen({"id": 1}, 10.0)
    a.abholen(11.0)
    assert a.abgelaufen(20.0) == []


def test_app_gilt_kurz_nach_der_abfrage_als_vorn():
    a = Ablage()
    assert not a.app_vorn(10.0)
    a.app_meldet(10.0)
    assert a.app_vorn(10.0 + Ablage.APP_WEG_S - 0.1)
    assert not a.app_vorn(10.0 + Ablage.APP_WEG_S)


def test_kiosk_seite_loest_app_sofort_ab():
    a = Ablage()
    a.app_meldet(10.0)
    a.kiosk_vorn(10.0)
    assert not a.app_vorn(10.1)


def test_frist_liegt_unter_der_der_bridge():
    # rundfunk netzgeraet.BEFEHL_FRIST_S = 3.0
    assert Ablage.FRIST_S < 3.0


def test_verlassene_kiosk_seite_gilt_als_weg_bis_eine_neue_kommt():
    a = Ablage()
    a.kiosk_geht()
    assert a.app_vorn(100.0)  # auch ohne Abfrage einer App
    a.kiosk_vorn(100.0)
    assert not a.app_vorn(100.0)


def test_neue_kiosk_seite_bekommt_wartende_befehle():
    a = Ablage()
    a.ablegen({"id": 1}, 10.0)
    a.ablegen({"id": 2}, 10.0 + Ablage.FRIST_S + 0.5)
    assert a.kiosk_vorn(10.0 + Ablage.FRIST_S + 1) == [{"id": 2}]
    assert a.abholen(10.0 + Ablage.FRIST_S + 1) is None
    assert a.abgelaufen(100.0) == [{"id": 1}]


# --- Lokale Befehle (Weckwort, #89) ----------------------------------------------
def lokal(nummer=1, richtung="vor"):
    return {
        "id": f"lokal-{nummer}",
        "name": "rezeptschritt",
        "argumente": {"richtung": richtung},
    }


def test_ist_lokal_erkennt_nur_eigene_kennungen():
    from vertrag import ist_lokal

    assert ist_lokal("lokal-3")
    assert not ist_lokal(3)
    assert not ist_lokal(None)
    assert not ist_lokal("3")


def test_quittung_der_bridge_geht_weiter_an_die_bridge():
    from vertrag import quittung_leiten

    nachricht, zeile = quittung_leiten({"id": 7, "ok": True, "fremd": 1})
    assert nachricht == {"type": "quittung", "id": 7, "ok": True}
    assert zeile is None


def test_quittung_eines_lokalen_befehls_geht_nicht_an_die_bridge():
    from vertrag import quittung_leiten

    nachricht, zeile = quittung_leiten({"id": "lokal-4", "ok": True})
    assert nachricht is None
    assert "lokal-4" in zeile and "ausgeführt" in zeile


def test_fehlerquittung_eines_lokalen_befehls_steht_im_journal_nicht_bei_der_bridge():
    from vertrag import quittung_leiten

    nachricht, zeile = quittung_leiten(
        {"id": "lokal-5", "ok": False, "fehler": "Hier geht es nur vor."}
    )
    assert nachricht is None
    assert "ohne Wirkung" in zeile and "Hier geht es nur vor." in zeile


def test_abgelaufener_lokaler_befehl_geht_nicht_an_die_bridge():
    from vertrag import abgelaufene_melden

    bridge, journal = abgelaufene_melden([lokal(1), {"id": 9, "name": "x"}])
    assert [n["id"] for n in bridge] == [9]
    assert bridge[0]["ok"] is False
    assert len(journal) == 1 and "lokal-1" in journal[0]


def test_lokaler_befehl_wird_von_der_app_abgeholt():
    a = Ablage()
    a.ablegen(lokal(2, "zurueck"), 10.0)
    assert a.abholen(10.5)["argumente"] == {"richtung": "zurueck"}


def test_kiosk_seite_bekommt_keinen_lokalen_befehl():
    a = Ablage()
    a.ablegen(lokal(1), 10.0)
    a.ablegen({"id": 3, "name": "seite_zeigen"}, 10.1)
    offen = a.kiosk_vorn(10.5)
    assert [b["id"] for b in offen] == [3]
    assert a.abgelaufen(100.0) == []  # auch nicht als „abgelaufen“ übrig


def test_verworfener_lokaler_befehl_kommt_ins_journal(caplog):
    a = Ablage()
    a.ablegen({"id": "lokal-7", "name": "rezeptschritt"}, 10.0)
    a.ablegen({"id": 3}, 10.0)
    with caplog.at_level(logging.WARNING, logger="dienst"):
        offen = a.kiosk_vorn(10.5)
    assert offen == [{"id": 3}]
    zeilen = [r.getMessage() for r in caplog.records]
    assert len(zeilen) == 1 and "lokal-7" in zeilen[0]


def test_ohne_lokalen_befehl_bleibt_das_journal_leer(caplog):
    a = Ablage()
    a.ablegen({"id": 3}, 10.0)
    with caplog.at_level(logging.WARNING, logger="dienst"):
        a.kiosk_vorn(10.5)
    assert not caplog.records


def test_tipp_ohne_bridge_zeigt_nur_einen_hinweis():
    l = Leitung()
    a = l.tipp(verbunden=False)
    assert arten(a) == ["anzeige"]
    assert a[0].daten == {
        "ereignis": "hinweis",
        "text": "Elektra ist gerade nicht erreichbar",
    }
    # Das Gespräch hat nicht begonnen: Zustand bleibt aus, das Mikrofon zu.
    assert l.zustand == "aus"
    assert l.mikro_offen is False


def test_tipp_mit_bridge_bleibt_wie_vorher():
    assert arten(Leitung().tipp(verbunden=True)) == arten(Leitung().tipp())


@pytest.mark.parametrize("roh", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_lautstaerke_nicht_endlich_ist_ohne_wirkung(roh):
    # json.loads nimmt diese Werte an; int() darauf wirft (#102)
    assert Leitung().nachricht('{"type":"lautstaerke","wert":' + roh + "}") == []
