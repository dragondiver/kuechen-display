"""POST /tipp ohne Leitung zur Bridge (#50): die Seite bekommt den Hinweis, es beginnt nichts."""

import http.client
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
