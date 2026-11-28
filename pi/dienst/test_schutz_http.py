"""Header-Pflicht (X-Kuechen) für /geste, /hinweis, /hand, /messung und /weg (#114)."""

import http.client
import threading
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
