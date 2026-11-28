"""Header-Pflicht (X-Kuechen) für /geste, /hinweis, /hand, /messung und /weg (#114) und für GET /lage (#120)."""

import http.client
import json
import threading
import time
from http.server import ThreadingHTTPServer

import dienst
import pytest

HEADER = {"X-Kuechen": "1"}
PFADE = ["/geste", "/hinweis", "/hand", "/messung", "/weg"]


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dienst.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def post(port, pfad, header=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", pfad, body="{}", headers=header or {})
    r = c.getresponse()
    r.read()
    c.close()
    return r.status


@pytest.mark.parametrize("pfad", PFADE)
def test_ohne_header_403(server, pfad):
    assert post(server, pfad) == 403


@pytest.mark.parametrize("pfad", PFADE)
def test_mit_header_wie_bisher(server, pfad):
    assert post(server, pfad, HEADER) == 204


def test_ohne_header_kein_seiteneffekt(server, monkeypatch):
    gesendet = []
    monkeypatch.setattr(dienst, "an_seite", lambda *a: gesendet.append(a))
    assert post(server, "/hinweis") == 403
    assert post(server, "/hinweis", HEADER) == 204
    assert len(gesendet) == 1


def get(port, pfad, header=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", pfad, headers=header or {})
    r = c.getresponse()
    roh = r.read()
    c.close()
    return r.status, roh


def test_lage_ohne_header_403_ohne_nebenwirkung(server):
    jetzt = time.monotonic()
    befehl = {"name": "rezeptschritt", "id": "lokal-1"}
    with dienst.ablage_sperre:
        dienst.ablage.app_zuletzt = None
        dienst.ablage.ablegen(befehl, jetzt)
    try:
        status, _ = get(server, "/lage")
        assert status == 403
        # Der Befehl liegt noch da, und keine App gilt als vorn.
        assert [b for _, b in dienst.ablage.befehle] == [befehl]
        assert dienst.ablage.app_zuletzt is None
        # Mit Header kommt er wie bisher heraus.
        status, roh = get(server, "/lage", HEADER)
        assert status == 200
        assert json.loads(roh)["befehl"] == befehl
        assert dienst.ablage.app_zuletzt is not None
    finally:
        with dienst.ablage_sperre:
            dienst.ablage.befehle.clear()
            dienst.ablage.app_zuletzt = None
