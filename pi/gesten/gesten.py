#!/usr/bin/env python3
"""Gestendienst und Webserver für den Kiosk des Küchen-Displays (kuechen-display#2, #15).

Ein Prozess, zwei Aufgaben:
- liefert die Kiosk-Seite aus (pi/kiosk, Wetterbilder) auf http://localhost:8080/
- liest die Kamera, erkennt mit MediaPipe Hand und Handform, macht daraus Gesten
  (geste.py) und schickt sie als Server-Sent Events an /ereignisse.

Bilder verlassen das Gerät nicht und werden nicht gespeichert (Festlegung 19.10.2026).
Der Server hört nur auf localhost.

POST /messung nimmt die Bildraten-Messung der Seite (?messen=1) an und schreibt sie ins Journal.
Anleitung: docs/kiosk-und-gesten.md
"""

import json
import logging
import os
import queue
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from geste import Beobachtung, Gestenerkenner

PORT = 8080
SEITE = os.environ.get(
    "KIOSK_VERZEICHNIS", os.path.expanduser("~/kuechen-display/kiosk")
)
MODELL = os.environ.get(
    "GESTEN_MODELL", os.path.expanduser("~/kuechen-display/gesture_recognizer.task")
)
BILD = (640, 360)
# Kamera mit 30 Bildern/s und kurzer Belichtung, damit eine schnell bewegte Hand nicht verwischt.
# Ausgewertet wird, so schnell die Erkennung kommt (ca. 20/s), immer das neueste Bild.
BILDER_PRO_S = 30

log = logging.getLogger("gesten")
abonnenten: list[queue.Queue] = []
abonnenten_sperre = threading.Lock()
statistik = {"bilder": 0, "mit_hand": 0, "erkennung_ms": 0.0}


def verteile(ereignis: dict, art: str = "geste") -> None:
    if art == "geste":
        log.info("Geste: %s", ereignis)
    with abonnenten_sperre:
        for q in abonnenten:
            q.put((art, ereignis))


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
        try:
            while True:
                try:
                    art, e = q.get(timeout=15)
                    self.wfile.write(
                        f"event: {art}\ndata: {json.dumps(e)}\n\n".encode()
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
        if self.path != "/messung":
            self.send_error(404)
            return
        laenge = int(self.headers.get("Content-Length", 0))
        log.info("Messung Seite: %s", self.rfile.read(laenge).decode(errors="replace"))
        self.send_response(204)
        self.end_headers()


def kamera_schleife() -> None:
    import libcamera
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    from picamera2 import Picamera2

    kamera = Picamera2()
    kamera.configure(
        kamera.create_video_configuration(
            main={"size": BILD, "format": "RGB888"},
            # Die Kamera liegt beim Tischtest kopfüber; im Gehäuse ggf. anpassen.
            transform=libcamera.Transform(hflip=1, vflip=1),
            controls={
                "FrameDurationLimits": (int(1e6 / BILDER_PRO_S),) * 2,
                "AeExposureMode": libcamera.controls.AeExposureModeEnum.Short,
            },
        )
    )
    kamera.start()
    erkenner_mp = vision.GestureRecognizer.create_from_options(
        vision.GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=MODELL),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
        )
    )
    gesten = Gestenerkenner()
    t0 = time.monotonic()
    while True:
        bild = kamera.capture_array()  # BGR
        t = time.monotonic()
        erg = erkenner_mp.recognize_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=bild[:, :, ::-1].copy()),
            int((t - t0) * 1000),
        )
        statistik["bilder"] += 1
        statistik["erkennung_ms"] += (time.monotonic() - t) * 1000
        n = statistik["bilder"]
        if not erg.hand_landmarks:
            gesten.keine_hand(t)
            if n % 5 == 0:
                verteile({}, "hand")
            continue
        statistik["mit_hand"] += 1
        punkte = erg.hand_landmarks[0]
        # Handmitte: Handgelenk und die Grundgelenke der Finger
        mitte = [punkte[i] for i in (0, 5, 9, 13, 17)]
        x = sum(p.x for p in mitte) / len(mitte)
        y = sum(p.y for p in mitte) / len(mitte)
        kategorie = erg.gestures[0][0] if erg.gestures and erg.gestures[0] else None
        ereignis = gesten.beobachte(
            Beobachtung(
                t,
                x,
                y,
                kategorie.category_name if kategorie else "",
                kategorie.score if kategorie else 0.0,
            )
        )
        if n % 3 == 0:
            # Für die Debug-Anzeige der Seite: was die Kamera gerade sieht.
            verteile(
                {
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "form": kategorie.category_name if kategorie else "",
                    "sicher": round(kategorie.score, 2) if kategorie else 0,
                },
                "hand",
            )
        if ereignis:
            verteile(ereignis)


def statistik_schleife() -> None:
    """Jede Minute Bildrate und Rechenzeit ins Journal, für die Messung auf dem Pi."""
    cpu0, t0 = os.times(), time.monotonic()
    while True:
        time.sleep(60)
        cpu1, t1 = os.times(), time.monotonic()
        n = statistik["bilder"]
        cpu = (cpu1.user - cpu0.user + cpu1.system - cpu0.system) / (t1 - t0) * 100
        log.info(
            "Kamera: %.1f Bilder/s, davon mit Hand %d, Erkennung im Mittel %.0f ms, CPU %.0f %% eines Kerns",
            n / (t1 - t0),
            statistik["mit_hand"],
            statistik["erkennung_ms"] / n if n else 0,
            cpu,
        )
        statistik.update(bilder=0, mit_hand=0, erkennung_ms=0.0)
        cpu0, t0 = cpu1, t1


def kamera_wache() -> None:
    """Fällt die Kamera aus, laut abbrechen; systemd startet neu."""
    try:
        kamera_schleife()
    except Exception:
        log.exception("Kamera oder Erkennung ausgefallen")
        os._exit(1)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout
    )
    threading.Thread(target=kamera_wache, daemon=True).start()
    threading.Thread(target=statistik_schleife, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=SEITE))
    server.daemon_threads = True
    log.info("Kiosk-Seite aus %s auf http://localhost:%d/", SEITE, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
