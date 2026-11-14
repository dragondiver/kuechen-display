import json
from array import array

from vertrag import RAHMEN_BYTES, ROH_BYTES, Leitung, kanal


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


def test_tipp_beim_zuhoeren_beendet_gespraech_am_display():
    # 8.11.2026: Ein zweiter Tipp schaltet Elektras Mikrofon wieder aus. Die Bridge kennt noch
    # keine Nachricht dafür; sie hört nichts mehr und schläft nach ihrer Ruhezeit ein.
    l = Leitung()
    l.nachricht(json.dumps({"type": "zustand", "wert": "zuhoeren"}))
    a = l.tipp()
    assert not l.mikro_offen and l.zustand == "aus"
    assert [x.daten for x in a if x.art == "anzeige"] == [
        {"ereignis": "zustand", "wert": "aus"}
    ]
    assert [x for x in a if x.art == "senden"] == []


def test_tipp_beim_nachdenken_beendet_auch():
    l = Leitung()
    l.nachricht(json.dumps({"type": "zustand", "wert": "nachdenken"}))
    l.tipp()
    assert not l.mikro_offen


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
