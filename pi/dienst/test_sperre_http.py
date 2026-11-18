"""POST /sperren (#82): Header-Pflicht, Sperre aus, Erfolg, Fehlschlag."""

import http.client
import queue
import threading
import urllib.error
from http.server import ThreadingHTTPServer

import dienst
import pytest
from sperre import Sperre
from test_hass import FakeHA

HELFER = "input_boolean.termine_privat"


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(dienst, "sperre", Sperre(HELFER))
    monkeypatch.setattr(dienst, "letzte_daten", {})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dienst.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def sperren(port, header=None):
    seite: queue.Queue = queue.Queue()
    dienst.abonnenten.append(seite)
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("POST", "/sperren", body="{}", headers=header or {})
        status = c.getresponse().status
        c.close()
    finally:
        dienst.abonnenten.remove(seite)
    ereignisse = []
    while not seite.empty():
        ereignisse.append(seite.get_nowait())
    return status, ereignisse


def test_ohne_header_abgewiesen(server, monkeypatch):
    monkeypatch.setattr(dienst, "ha_verbindung", FakeHA({}))
    status, ereignisse = sperren(server)
    assert status == 403 and ereignisse == []
    assert dienst.sperre.gesperrt is False


def test_sperre_aus_tut_nichts(server, monkeypatch):
    monkeypatch.setattr(dienst, "sperre", Sperre(""))
    monkeypatch.setattr(dienst, "ha_verbindung", FakeHA({}))
    status, ereignisse = sperren(server, {"X-Kuechen": "1"})
    assert status == 404 and ereignisse == []


def test_erfolg_zeigt_das_schloss_sofort(server, monkeypatch):
    ha = FakeHA({"/api/services/input_boolean/turn_on": []})
    monkeypatch.setattr(dienst, "ha_verbindung", ha)
    status, ereignisse = sperren(server, {"X-Kuechen": "1"})
    assert status == 204
    assert ereignisse == [("termine", {"gesperrt": True, "sperrbar": True})]
    assert dienst.sperre.gesperrt is True
    assert dienst.letzte_daten["termine"] == {"gesperrt": True, "sperrbar": True}


def test_fehlschlag_bleibt_frei_und_zeigt_hinweis(server, monkeypatch):
    class Kaputt(FakeHA):
        def _anfrage(self, *a, **k):
            raise urllib.error.URLError("weg")

    monkeypatch.setattr(dienst, "ha_verbindung", Kaputt({}))
    status, ereignisse = sperren(server, {"X-Kuechen": "1"})
    assert status == 204
    assert ereignisse == [("hinweis", {"text": "Sperren hat nicht geklappt"})]
    assert dienst.sperre.gesperrt is False
    assert "termine" not in dienst.letzte_daten


def test_ohne_token_zeigt_hinweis_und_bleibt_frei(server, monkeypatch):
    monkeypatch.setattr(dienst, "ha_verbindung", None)
    _, ereignisse = sperren(server, {"X-Kuechen": "1"})
    assert ereignisse == [("hinweis", {"text": "Sperren hat nicht geklappt"})]
    assert dienst.sperre.gesperrt is False
