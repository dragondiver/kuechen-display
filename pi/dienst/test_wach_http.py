"""GET /wach: Mit ?dunkel= setzt der Aufruf Zustand und verlangt den Header X-Kuechen (#92)."""

import http.client
import threading
from http.server import ThreadingHTTPServer

import dienst
import pytest


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dienst.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def get(port, pfad, header=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", pfad, headers=header or {})
    r = c.getresponse()
    r.read()
    c.close()
    return r.status


def test_dunkel_ohne_header_wird_abgewiesen(server):
    assert get(server, "/wach?dunkel=1") == 403
    assert get(server, "/wach?dunkel=0") == 403


def test_dunkel_mit_header_wird_angenommen(server):
    assert get(server, "/wach?dunkel=1", {"X-Kuechen": "1"}) == 200


def test_reines_lesen_braucht_keinen_header(server):
    assert get(server, "/wach") == 200
