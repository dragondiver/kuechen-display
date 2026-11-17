import threading
import urllib.error
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer

import pytest
from statisch import StatischOhneCache


class Handler(StatischOhneCache):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/lage":
            # wie dienst.py: eigene Antwort mit eigenem Header
            self.send_response(200)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"{}")
            return
        return super().do_GET()


@pytest.fixture
def adresse(tmp_path):
    (tmp_path / "index.html").write_text("<p>neu</p>")
    (tmp_path / "bild.png").write_bytes(b"\x89PNG")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(tmp_path))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def kopf(url, **header):
    with urllib.request.urlopen(urllib.request.Request(url, headers=header)) as a:
        return a.headers.get_all("Cache-Control")


@pytest.mark.parametrize("pfad", ["/", "/index.html", "/bild.png"])
def test_dateien_haben_no_cache(adresse, pfad):
    assert kopf(adresse + pfad) == ["no-cache"]


def test_nachfrage_bleibt_304_moeglich(adresse):
    with urllib.request.urlopen(adresse + "/") as a:
        stand = a.headers["Last-Modified"]
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(
            urllib.request.Request(adresse + "/", headers={"If-Modified-Since": stand})
        )
    assert e.value.code == 304


def test_eigene_antworten_behalten_no_store(adresse):
    assert kopf(adresse + "/lage") == ["no-store"]


def test_fehlende_datei_404_ohne_absturz(adresse):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(adresse + "/gibts-nicht")
    assert e.value.code == 404
