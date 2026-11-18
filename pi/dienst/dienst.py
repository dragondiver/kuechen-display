#!/usr/bin/env python3
"""Küchen-Dienst: Kiosk-Seite, Sprachweg zur rundfunk-Bridge und Ton (kuechen-display#15, rundfunk#128).

Ein Prozess, vier Aufgaben:
- liefert die Kiosk-Seite aus (pi/kiosk) auf http://localhost:8080/ und schickt ihr
  Ereignisse als Server-Sent Events an /ereignisse;
- verbindet sich als Netz-Gerät mit der Bridge (Vertrag: rundfunk/src/rundfunk/netzgeraet.py),
  schickt das Mikrofon (XVF3800, ALSA hw, Kanal 0) und spielt Elektras Stimme ab;
- nimmt Gesten vom Kameradienst (pi/gesten) an und reicht sie an Seite und Bridge weiter;
- holt Wetter und Termine aus Home Assistant und schickt sie der Seite (docs/datenweg.md).

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
from datetime import datetime
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import websockets
from diktat import (
    MAX_S,
    MIN_S,
    Aufnahme,
    DiktatFehler,
    braucht_modell,
    suchbegriff,
    transkribieren,
)
from hass import HomeAssistant, termine_karte, wetter_karte
from konfig import geheimnis
from statisch import StatischOhneCache
from vertrag import (
    RAHMEN_BYTES,
    RAHMEN_PROBEN,
    RATE,
    ROH_BYTES,
    XVF_KANAELE,
    Ablage,
    Aktion,
    Leitung,
    abgelaufene_melden,
    kanal,
    quittung_leiten,
)
from wach import Wach
from weckwort import NICHTS, VOR, WECKEN, ZURUECK, Lauscher, Weckwort, erkenner_laden

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
# Apps, die die Kiosk-Seite per app_oeffnen öffnen kann; jede braucht eine Kachel mit
# data-app=<name> in pi/kiosk/index.html (#70). Ohne Eintrag bietet die Bridge Elektra das
# Werkzeug gar nicht erst an.
APPS: list[str] = ["spotify", "rezepte"]
RAHMEN_S = RAHMEN_PROBEN / RATE
# Home Assistant (docs/datenweg.md). Ohne HA_TOKEN läuft der Dienst weiter, nur ohne Wetter
# und Termine.
HA_URL = os.environ.get("HA_URL", "http://raspi-agent.local:8123")
HA_TOKEN_DATEI = Path(
    os.environ.get(
        "HA_TOKEN_DATEI", os.path.expanduser("~/.config/kuechen-display/ha-token")
    )
)
WETTER_ENTITAET = os.environ.get("WETTER_ENTITAET", "weather.stuttgart_schn")
TEMPERATUR_SENSOR = os.environ.get(
    "TEMPERATUR_SENSOR", "sensor.stuttgart_schn_temperatur"
)
ORT = os.environ.get("ORT", "Kornwestheim")
# Kalender der CalDAV-Integration, durch Komma getrennt; die Reihenfolge gibt die Farbe des
# Punkts (Festlegung 15.11.2026 in #15: Family und Abfall).
KALENDER = [
    k.strip()
    for k in os.environ.get("KALENDER", "calendar.family,calendar.abfall").split(",")
    if k.strip()
]
ZONE = ZoneInfo(os.environ.get("ZEITZONE", "Europe/Berlin"))
# Termine alle zwei Minuten (Wunsch 15.11.2026), das Wetter weiter alle zehn.
TERMINE_TAKT_S = 120
WETTER_TAKT_S = 600

log = logging.getLogger("dienst")
leitung = Leitung()
leitung_sperre = threading.Lock()
abonnenten: list[queue.Queue] = []
abonnenten_sperre = threading.Lock()
wiedergabe: queue.Queue[bytes] = queue.Queue()
schleife: asyncio.AbstractEventLoop | None = None
# Letzter Stand je Ereignisart, den eine neu geöffnete Seite sofort bekommt (z. B. "wetter").
letzte_daten: dict[str, dict] = {}
ws = None  # aktuelle Leitung zur Bridge oder None
# Befehle für eine offene App ohne Kiosk-Seite; die Rückweg-Erweiterung holt sie über /lage (#70).
ablage = Ablage()
ablage_sperre = threading.Lock()
GESCHUETZT = {
    "/tipp",
    "/stopp",
    "/quittung",
    "/diktat/start",
    "/diktat/stopp",
    "/diktat/ergebnis",
    "/video",
    "/rezept",
}
# Was das Display wach hält (#48): Elektra und Video; der Schlafwächter fragt über GET /wach.
wach = Wach()
wach_sperre = threading.Lock()
# Diktat ins Suchfeld (#70), ohne Elektra; der Schlüssel kommt aus dem 1Password-Environment.
aufnahme = Aufnahme(RATE)
aufnahme_sperre = threading.Lock()
DIKTAT_MODELL = os.environ.get("DIKTAT_MODELL", "gpt-transcribe")
DIKTAT_TEXT_MODELL = os.environ.get("DIKTAT_TEXT_MODELL", "gpt-6-luna")
OPENAI_DATEI = Path(os.path.expanduser("~/.config/kuechen-display/openai-key"))
# Weckwort „Weiter“/„Zurück“ bei offenem Rezept (#89, docs/stimme-und-geste.md). Schalter: WECKWORT=an|aus
# in der Unit (kuechen-dienst.service).
WECKWORT_MODELL = Path(
    os.environ.get(
        "WECKWORT_MODELL",
        os.path.expanduser("~/kuechen-display/modelle/vosk-model-small-de-0.15"),
    )
)
weckwort = Weckwort()
weckwort_sperre = threading.Lock()
lauscher: Lauscher | None = None
lokal_zaehler = 0


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
            if art != "befehl":
                an_seite(art, daten)
                continue
            # Ist eine App vorn, hängt an /ereignisse höchstens noch die verlassene Kiosk-Seite,
            # deren Abbruch der Dienst erst beim nächsten Schreiben merkt. Dann holt die
            # Rückweg-Erweiterung den Befehl ab, sonst die Kiosk-Seite.
            with ablage_sperre:
                app_vorn = ablage.app_vorn(time.monotonic())
            if app_vorn or an_seite(art, daten) == 0:
                log.info("Befehl %s für die App bereitgelegt", daten.get("name"))
                befehl_ablegen(daten)


def befehl_ablegen(befehl: dict) -> None:
    with ablage_sperre:
        ablage.ablegen(befehl, time.monotonic())
    zeitgeber = threading.Timer(Ablage.FRIST_S + 0.5, ablage_aufraeumen)
    zeitgeber.daemon = True
    zeitgeber.start()


def ablage_aufraeumen() -> None:
    """Befehle, die keine App abgeholt hat: laut zurückmelden. Bei einem lokalen Befehl (Weckwort)
    ins Journal, denn die Bridge kennt seine Nummer nicht."""
    try:
        with ablage_sperre:
            alt = ablage.abgelaufen(time.monotonic())
    except Exception:
        log.exception("Ablage aufräumen")
        return
    bridge, journal = abgelaufene_melden(alt)
    for zeile in journal:
        log.warning("%s", zeile)
    for nachricht in bridge:
        an_bruecke(nachricht)


class Handler(StatischOhneCache):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/lage":
            return self.lage()
        if urlsplit(self.path).path == "/wach":
            return self.wach_lage()
        if self.path != "/ereignisse":
            return super().do_GET()
        with ablage_sperre:
            offen = ablage.kiosk_vorn(time.monotonic())
        # Die Kiosk-Seite ist vorn, also ist kein Rezept offen (die Erweiterung läuft nur in https-Seiten).
        with weckwort_sperre:
            weckwort.rezept.zuruecksetzen()
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
        for befehl in offen:
            log.info("Befehl %s an die neue Kiosk-Seite", befehl.get("name"))
            q.put(("befehl", befehl))
        for art, e in list(letzte_daten.items()):
            q.put((art, e))
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

    def lage(self) -> None:
        """Für die Rückweg-Erweiterung in einer App: Elektras Zustand und ein wartender Befehl."""
        jetzt = time.monotonic()
        with ablage_sperre:
            ablage.app_meldet(jetzt)
            befehl = ablage.abholen(jetzt)
        if befehl:
            log.info("Befehl %s von der App abgeholt", befehl.get("name"))
        roh = json.dumps(
            {
                "zustand": leitung.zustand,
                "verbunden": ws is not None,
                "befehl": befehl,
                "diktat": aufnahme.aktiv,
                "weckwort": weckwort_hoert(),
                "wort": weckwort.gehoert,
            },
            ensure_ascii=False,
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def wach_lage(self) -> None:
        """Für den Schlafwächter (pi/schlafen): Darf das Display ausgehen? Er meldet dabei mit
        ?dunkel=0|1, ob es dunkel ist, und bekommt zurück, ob ein Weckwort geweckt haben will (#89)."""
        jetzt = time.monotonic()
        dunkel = parse_qs(urlsplit(self.path).query).get("dunkel", [None])[0]
        # Mit ?dunkel= setzt der Aufruf Zustand: wie bei den POST-Wegen nur mit eigenem Header, den eine
        # fremde Seite im Kiosk nicht ohne Vorabfrage mitschicken kann. Das reine Lesen bleibt offen.
        if dunkel is not None and self.headers.get("X-Kuechen") != "1":
            self.send_error(403)
            return
        with weckwort_sperre:
            if dunkel in ("0", "1"):
                weckwort.anzeige.melden(dunkel == "1", jetzt)
            elif dunkel is not None:
                log.warning("/wach: dunkel=%r ist weder 0 noch 1", dunkel[:20])
            start, zaehler = weckwort.start, weckwort.wecken_zaehler
        with wach_sperre:
            gruende = wach.gruende(leitung.zustand, jetzt)
        roh = json.dumps(
            {
                "haelt": bool(gruende),
                "gruende": gruende,
                "start": start,
                "wecken": zaehler,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def antworte(self, code: int, daten: dict) -> None:
        roh = json.dumps(daten, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def diktat(self, schritt: str, daten: dict) -> None:
        """start: Aufnahme an, Antwort mit ihrer Nummer. stopp: Aufnahme aus (Tipp).
        ergebnis {id}: wartet, bis diese Aufnahme endet (Ruhe, Tipp, Frist), und gibt den
        erkannten Text zurück; für eine veraltete Nummer sofort leeren Text."""
        if schritt == "stopp":
            with aufnahme_sperre:
                aufnahme.beenden("Tipp")
            return self.antworte(200, {})
        schluessel = geheimnis("OPENAI_API_KEY", OPENAI_DATEI)
        if not schluessel:
            return self.antworte(
                503, {"fehler": "Kein OpenAI-Schlüssel auf dem Display."}
            )
        if schritt == "start":
            with aufnahme_sperre:
                nummer = aufnahme.start()
            log.info("Diktat: Aufnahme %d läuft", nummer)
            return self.antworte(200, {"id": nummer})
        if not aufnahme.fertig.wait(timeout=MAX_S + 1):
            with aufnahme_sperre:
                aufnahme.beenden("Zeit abgelaufen")  # Mikrofon lieferte nichts mehr
        with aufnahme_sperre:
            if daten.get("id") != aufnahme.nummer:
                return self.antworte(200, {"text": ""})
            ton = aufnahme.nehmen()
            grund, boden, spitze = aufnahme.grund, aufnahme.boden_db, aufnahme.spitze()
        dauer = aufnahme.sekunden(ton)
        # Nur Längen und Pegel ins Journal, nicht was gesucht wurde. Die Pegel sind zum
        # Nachstellen der Schwellen in diktat.py.
        werte = f"{dauer:.1f} s Ton, Ende: {grund}, Boden {boden:.0f} dB, Spitze {spitze:.0f} dB"
        if dauer < MIN_S:
            log.info("Diktat: %s, zu kurz", werte)
            return self.antworte(200, {"text": ""})
        beginn = time.monotonic()
        try:
            text = transkribieren(ton, RATE, schluessel, DIKTAT_MODELL)
        except DiktatFehler as fehler:
            log.warning("Diktat: %s; %s", werte, fehler)
            return self.antworte(502, {"fehler": "Die Spracherkennung ging nicht."})
        erkannt = time.monotonic() - beginn
        # Ein ganzer Satz („spiel mir was von Queen“) gehört nicht ins Suchfeld. Das Modell
        # zieht den Suchbegriff heraus; geht das schief, bleibt der erkannte Text.
        begriff, wie = text, "kurz"
        if braucht_modell(text):
            try:
                begriff, wie = (
                    suchbegriff(text, schluessel, DIKTAT_TEXT_MODELL),
                    "Modell",
                )
            except DiktatFehler as fehler:
                wie = "Modell ging nicht"
                log.warning("Diktat: Suchbegriff: %s", fehler)
            if wie == "Modell" and begriff == text:
                wie = "Modell, unverändert"
        log.info(
            "Diktat: %s, %.1f s Erkennung, %.1f s gesamt, %d → %d Zeichen (%s)",
            werte,
            erkannt,
            time.monotonic() - beginn,
            len(text),
            len(begriff),
            wie,
        )
        self.antworte(200, {"text": begriff})

    def do_POST(self):
        laenge = int(self.headers.get("Content-Length", 0))
        roh = self.rfile.read(laenge).decode(errors="replace")
        try:
            daten = json.loads(roh) if roh else {}
        except json.JSONDecodeError:
            daten = {}
        # Was Mikrofon oder Elektra auslöst, nur mit eigenem Header. Eine fremde Webseite im Kiosk
        # kann ihn nicht ohne Vorabfrage (OPTIONS, beantwortet der Dienst nicht) mitschicken;
        # ohne ihn könnte sie per no-cors-POST das Mikrofon öffnen (verifier zu #71).
        if self.path in GESCHUETZT and self.headers.get("X-Kuechen") != "1":
            self.send_error(403)
            return
        if self.path == "/weg":
            # sendBeacon der Kiosk-Seite beim Verlassen (kein eigener Header möglich)
            with ablage_sperre:
                ablage.kiosk_geht()
            self.send_response(204)
            self.end_headers()
            return
        if self.path == "/video":
            # Die Rückweg-Erweiterung meldet die <video>-Elemente der offenen Seite (#48).
            with wach_sperre:
                vorher = wach.video_laeuft(time.monotonic())
                probleme = wach.video_melden(daten.get("videos"), time.monotonic())
                jetzt_an = wach.video_laeuft(time.monotonic())
            for problem in probleme:
                log.warning("Video-Meldung: %s", problem)
            if jetzt_an != vorher:
                log.info(
                    "Video: %s", "läuft, hält das Display wach" if jetzt_an else "aus"
                )
            self.send_response(204)
            self.end_headers()
            return
        if self.path == "/rezept":
            # Die Rückweg-Erweiterung meldet alle 2 s, ob ein Rezept von mise-en-place offen ist (#89).
            offen = daten.get("offen")
            if not isinstance(offen, bool):
                log.warning("Rezept-Meldung ohne offen=true/false: %s", roh[:80])
                self.send_error(400)
                return
            with weckwort_sperre:
                vorher = weckwort.rezept.offen
                weckwort.rezept.melden(offen, time.monotonic())
            if offen != vorher:
                log.info("Rezept: %s", "offen" if offen else "zu")
            self.send_response(204)
            self.end_headers()
            return
        if self.path in ("/diktat/start", "/diktat/stopp", "/diktat/ergebnis"):
            return self.diktat(self.path.rsplit("/", 1)[1], daten)
        if self.path == "/tipp":
            with leitung_sperre:
                ausfuehren(leitung.tipp())
        elif self.path == "/stopp":
            with leitung_sperre:
                ausfuehren(leitung.stopp())
        elif self.path == "/quittung":
            nachricht, zeile = quittung_leiten(daten)
            if nachricht:
                an_bruecke(nachricht)
            if zeile:
                log.info("%s", zeile)
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


# --- Weckwort -----------------------------------------------------------------
WORT_TEXT = {VOR: "weiter", ZURUECK: "zurück"}  # fürs Journal: das gesagte Wort


def weckwort_belegt() -> bool:
    """Elektra, ein Diktat oder Wiedergabe sind dran: Dann wertet die Erkennung nichts aus."""
    return (
        leitung.zustand != "aus"
        or leitung.mikro_offen
        or aufnahme.aktiv
        or not wiedergabe.empty()
    )


def weckwort_hoert() -> bool:
    """Bekommt die Erkennung gerade Ton? Zeigt die Rückweg-Leiste an. Ohne Erkennung nie."""
    if lauscher is None or not lauscher.bereit:
        return False
    with weckwort_sperre:
        return weckwort.hoert(weckwort_belegt(), time.monotonic())


def weckwort_text(text: str) -> None:
    """Läuft im Faden der Erkennung: ein Ergebnis auswerten und ausführen."""
    jetzt = time.monotonic()
    with weckwort_sperre:
        treffer = weckwort.wort(text, weckwort_belegt(), jetzt)
        zaehler = weckwort.wecken_zaehler
    if treffer is None or treffer.aktion == NICHTS:
        return
    if treffer.aktion == WECKEN:
        log.info(
            "Weckwort „%s“: wecken (%s), Zähler %d",
            WORT_TEXT[treffer.wort],
            treffer.grund,
            zaehler,
        )
        return
    global lokal_zaehler
    lokal_zaehler += 1  # nur dieser Faden schreibt
    richtung = "vor" if treffer.aktion == VOR else "zurueck"
    with wach_sperre:
        wach.wort_gehoert(jetzt)
    log.info("Weckwort „%s“: blättern %s", WORT_TEXT[treffer.wort], richtung)
    befehl_ablegen(
        {
            "id": f"lokal-{lokal_zaehler}",
            "name": "rezeptschritt",
            "argumente": {"richtung": richtung},
        }
    )


def weckwort_starten() -> None:
    """Schalter WECKWORT=an|aus; Vosk und Modell werden erst hier geladen. Jeder Ausgang ins
    Journal, auch der stille Fall „aus“."""
    global lauscher
    schalter = os.environ.get("WECKWORT", "an").strip().lower()
    if schalter == "aus":
        log.info("Weckwort aus (WECKWORT=aus in der Unit)")
        return
    if schalter != "an":
        log.error(
            "WECKWORT=%r geht nicht (an oder aus), das Weckwort bleibt aus", schalter
        )
        return
    erkenner, fehler = erkenner_laden(WECKWORT_MODELL, RATE)
    if erkenner is None:
        log.error("Weckwort nicht verfügbar: %s", fehler)
        return
    lauscher = Lauscher(erkenner, weckwort_text)
    threading.Thread(target=lauscher.lauf, daemon=True, name="weckwort").start()
    log.info(
        "Weckwort bereit (Modell %s), hört bei offenem Rezept zu", WECKWORT_MODELL.name
    )


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
            ton = kanal(roh)
            if leitung.mikro_offen:
                an_bruecke(ton)
            if aufnahme.aktiv:
                with aufnahme_sperre:
                    aufnahme.rahmen(ton)
            if lauscher is not None:
                lauscher.rahmen(ton, weckwort_hoert())
        log.warning("arecord beendet (Code %s), starte neu", prozess.wait())
        time.sleep(2)


# --- Daten aus Home Assistant -------------------------------------------------
class Abruf:
    """Ein Abruf aus Home Assistant mit eigenem Fehlerstand: Schlägt er fehl, behält die Seite
    den letzten Stand; der Fehler steht einmal im Journal, bis es wieder geht."""

    def __init__(self, was: str) -> None:
        self.was = was
        self.gestoert = False

    def __call__(self, holen):
        try:
            ergebnis = holen()
        except (OSError, ValueError) as fehler:
            if not self.gestoert:
                log.warning("%s: Home Assistant antwortet nicht: %s", self.was, fehler)
            self.gestoert = True
            return None
        if self.gestoert:
            log.info("%s: Home Assistant antwortet wieder", self.was)
        self.gestoert = False
        return ergebnis


def daten_schleife() -> None:
    """Holt alle zwei Minuten die Termine und alle zehn Minuten das Wetter und schickt beides
    der Seite."""
    token = geheimnis("HA_TOKEN", HA_TOKEN_DATEI)
    if token is None:
        log.warning(
            "Kein Wetter, keine Termine: HA_TOKEN fehlt (siehe docs/datenweg.md)"
        )
        return
    ha = HomeAssistant(HA_URL, token)
    wetter_abruf, termine_abruf = Abruf("Wetter"), Abruf("Termine")
    gemeldet = None
    fehlt_gemeldet: list[str] = []
    wetter_zuletzt = None
    while True:
        karte = None
        if wetter_zuletzt is None or time.monotonic() - wetter_zuletzt >= WETTER_TAKT_S:
            wetter_zuletzt = time.monotonic()
            karte = wetter_abruf(
                lambda: wetter_karte(ha, WETTER_ENTITAET, TEMPERATUR_SENSOR, ORT)
            )
        if karte is not None:
            if karte["unbekannt"] and karte["zustand"] != gemeldet:
                log.warning(
                    "Wetter: %s liefert '%s', dafür gibt es kein Bild",
                    WETTER_ENTITAET,
                    karte["zustand"],
                )
            gemeldet = karte["zustand"] if karte["unbekannt"] else None
            if karte != {**letzte_daten.get("wetter", {}), "stand": karte["stand"]}:
                log.info(
                    "Wetter: %s, %s, Bild %s",
                    karte["temperatur"],
                    karte["zustand"],
                    karte["bild"],
                )
            letzte_daten["wetter"] = karte
            an_seite("wetter", karte)

        termine = termine_abruf(lambda: termine_karte(ha, KALENDER, datetime.now(ZONE)))
        if termine is not None:
            fehlt = termine.pop("fehlt")
            if fehlt and fehlt != fehlt_gemeldet:
                log.warning("Termine: Home Assistant kennt %s nicht", ", ".join(fehlt))
            fehlt_gemeldet = fehlt
            alt = letzte_daten.get("termine", {})
            if {**termine, "stand": 0} != {**alt, "stand": 0}:
                log.info(
                    "Termine: heute %d, morgen %d, Woche %d",
                    len(termine["heute"]),
                    len(termine["morgen"]),
                    sum(len(t["termine"]) for t in termine["woche"]),
                )
            letzte_daten["termine"] = termine
            an_seite("termine", termine)
        time.sleep(TERMINE_TAKT_S)


# --- Bridge -------------------------------------------------------------------
async def bruecke_schleife() -> None:
    global ws
    token = geheimnis("RUNDFUNK_GERAETE_TOKEN", TOKEN_DATEI)
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
    if geheimnis("RUNDFUNK_GERAETE_TOKEN", TOKEN_DATEI) is None:
        log.error("RUNDFUNK_GERAETE_TOKEN fehlt (siehe docs/stimme-und-geste.md)")
        sys.exit(1)
    weckwort_starten()
    for ziel in (bruecke_faden, wiedergabe_schleife, mikro_schleife, daten_schleife):
        threading.Thread(target=ziel, daemon=True, name=ziel.__name__).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=SEITE))
    server.daemon_threads = True
    log.info("Kiosk-Seite aus %s auf http://localhost:%d/", SEITE, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
