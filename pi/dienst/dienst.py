#!/usr/bin/env python3
"""Küchen-Dienst: Kiosk-Seite, Sprachweg zur rundfunk-Bridge und Ton (kuechen-display#15, rundfunk#128).

Ein Prozess, drei Aufgaben:
- liefert die Kiosk-Seite aus (pi/kiosk) auf http://localhost:8080/ und schickt ihr
  Ereignisse als Server-Sent Events an /ereignisse;
- verbindet sich als Netz-Gerät mit der Bridge (Vertrag: rundfunk/src/rundfunk/netzgeraet.py),
  schickt das Mikrofon (XVF3800, ALSA hw, Kanal 0) und spielt Elektras Stimme ab;
- nimmt Gesten vom Kameradienst (pi/gesten) an und reicht sie an Seite und Bridge weiter.

Ein Gespräch beginnt mit einem Tipp auf die Figur (Festlegung 8.11.2026); das Aktivierungswort
kommt später. Ton geht an den Standardausgang von PipeWire (beim Tischtest Bluetooth).

Anleitung: docs/stimme-und-geste.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websockets
from vertrag import (
    RAHMEN_BYTES,
    RAHMEN_PROBEN,
    RATE,
    ROH_BYTES,
    XVF_KANAELE,
    Aktion,
    Leitung,
    kanal,
)

PORT = 8080
SEITE = os.environ.get(
    "KIOSK_VERZEICHNIS", os.path.expanduser("~/kuechen-display/kiosk")
)
BRUECKE = os.environ.get("BRUECKE_URL", "ws://raspi-agent.local:8000/geraet/netz")
GERAET = os.environ.get("GERAET_ID", "kueche")
TOKEN_DATEI = Path(
    os.environ.get(
        "TOKEN_DATEI", os.path.expanduser("~/.config/kuechen-display/geraete-token")
    )
)
MIKRO = os.environ.get("MIKRO_GERAET", "hw:CARD=L16K6Ch,DEV=0")
# Apps, die die Seite wirklich öffnen kann. Noch keine; ohne Eintrag bietet die Bridge
# Elektra das Werkzeug app_oeffnen gar nicht erst an.
APPS: list[str] = []
RAHMEN_S = RAHMEN_PROBEN / RATE

log = logging.getLogger("dienst")
leitung = Leitung()
leitung_sperre = threading.Lock()
abonnenten: list[queue.Queue] = []
abonnenten_sperre = threading.Lock()
wiedergabe: queue.Queue[bytes] = queue.Queue()
schleife: asyncio.AbstractEventLoop | None = None
ws = None  # aktuelle Leitung zur Bridge oder None


# --- Seite --------------------------------------------------------------------
def an_seite(art: str, daten: dict) -> int:
    """Ereignis an alle offenen Seiten; gibt die Zahl der Empfänger zurück."""
    with abonnenten_sperre:
        for q in abonnenten:
            q.put((art, daten))
        return len(abonnenten)


def an_bruecke(nachricht: dict | bytes) -> bool:
    if ws is None or schleife is None:
        return False
    daten = (
        nachricht
        if isinstance(nachricht, bytes)
        else json.dumps(nachricht, ensure_ascii=False)
    )
    asyncio.run_coroutine_threadsafe(_senden(daten), schleife)
    return True


async def _senden(daten) -> None:
    try:
        if ws is not None:
            await ws.send(daten)
    except websockets.ConnectionClosed:
        pass


def ausfuehren(aktionen: list[Aktion]) -> None:
    for a in aktionen:
        if a.art == "senden":
            if not an_bruecke(a.daten):
                log.warning("Keine Leitung zur Bridge, %s nicht gesendet", a.daten)
                an_seite("verbindung", {"da": False})
        elif a.art == "verwerfen":
            verwerfen()
        elif a.art == "lautstaerke":
            lautstaerke(a.daten["wert"])
        elif a.art == "anzeige":
            daten = dict(a.daten)
            art = daten.pop("ereignis")
            if art == "zustand":
                log.info("Zustand: %s", daten["wert"])
            if an_seite(art, daten) == 0 and art == "befehl":
                # Ohne offene Seite kann nichts den Befehl ausführen: laut zurückmelden.
                an_bruecke(
                    {
                        "type": "quittung",
                        "id": daten["id"],
                        "ok": False,
                        "fehler": "Die Anzeige ist nicht offen.",
                    }
                )


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path != "/ereignisse":
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        q: queue.Queue = queue.Queue()
        with abonnenten_sperre:
            abonnenten.append(q)
        # Neue Seite: gleich den aktuellen Stand, damit nach einem Neuladen nichts falsch steht.
        q.put(("verbindung", {"da": ws is not None}))
        q.put(("zustand", {"wert": leitung.zustand}))
        try:
            while True:
                try:
                    art, e = q.get(timeout=15)
                    self.wfile.write(
                        f"event: {art}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n".encode()
                    )
                except queue.Empty:
                    self.wfile.write(b": still\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with abonnenten_sperre:
                abonnenten.remove(q)

    def do_POST(self):
        laenge = int(self.headers.get("Content-Length", 0))
        roh = self.rfile.read(laenge).decode(errors="replace")
        try:
            daten = json.loads(roh) if roh else {}
        except json.JSONDecodeError:
            daten = {}
        if self.path == "/tipp":
            with leitung_sperre:
                ausfuehren(leitung.tipp())
        elif self.path == "/stopp":
            with leitung_sperre:
                ausfuehren(leitung.stopp())
        elif self.path == "/quittung":
            an_bruecke(
                {
                    "type": "quittung",
                    **{k: daten[k] for k in ("id", "ok", "fehler") if k in daten},
                }
            )
        elif self.path == "/geste":
            # Vom Kameradienst: an die Seite (Blättern, Rückmeldung) und Stopp an die Bridge.
            log.info("Geste: %s", daten)
            an_seite("geste", daten)
            if daten.get("art") == "stopp":
                with leitung_sperre:
                    ausfuehren(leitung.stopp())
        elif self.path == "/hinweis":
            # Text in der Zeile der Seite, z. B. Anweisungen beim Messen der Gesten.
            an_seite("text", {"rolle": "hinweis", "text": str(daten.get("text", ""))})
        elif self.path == "/hand":
            an_seite("hand", daten)
        elif self.path == "/messung":
            log.info("Messung Seite: %s", roh)
        else:
            self.send_error(404)
            return
        self.send_response(204)
        self.end_headers()


# --- Ton ----------------------------------------------------------------------
def verwerfen() -> None:
    n = 0
    while True:
        try:
            wiedergabe.get_nowait()
            n += 1
        except queue.Empty:
            break
    if n:
        log.info("Wiedergabe: %d Rahmen verworfen", n)


def lautstaerke(wert: int) -> None:
    log.info("Lautstärke: %d", wert)
    subprocess.run(
        ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{wert / 100:.2f}"],
        check=False,
    )


def wiedergabe_schleife() -> None:
    """Schreibt im 60-ms-Takt an pw-cat: Elektras Stimme oder Stille.

    Die Stille hält den Ausgang wach. Bluetooth verschluckt sonst beim Aufwachen
    rund eine Sekunde (Tischtest 8.11.2026). Im Takt schreiben heißt: Es staut sich
    nichts in der Pipe, Verwerfen wirkt sofort.
    """
    stille = bytes(RAHMEN_BYTES)
    while True:
        prozess = subprocess.Popen(
            [
                "pw-cat",
                "--playback",
                "--raw",
                "--format",
                "s16",
                "--rate",
                str(RATE),
                "--channels",
                "1",
                "--latency",
                "60ms",
                "--media-role",
                "Assistant",
                "-",
            ],
            stdin=subprocess.PIPE,
        )
        takt = time.monotonic()
        try:
            while True:
                try:
                    rahmen = wiedergabe.get_nowait()
                except queue.Empty:
                    rahmen = stille
                prozess.stdin.write(rahmen)
                prozess.stdin.flush()
                takt += RAHMEN_S
                pause = takt - time.monotonic()
                if pause > 0:
                    time.sleep(pause)
                elif pause < -0.5:
                    takt = time.monotonic()  # nach einem Hänger nicht hinterherhetzen
        except (BrokenPipeError, OSError):
            log.warning("pw-cat beendet (Code %s), starte neu", prozess.poll())
            time.sleep(1)


def mikro_schleife() -> None:
    """Liest den XVF3800 direkt über ALSA (PipeWire reicht im Profil 2.1 nur zwei Kanäle durch)
    und schickt Kanal 0, solange das Mikrofon offen ist."""
    while True:
        prozess = subprocess.Popen(
            [
                "arecord",
                "-q",
                "-D",
                MIKRO,
                "-f",
                "S16_LE",
                "-r",
                str(RATE),
                "-c",
                str(XVF_KANAELE),
                "-t",
                "raw",
            ],
            stdout=subprocess.PIPE,
        )
        log.info("Mikrofon %s offen", MIKRO)
        while True:
            roh = prozess.stdout.read(ROH_BYTES)
            if len(roh) < ROH_BYTES:
                break
            if leitung.mikro_offen:
                an_bruecke(kanal(roh))
        log.warning("arecord beendet (Code %s), starte neu", prozess.wait())
        time.sleep(2)


# --- Bridge -------------------------------------------------------------------
async def bruecke_schleife() -> None:
    global ws
    token = TOKEN_DATEI.read_text().strip()
    warte = 1
    while True:
        try:
            async with websockets.connect(
                BRUECKE,
                additional_headers={
                    "Authorization": f"Bearer {token}",
                    "Device-Id": GERAET,
                },
                max_size=None,
            ) as verbindung:
                await verbindung.send(json.dumps({"type": "hallo", "apps": APPS}))
                ws = verbindung
                warte = 1
                log.info("Mit der Bridge verbunden: %s als %s", BRUECKE, GERAET)
                an_seite("verbindung", {"da": True})
                async for nachricht in verbindung:
                    if isinstance(nachricht, bytes):
                        if len(nachricht) == RAHMEN_BYTES:
                            wiedergabe.put(nachricht)
                        else:
                            log.warning(
                                "Wiedergabe-Rahmen mit %d Bytes verworfen",
                                len(nachricht),
                            )
                    else:
                        with leitung_sperre:
                            aktionen = leitung.nachricht(nachricht)
                        if not aktionen:
                            log.warning(
                                "Nachricht der Bridge ohne Wirkung: %s", nachricht[:200]
                            )
                        ausfuehren(aktionen)
        except (OSError, websockets.WebSocketException) as fehler:
            log.warning("Bridge nicht erreichbar oder getrennt: %s", fehler)
        ws = None
        with leitung_sperre:
            ausfuehren(leitung.getrennt())
        an_seite("verbindung", {"da": False})
        await asyncio.sleep(warte)
        warte = min(warte * 2, 30)


def bruecke_faden() -> None:
    global schleife
    schleife = asyncio.new_event_loop()
    try:
        schleife.run_until_complete(bruecke_schleife())
    except Exception:
        log.exception("Bridge-Anbindung ausgefallen")
        os._exit(1)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout
    )
    if not TOKEN_DATEI.exists():
        log.error("Token fehlt: %s (siehe docs/stimme-und-geste.md)", TOKEN_DATEI)
        sys.exit(1)
    for ziel in (bruecke_faden, wiedergabe_schleife, mikro_schleife):
        threading.Thread(target=ziel, daemon=True, name=ziel.__name__).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=SEITE))
    server.daemon_threads = True
    log.info("Kiosk-Seite aus %s auf http://localhost:%d/", SEITE, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
