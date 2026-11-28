"""POST /tipp ohne Leitung zur Bridge (#50): die Seite bekommt den Hinweis, es beginnt nichts."""

import http.client
import json
import logging
import queue
import threading
from http.server import ThreadingHTTPServer

import dienst
import pytest


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(dienst, "ws", None)
    monkeypatch.setattr(dienst, "leitung", dienst.Leitung())
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dienst.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_tipp_ohne_bridge_schickt_hinweis_und_startet_nichts(server):
    seite: queue.Queue = queue.Queue()
    dienst.abonnenten.append(seite)
    try:
        c = http.client.HTTPConnection("127.0.0.1", server, timeout=5)
        c.request("POST", "/tipp", body="{}", headers={"X-Kuechen": "1"})
        c.getresponse().read()
        c.close()
    finally:
        dienst.abonnenten.remove(seite)
    ereignisse = []
    while not seite.empty():
        ereignisse.append(seite.get_nowait())
    assert ereignisse == [("hinweis", {"text": "Elektra ist gerade nicht erreichbar"})]
    assert dienst.leitung.zustand == "aus"


def post(port, body=None, headers=None, roh_header=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.putrequest("POST", "/lautstaerke")
    c.putheader("X-Kuechen", "1")
    for k, v in (roh_header or {}).items():
        c.putheader(k, v)
    if body is not None and not roh_header:
        c.putheader("Content-Length", str(len(body)))
    c.endheaders(body)
    antwort = c.getresponse()
    daten = antwort.read()
    c.close()
    return antwort.status, daten


@pytest.mark.parametrize("body", [b"[]", b"1", b'"x"', b"null", b"[1,2]"])
def test_body_ohne_json_objekt_ergibt_400(server, body):
    status, _ = post(server, body)
    assert status == 400


@pytest.mark.parametrize("laenge", ["abc", "-1", "1.5", ""])
def test_ungueltige_content_length_ergibt_400(server, laenge):
    status, _ = post(server, roh_header={"Content-Length": laenge})
    assert status == 400


def test_zu_grosser_body_ergibt_413_ohne_ihn_zu_lesen(server):
    status, _ = post(
        server, roh_header={"Content-Length": str(dienst.POST_MAX_BYTES + 1)}
    )
    assert status == 413


def test_body_an_der_grenze_wird_noch_gelesen(server):
    fuell = "a" * (dienst.POST_MAX_BYTES - 40)
    body = json.dumps({"videos": [], "x": fuell}).encode()
    assert len(body) <= dienst.POST_MAX_BYTES
    c = http.client.HTTPConnection("127.0.0.1", server, timeout=5)
    c.request("POST", "/video", body=body, headers={"X-Kuechen": "1"})
    antwort = c.getresponse()
    antwort.read()
    c.close()
    assert antwort.status == 204


def test_gueltige_anfrage_bleibt_unveraendert(server):
    status, daten = post(server, b'{"wert": "kaputt"}')
    assert status == 400 and b"wert muss" in daten


@pytest.mark.parametrize("roh", ["NaN", "Infinity", "1e400"])
def test_nachricht_der_bridge_mit_nicht_endlichem_wert_laesst_die_schleife_leben(
    monkeypatch, roh
):
    monkeypatch.setattr(dienst, "leitung", dienst.Leitung())
    dienst.nachricht_verarbeiten('{"type":"lautstaerke","wert":' + roh + "}")


def test_unerwartete_ausnahme_bei_einer_nachricht_wird_geloggt_und_geschluckt(
    monkeypatch, caplog
):
    def kaputt(aktionen):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(dienst, "leitung", dienst.Leitung())
    monkeypatch.setattr(dienst, "ausfuehren", kaputt)
    with caplog.at_level(logging.WARNING, logger="dienst"):
        dienst.nachricht_verarbeiten('{"type":"zustand","wert":"sprechen"}')
    assert [
        r for r in caplog.records if r.exc_info and "RuntimeError" in repr(r.exc_info)
    ]
