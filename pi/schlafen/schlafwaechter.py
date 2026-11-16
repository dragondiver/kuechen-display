#!/usr/bin/env python3
"""Schlafwächter: schaltet das Küchen-Display nach Ruhe aus und beim Tippen wieder an (kuechen-display#48).

Ein Prozess, als Dienst `kuechen-schlafen` (Python-Standardbibliothek, kein venv):
- swayidle meldet, ob labwc Eingaben sieht (Touch, Tastatur, VNC). Das ist die Quelle für „Ruhe“.
- Der Küchen-Dienst (GET /wach) sagt, ob ein Video oder Elektra wach hält.
- Die Entscheidung trifft ruhe.py (reine Logik, getestet). Hier steht nur, was am Gerät passiert.

Ausschalten: Helligkeit merken, Beleuchtung auf 0 und/oder Ausgang aus (wlopm), und den Touch
sperren (EVIOCGRAB auf das Goodix-Gerät). Beim ersten Tipp wird das Display angeschaltet; der
Touch bleibt gesperrt, bis der Finger wieder oben ist. labwc würde die Berührung sonst auch bei
ausgeschaltetem Ausgang an das Fenster geben.

Fällt etwas aus, bleibt das Display an: swayidle weg, Küchen-Dienst weg, kein Touch-Gerät zum
Sperren, wlopm ohne Erfolg. Stirbt der Wächter selbst, schaltet ExecStopPost mit --an ein.

Aufruf: schlafwaechter.py [--konfig DATEI]   Dienst
        schlafwaechter.py --an               Display einschalten (Notausgang, ExecStopPost)
Anleitung: docs/schlafen.md
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import selectors
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from ruhe import (
    EVENT_BYTES,
    SCHLAFEN,
    WECKEN,
    Konfig,
    Ruhe,
    WeckTipp,
    ereignisse_zerlegen,
    konfig_lesen,
    touch_geraet_finden,
)

log = logging.getLogger("schlafen")

# Muss derselbe Name sein wie deviceName in pi/kiosk/labwc-rc.xml (ein Test prüft das).
TOUCH_NAME = "10-0014 Goodix Capacitive TouchScreen"
AUSGANG = "DSI-1"
BACKLIGHT = Path(
    os.environ.get("BACKLIGHT_VERZEICHNIS", "/sys/class/backlight/10-0045")
)
ZUSTAND = Path(
    os.environ.get("SCHLAFEN_ZUSTAND", "/run/kuechen-schlafen/helligkeit")
)  # RuntimeDirectory der Unit: übersteht einen Neustart des Dienstes, nicht des Pi
WACH_URL = os.environ.get("WACH_URL", "http://127.0.0.1:8080/wach")
GERAETELISTE = Path("/proc/bus/input/devices")
EVIOCGRAB = 0x40044590  # _IOW('E', 0x90, int)
WACH_TAKT_S = 5.0
NEU_VERSUCH_S = 3.0  # Einschalten, das nicht klappte, alle 3 s wiederholen
SWAYIDLE_PAUSE_S = 5.0


# --- Anzeige: Beleuchtung und Ausgang ----------------------------------------------------
class Anzeige:
    """Schaltet Beleuchtung und Ausgang. Die Helligkeit vor dem Ausschalten wird gemerkt, auch
    auf der Platte, damit ein neu gestarteter Wächter sie zurückgeben kann."""

    def __init__(
        self,
        aus_weg: str,
        backlight: Path = BACKLIGHT,
        zustand: Path = ZUSTAND,
        ausgang: str = AUSGANG,
        lauf=subprocess.run,
    ) -> None:
        self.aus_weg = aus_weg
        self.backlight = backlight
        self.zustand = zustand
        self.ausgang = ausgang
        self.lauf = lauf

    @property
    def mit_backlight(self) -> bool:
        return self.aus_weg in ("beides", "backlight")

    @property
    def mit_ausgang(self) -> bool:
        return self.aus_weg in ("beides", "ausgang")

    def _zahl(self, name: str) -> int | None:
        try:
            return int((self.backlight / name).read_text().strip())
        except (OSError, ValueError) as fehler:
            log.error("Beleuchtung: %s nicht lesbar: %s", self.backlight / name, fehler)
            return None

    def _helligkeit_setzen(self, wert: int) -> bool:
        try:
            (self.backlight / "brightness").write_text(f"{wert}\n")
            return True
        except OSError as fehler:
            log.error("Beleuchtung: %d nicht gesetzt: %s", wert, fehler)
            return False

    def _wlopm(self, schalter: str) -> bool:
        try:
            ergebnis = self.lauf(
                ["wlopm", schalter, self.ausgang],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as fehler:
            log.error("wlopm %s %s: %s", schalter, self.ausgang, fehler)
            return False
        if ergebnis.returncode != 0:
            log.error(
                "wlopm %s %s: Code %s, %s",
                schalter,
                self.ausgang,
                ergebnis.returncode,
                (ergebnis.stderr or "").strip(),
            )
            return False
        return True

    def _merken(self) -> bool:
        """Helligkeit vor dem Ausschalten festhalten. Ohne gemerkten Wert wird nicht abgedunkelt:
        Zurückgeben ließe sich dann nur der Höchstwert."""
        hell = self._zahl("brightness")
        if hell is None:
            return False
        if hell == 0 and self.zustand.exists():
            return True  # schon dunkel, der gemerkte Wert gilt weiter
        if hell == 0:
            log.error(
                "Beleuchtung steht schon auf 0 und nichts ist gemerkt: nicht abgedunkelt"
            )
            return False
        try:
            self.zustand.parent.mkdir(parents=True, exist_ok=True)
            self.zustand.write_text(f"{hell}\n")
        except OSError as fehler:
            log.error("Helligkeit nicht gemerkt (%s): %s", self.zustand, fehler)
            return False
        return True

    def aus(self) -> bool:
        """True, wenn mindestens ein Weg geklappt hat. Klappt keiner, bleibt alles wie es war."""
        ergebnisse = []
        if self.mit_backlight:
            if self._merken():
                ergebnisse.append(self._helligkeit_setzen(0))
            else:
                ergebnisse.append(False)
        if self.mit_ausgang:
            ergebnisse.append(self._wlopm("--off"))
        if not any(ergebnisse):
            return False
        if not all(ergebnisse):
            log.warning("Ausschalten nur teilweise gelungen (aus_weg=%s)", self.aus_weg)
        return True

    def an(self) -> bool:
        """True, wenn alles gelungen ist, sonst loggt es und der Aufrufer versucht es wieder."""
        ok = True
        if self.mit_ausgang:
            ok = self._wlopm("--on") and ok
        if self.mit_backlight:
            ok = self._helligkeit_zurueck() and ok
        return ok

    def _helligkeit_zurueck(self) -> bool:
        try:
            wert = int(self.zustand.read_text().strip())
        except FileNotFoundError:
            wert = None
        except (OSError, ValueError) as fehler:
            log.error("Gemerkte Helligkeit unlesbar (%s): %s", self.zustand, fehler)
            wert = None
        if wert is None:
            jetzt = self._zahl("brightness")
            if jetzt is None:
                return False
            if jetzt > 0:
                return True
            # Dunkel und nichts gemerkt: im Zweifel an.
            wert = self._zahl("max_brightness") or 255
            log.warning("Beleuchtung steht auf 0, nichts gemerkt: setze %d", wert)
        if not self._helligkeit_setzen(wert):
            return False
        self.zustand.unlink(missing_ok=True)
        return True


# --- Touch sperren -----------------------------------------------------------------------
class Touch:
    """Das Goodix-Gerät, solange das Display schläft: allein gelesen, für labwc gesperrt."""

    def __init__(self, geraete_text: str | None = None) -> None:
        self.fd: int | None = None
        self.rest = b""
        self.geraete_text = geraete_text

    def sperren(self) -> bool:
        try:
            text = self.geraete_text or GERAETELISTE.read_text()
        except OSError as fehler:
            log.error("Touch: %s nicht lesbar: %s", GERAETELISTE, fehler)
            return False
        pfad = touch_geraet_finden(text, TOUCH_NAME)
        if pfad is None:
            log.error("Touch: kein Gerät mit dem Namen '%s'", TOUCH_NAME)
            return False
        try:
            fd = os.open(pfad, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as fehler:
            log.error("Touch: %s nicht zu öffnen (Gruppe input?): %s", pfad, fehler)
            return False
        try:
            fcntl.ioctl(fd, EVIOCGRAB, 1)
        except OSError as fehler:
            os.close(fd)
            log.error("Touch: %s nicht zu sperren: %s", pfad, fehler)
            return False
        self.fd = fd
        self.rest = b""
        return True

    def lesen(self) -> list[tuple[int, int, int]]:
        if self.fd is None:
            return []
        try:
            roh = os.read(self.fd, EVENT_BYTES * 64)
        except BlockingIOError:
            return []
        except OSError as fehler:
            log.error("Touch: Lesen schlug fehl: %s", fehler)
            return []
        ereignisse, self.rest = ereignisse_zerlegen(self.rest + roh)
        return ereignisse

    def freigeben(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)  # schließt auch die Sperre
            except OSError as fehler:
                log.error("Touch: Schließen schlug fehl: %s", fehler)
            self.fd = None


# --- Küchen-Dienst fragen ----------------------------------------------------------------
def wach_fragen(url: str = WACH_URL) -> tuple[bool, list[str]]:
    """Hält etwas wach? Antwortet der Dienst nicht oder unlesbar, gilt: ja (im Zweifel an)."""
    try:
        with urllib.request.urlopen(url, timeout=2) as antwort:
            daten = json.load(antwort)
        if not isinstance(daten, dict) or not isinstance(daten.get("haelt"), bool):
            raise TypeError(f"unerwartete Antwort: {str(daten)[:100]}")
        gruende = [str(g) for g in daten.get("gruende", [])]
        return daten["haelt"], gruende
    except (OSError, ValueError, TypeError) as fehler:
        return True, [f"dienst: {fehler}"]


# --- Zusammenspiel -----------------------------------------------------------------------
class Waechter:
    """Verbindet Ruhe (Entscheidung) mit Anzeige und Touch (Wirkung). Ohne Schleife, damit die
    Schritte mit Attrappen getestet werden können (test_schlafwaechter.py)."""

    def __init__(self, konfig: Konfig, anzeige, touch_neu, jetzt: float) -> None:
        self.konfig = konfig
        self.anzeige = anzeige
        self.touch_neu = touch_neu  # () -> Touch-Objekt mit sperren/lesen/freigeben
        self.ruhe = Ruhe(konfig.ruhe_s, jetzt)
        self.touch = None
        self.tipp: WeckTipp | None = None
        self.an_offen = False  # Einschalten ist nicht gelungen und wird wiederholt
        self.an_versuch = 0.0

    # Aktionen aus der Entscheidung
    def ausfuehren(self, aktion: str, jetzt: float, grund: str = "") -> None:
        if aktion == SCHLAFEN:
            self.schlafen(jetzt)
        elif aktion == WECKEN:
            self.wecken(jetzt, grund or "Anlass unbekannt")

    def schlafen(self, jetzt: float) -> None:
        touch = self.touch_neu()
        if not touch.sperren():
            log.error(
                "Display bleibt an: der Touch lässt sich nicht sperren, der erste Tipp würde sonst durchgehen"
            )
            self.ruhe.schlafen_misslungen(jetzt)
            return
        if not self.anzeige.aus():
            touch.freigeben()
            log.error("Display bleibt an: Ausschalten ist nicht gelungen")
            self.ruhe.schlafen_misslungen(jetzt)
            return
        self.touch, self.tipp = touch, WeckTipp()
        self.ruhe.eingeschlafen()
        log.info("Display aus nach %d s Ruhe", self.konfig.ruhe_s)

    def wecken(self, jetzt: float, grund: str) -> None:
        if self.anzeige.an():
            self.an_offen = False
        else:
            self.an_offen = True
            self.an_versuch = jetzt
            log.error(
                "Einschalten nicht gelungen, nächster Versuch in %.0f s", NEU_VERSUCH_S
            )
        self.ruhe.aufgewacht(jetzt)
        log.info("Display an: %s", grund)
        # Den Touch erst freigeben, wenn der Finger oben ist (touch_lesen). Gab es keine
        # Berührung (Elektra, Eingabe von VNC), gibt es nichts zu verschlucken.
        if self.tipp is None or self.tipp.beginn is None:
            self.touch_freigeben()

    def touch_freigeben(self) -> None:
        if self.touch is not None:
            self.touch.freigeben()
        self.touch = self.tipp = None

    # Ereignisse
    def touch_lesen(self, jetzt: float) -> None:
        if self.touch is None or self.tipp is None:
            return
        for art, code, wert in self.touch.lesen():
            ergebnis = self.tipp.ereignis(art, code, wert, jetzt)
            if ergebnis.weck and self.ruhe.schlaeft:
                self.ruhe.beruehrt(jetzt)
                self.wecken(jetzt, "Berührung (verschluckt)")
            if ergebnis.frei:
                self.touch_freigeben()
                return

    def takt(self, jetzt: float) -> None:
        if self.tipp is not None and self.tipp.tick(jetzt).frei:
            log.warning(
                "Berührung hängt länger als %.0f s: Touch wird freigegeben",
                WeckTipp.MAX_S,
            )
            self.touch_freigeben()
        if self.an_offen and jetzt - self.an_versuch >= NEU_VERSUCH_S:
            self.an_versuch = jetzt
            self.an_offen = not self.anzeige.an()
            if self.an_offen:
                log.error("Einschalten weiter ohne Erfolg")
        aktion = self.ruhe.tick(jetzt)
        if aktion == WECKEN:
            grund = "Eingabe" if self.ruhe.eingabe_laeuft else "etwas hält wach"
            self.ausfuehren(WECKEN, jetzt, grund)
        else:
            self.ausfuehren(aktion, jetzt)

    def swayidle_zeile(self, zeile: str, jetzt: float) -> None:
        if zeile == "AKTIV":
            if self.ruhe.aktiv(jetzt) == WECKEN:
                self.ausfuehren(WECKEN, jetzt, "Eingabe (nicht Touch)")
        elif zeile == "IDLE":
            self.ruhe.ruhig(jetzt)
        else:
            log.warning("Unerwartete Zeile von swayidle: %r", zeile[:100])

    def wach_antwort(self, haelt: bool, jetzt: float, gruende: list[str]) -> None:
        if self.ruhe.halt(jetzt, haelt) == WECKEN:
            self.ausfuehren(WECKEN, jetzt, "hält wach: " + ", ".join(gruende))

    def swayidle_fehlt(self, jetzt: float) -> None:
        if self.ruhe.eingabe_unbekannt() == WECKEN:
            self.ausfuehren(WECKEN, jetzt, "swayidle fehlt")


# --- Schleife ----------------------------------------------------------------------------
def wayland_socket() -> Path:
    return Path(
        os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    ) / os.environ.get("WAYLAND_DISPLAY", "wayland-0")


def swayidle_starten() -> subprocess.Popen:
    return subprocess.Popen(
        ["swayidle", "-w", "timeout", "1", "echo IDLE", "resume", "echo AKTIV"],
        stdout=subprocess.PIPE,
    )


def lauf(konfig: Konfig) -> None:
    anzeige = Anzeige(konfig.aus_weg)
    beenden = []
    signal.signal(signal.SIGTERM, lambda *_: beenden.append(True))
    signal.signal(signal.SIGINT, lambda *_: beenden.append(True))

    # Ohne Wayland-Sitzung gibt es nichts zu schalten; nach dem Hochfahren dauert sie etwas.
    gemeldet = False
    while not wayland_socket().exists() and not beenden:
        if not gemeldet:
            log.info("Warte auf %s", wayland_socket())
            gemeldet = True
        time.sleep(2)
    # Ein Wächter, der nach einem Absturz startet, gibt ein dunkles Display zurück.
    if not anzeige.an():
        log.error("Beim Start war das Einschalten nicht ganz gelungen")

    w = Waechter(konfig, anzeige, Touch, time.monotonic())
    sel = selectors.DefaultSelector()
    idle: subprocess.Popen | None = None
    idle_puffer = b""
    idle_neu = 0.0
    wach_zuletzt = -WACH_TAKT_S
    wach_stand: tuple[bool, tuple[str, ...]] | None = None
    touch_fd = None
    try:
        while not beenden:
            jetzt = time.monotonic()
            if idle is None and jetzt >= idle_neu:
                try:
                    idle = swayidle_starten()
                    sel.register(idle.stdout, selectors.EVENT_READ, "idle")
                    idle_puffer = b""
                    log.info("swayidle läuft (pid %d)", idle.pid)
                except OSError as fehler:
                    log.error("swayidle nicht zu starten: %s", fehler)
                    idle, idle_neu = None, jetzt + SWAYIDLE_PAUSE_S
                    w.swayidle_fehlt(jetzt)
            if idle is not None and idle.poll() is not None:
                log.error(
                    "swayidle beendet (Code %s): Display bleibt an, neuer Start",
                    idle.returncode,
                )
                sel.unregister(idle.stdout)
                idle.stdout.close()
                idle, idle_neu = None, jetzt + SWAYIDLE_PAUSE_S
                w.swayidle_fehlt(jetzt)
            # Der Touch wird nur gelesen, solange das Display schläft.
            neu_fd = w.touch.fd if w.touch is not None else None
            if neu_fd != touch_fd:
                if touch_fd is not None:
                    sel.unregister(touch_fd)
                if neu_fd is not None:
                    sel.register(neu_fd, selectors.EVENT_READ, "touch")
                touch_fd = neu_fd

            for key, _ in sel.select(timeout=1.0):
                jetzt = time.monotonic()
                if key.data == "idle":
                    roh = os.read(key.fd, 4096)
                    if not roh:
                        continue  # swayidle ist weg; der nächste Durchlauf merkt es
                    idle_puffer += roh
                    *zeilen, idle_puffer = idle_puffer.split(b"\n")
                    for zeile in zeilen:
                        w.swayidle_zeile(zeile.decode(errors="replace").strip(), jetzt)
                elif key.data == "touch":
                    w.touch_lesen(jetzt)

            jetzt = time.monotonic()
            if jetzt - wach_zuletzt >= WACH_TAKT_S:
                wach_zuletzt = jetzt
                haelt, gruende = wach_fragen()
                stand = (haelt, tuple(gruende))
                if stand != wach_stand:
                    log.info(
                        "Wach halten: %s", ", ".join(gruende) if haelt else "nichts"
                    )
                    wach_stand = stand
                w.wach_antwort(haelt, jetzt, gruende)
            w.takt(jetzt)
    finally:
        log.info("Beende: Display einschalten")
        w.touch_freigeben()
        anzeige.an()
        if idle is not None:
            idle.terminate()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout
    )
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--konfig", type=Path, default=Path(__file__).with_name("schlafen.conf")
    )
    ap.add_argument("--an", action="store_true", help="Display einschalten und beenden")
    args = ap.parse_args()

    try:
        text = args.konfig.read_text()
    except OSError as fehler:
        log.error(
            "Konfiguration %s nicht lesbar (%s), es gelten die Standardwerte",
            args.konfig,
            fehler,
        )
        text = ""
    konfig, probleme = konfig_lesen(text)
    for p in probleme:
        log.error("%s: %s", args.konfig.name, p)

    if args.an:
        return 0 if Anzeige(konfig.aus_weg).an() else 1
    log.info("Start: Ruhe %d s, Aus-Weg %s", konfig.ruhe_s, konfig.aus_weg)
    lauf(konfig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
