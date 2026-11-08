#!/usr/bin/env python3
"""Kameradienst des Küchen-Displays: Handgesten per MediaPipe (kuechen-display#2).

Liest die Kamera, erkennt Hand und Handform, macht daraus Gesten (geste.py) und meldet sie
per POST an den Küchen-Dienst (pi/dienst, http://127.0.0.1:8080/geste). Der reicht sie an
die Seite und, bei Stopp, an die Bridge weiter.

Bilder verlassen das Gerät nicht und werden nicht gespeichert (Festlegung 19.10.2026).
Die Kamera läuft nur, wenn dieser Dienst läuft; beim Tischtest nur zum Testen (8.11.2026).
Anleitung: docs/stimme-und-geste.md
"""

import json
import logging
import os
import queue
import sys
import threading
import time
import urllib.request

from geste import Beobachtung, Gestenerkenner, flache_hand, gestenhand, handmitte

DIENST = os.environ.get("DIENST_URL", "http://127.0.0.1:8080")
PUNKTE_MITSENDEN = os.environ.get("GESTEN_PUNKTE") == "1"
KOPFUEBER = int(os.environ.get("KAMERA_KOPFUEBER", "0"))
MODELL = os.environ.get(
    "GESTEN_MODELL", os.path.expanduser("~/kuechen-display/gesture_recognizer.task")
)
BILD = (640, 360)
SENSOR = (2304, 1296)
# Kamera mit 30 Bildern/s und kurzer Belichtung, damit eine schnell bewegte Hand nicht verwischt.
# Ausgewertet wird, so schnell die Erkennung kommt (ca. 20/s), immer das neueste Bild.
BILDER_PRO_S = 30

log = logging.getLogger("gesten")
statistik = {"bilder": 0, "mit_hand": 0, "erkennung_ms": 0.0}
ausgang: queue.Queue = queue.Queue(maxsize=50)


def verteile(ereignis: dict, art: str = "geste") -> None:
    """Nicht blockierend: Die Kamera-Schleife wartet nie auf den Dienst."""
    if art == "geste":
        log.info("Geste: %s", ereignis)
    try:
        ausgang.put_nowait((art, ereignis))
    except queue.Full:
        if art == "geste":
            log.warning("Dienst nimmt nichts an, Geste verworfen: %s", ereignis)


def sende_schleife() -> None:
    while True:
        art, ereignis = ausgang.get()
        anfrage = urllib.request.Request(
            f"{DIENST}/{art}",
            data=json.dumps(ereignis).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(anfrage, timeout=2).close()
        except OSError as fehler:
            if art == "geste":
                log.warning("Geste nicht zugestellt (%s): %s", fehler, ereignis)


def kamera_schleife() -> None:
    import libcamera
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    from picamera2 import Picamera2

    kamera = Picamera2()
    kamera.configure(
        kamera.create_video_configuration(
            main={"size": BILD, "format": "RGB888"},
            # Ohne Vorgabe wählt libcamera 1536x864, beim IMX708 ein Ausschnitt aus der Mitte.
            # 2304x1296 ist gebinnt und behält den vollen Weitwinkel (bis 56 Bilder/s).
            sensor={"output_size": SENSOR},
            # Kabel nach unten wie im Gehäuse: keine Drehung. KAMERA_KOPFUEBER=1 für Kabel oben.
            transform=libcamera.Transform(hflip=KOPFUEBER, vflip=KOPFUEBER),
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
            num_hands=2,
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
        nr = gestenhand(erg.hand_landmarks)
        punkte = erg.hand_landmarks[nr]
        x, y = handmitte(punkte)
        kategorie = (
            erg.gestures[nr][0] if len(erg.gestures) > nr and erg.gestures[nr] else None
        )
        ereignis = gesten.beobachte(
            Beobachtung(
                t,
                x,
                y,
                # Die eigene Regel ersetzt MediaPipes "Open_Palm" (geste.FLACH_AB).
                "Open_Palm" if flache_hand(punkte) else "",
                1.0,
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
                    # Nur zum Messen (GESTEN_PUNKTE=1): alle 21 Handpunkte.
                    **(
                        {"punkte": [[round(p.x, 3), round(p.y, 3)] for p in punkte]}
                        if PUNKTE_MITSENDEN
                        else {}
                    ),
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
    threading.Thread(target=sende_schleife, daemon=True).start()
    threading.Thread(target=statistik_schleife, daemon=True).start()
    kamera_wache()


if __name__ == "__main__":
    main()
