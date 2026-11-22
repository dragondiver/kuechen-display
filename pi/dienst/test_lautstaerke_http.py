"""POST /lautstaerke (#99): Header-Pflicht, Prüfung, Weg des Bridge-Befehls, Wiederherstellen beim Start."""

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import dienst
import pytest
from lautstaerke import Lautstaerke
from vertrag import Leitung

HEADER = {"X-Kuechen": "1"}


@pytest.fixture
def aufrufe(monkeypatch, tmp_path):
    """Ersetzt wpctl: sammelt die PipeWire-Anteile, die gesetzt würden."""
    liste = []
    monkeypatch.setattr(
        dienst, "lautstaerke_stand", Lautstaerke(tmp_path / "lautstaerke")
    )

    def fake(kommando, **kw):
        assert kommando[:3] == ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@"]
        liste.append(float(kommando[3]))

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(dienst.subprocess, "run", fake)
    return liste


@pytest.fixture
def server(aufrufe):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dienst.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def anfrage(port, methode, pfad, body=None, header=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request(methode, pfad, body=body, headers=header or {})
    r = c.getresponse()
    roh = r.read()
    c.close()
    try:
        return r.status, json.loads(roh)
    except ValueError:  # 403 und 404 kommen als HTML
        return r.status, None


def setze(port, wert, header=HEADER):
    return anfrage(port, "POST", "/lautstaerke", json.dumps({"wert": wert}), header)


def test_ohne_header_abgewiesen_und_nichts_geaendert(server, aufrufe):
    status, _ = setze(server, 50, header={})
    assert status == 403
    assert aufrufe == []
    assert dienst.lautstaerke_stand.stellung == 60


def test_gueltiger_wert_stellt_um_und_wird_gemerkt(server, aufrufe, tmp_path):
    status, antwort = setze(server, 100)
    assert (status, antwort) == (200, {"wert": 100})
    assert aufrufe == [pytest.approx(1.0, abs=1e-3)]
    assert dienst.lautstaerke_stand.stellung == 100
    assert (tmp_path / "lautstaerke").read_text().strip() == "100"


def test_null_ist_stumm(server, aufrufe):
    assert setze(server, 0)[0] == 200
    assert aufrufe == [0.0]


def test_eins_ist_35_prozent(server, aufrufe):
    assert setze(server, 1)[0] == 200
    assert aufrufe == [pytest.approx(0.35, abs=1e-3)]


@pytest.mark.parametrize("wert", [-1, 101, 55.5, "50", None, True, [1]])
def test_ungueltiger_wert_wird_abgelehnt_und_aendert_nichts(
    server, aufrufe, tmp_path, wert
):
    status, _ = setze(server, wert)
    assert status == 400
    assert aufrufe == []
    assert dienst.lautstaerke_stand.stellung == 60
    assert not (tmp_path / "lautstaerke").exists()


def test_ohne_wert_und_mit_kaputtem_json_abgelehnt(server, aufrufe):
    assert anfrage(server, "POST", "/lautstaerke", "{}", HEADER)[0] == 400
    assert anfrage(server, "POST", "/lautstaerke", "{kaputt", HEADER)[0] == 400
    assert aufrufe == []


def test_lage_zeigt_die_stellung(server):
    setze(server, 73)
    status, lage = anfrage(server, "GET", "/lage")
    assert status == 200 and lage["lautstaerke"] == 73


def test_bridge_befehl_nimmt_denselben_weg(server, aufrufe, tmp_path):
    aktionen = Leitung().nachricht(json.dumps({"type": "lautstaerke", "wert": 1}))
    dienst.ausfuehren(aktionen)
    assert aufrufe == [pytest.approx(0.35, abs=1e-3)]
    assert dienst.lautstaerke_stand.stellung == 1
    assert (tmp_path / "lautstaerke").read_text().strip() == "1"
    # Der Schieber sieht die Änderung, die Elektra gemacht hat.
    assert anfrage(server, "GET", "/lage")[1]["lautstaerke"] == 1


def test_bridge_befehl_ueber_100_wird_auf_100_begrenzt(aufrufe):
    dienst.ausfuehren(
        Leitung().nachricht(json.dumps({"type": "lautstaerke", "wert": 140}))
    )
    assert aufrufe == [pytest.approx(1.0, abs=1e-3)]


def test_start_stellt_gemerkte_stellung_wieder_ein(aufrufe, tmp_path):
    (tmp_path / "lautstaerke").write_text("80\n")
    dienst.lautstaerke_stand.laden()
    dienst.lautstaerke_wiederherstellen(versuche=1, pause_s=0)
    assert aufrufe == [pytest.approx(0.35 + 0.65 * 79 / 99, abs=1e-3)]


def test_start_ohne_gemerkten_wert_nimmt_60(aufrufe):
    dienst.lautstaerke_stand.laden()
    dienst.lautstaerke_wiederherstellen(versuche=1, pause_s=0)
    assert aufrufe == [pytest.approx(0.35 + 0.65 * 59 / 99, abs=1e-3)]


def test_start_versucht_es_erneut_wenn_pipewire_noch_fehlt(monkeypatch, tmp_path):
    monkeypatch.setattr(dienst, "lautstaerke_stand", Lautstaerke(tmp_path / "l"))
    antworten = iter([1, 1, 0])

    class R:
        def __init__(self, code):
            self.returncode = code

    monkeypatch.setattr(dienst.subprocess, "run", lambda *a, **k: R(next(antworten)))
    dienst.lautstaerke_wiederherstellen(versuche=5, pause_s=0)
    assert next(antworten, None) is None  # genau drei Aufrufe, beim dritten klappte es


def lies_ereignisse(port, anzahl_lautstaerke, ausloeser=None):
    """Öffnet /ereignisse und sammelt die `lautstaerke`-Meldungen (#103). `ausloeser` läuft, sobald die erste da ist."""
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/ereignisse")
    r = c.getresponse()
    werte, art, ausgeloest = [], None, False
    while len(werte) < anzahl_lautstaerke:
        zeile = r.fp.readline().decode().strip()
        if zeile.startswith("event:"):
            art = zeile[6:].strip()
        elif zeile.startswith("data:") and art == "lautstaerke":
            werte.append(json.loads(zeile[5:])["wert"])
            if ausloeser and not ausgeloest:
                ausgeloest = True
                ausloeser()
    c.close()
    return werte


def test_neue_kiosk_seite_bekommt_den_stand_beim_verbinden(server):
    setze(server, 42)
    assert lies_ereignisse(server, 1) == [42]


def test_ereignis_nach_setzen_ueber_post(server):
    assert lies_ereignisse(server, 2, lambda: setze(server, 17)) == [60, 17]


def test_ereignis_nach_bridge_befehl(server):
    aktionen = Leitung().nachricht(json.dumps({"type": "lautstaerke", "wert": 5}))
    assert lies_ereignisse(server, 2, lambda: dienst.ausfuehren(aktionen)) == [60, 5]
