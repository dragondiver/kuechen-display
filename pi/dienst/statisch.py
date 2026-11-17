"""Auslieferung der Kiosk-Dateien ohne Abhängigkeiten (Test in test_statisch.py).

SimpleHTTPRequestHandler schickt nur Last-Modified. Chromium hält die Datei dann nach seiner
Faustregel (ein Zehntel der Zeit seit der Änderung) lange für frisch und fragt nach einem Deploy
nicht nach; am 17.11.2026 zeigte der Kiosk so die alte Startseite, auch nach einem Neustart.
`no-cache` heißt: jedes Mal nachfragen. Ist die Datei gleich, bleibt es bei 304 ohne Inhalt.
"""

from http.server import SimpleHTTPRequestHandler


class StatischOhneCache(SimpleHTTPRequestHandler):
    _statisch = False

    def send_head(self):
        # Nur der Zweig für Dateien; die JSON-Antworten und der Ereignisstrom setzen ihre eigenen Header.
        self._statisch = True
        try:
            return super().send_head()
        finally:
            self._statisch = False

    def end_headers(self):
        if self._statisch:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()
