#!/usr/bin/env python3
"""Probe fürs Aktivierungswort „Elektra“ (kuechen-display#111): aufnehmen und auszählen.

Drei Befehle, Anleitung in docs/weckwort-probe.md:

  weckwort_probe.py rufe ORDNER      nimmt einzelne Rufe auf, jeder nach einem Ton (auf dem Pi)
  weckwort_probe.py abend ORDNER     nimmt die Küche ohne Ruf auf, in Stücken von 10 Minuten (auf dem Pi)
  weckwort_probe.py zaehlen MODELL   lässt ein openWakeWord-Modell über die Aufnahmen laufen (Pi oder Mac)

Aufgenommen wird wie im Küchen-Dienst: arecord am XVF3800, sechs Kanäle, davon Kanal 0, 16 kHz
(pi/dienst/vertrag.py). Der Dienst hält das Gerät fest, deshalb hält die Aufnahme ihn an und
startet ihn danach wieder. Solange zeigt das Display nichts Neues und Elektra hört nicht.

Aufnehmen braucht nur die Standardbibliothek. numpy und openwakeword lädt erst `zaehlen`.
Die Zähllogik ist reine Logik ohne Ton und Modell (test_weckwort_probe.py).
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile
import time
import wave
from array import array
from contextlib import contextmanager
from pathlib import Path

# Wie pi/dienst/vertrag.py; hier wiederholt, damit das Werkzeug ohne den Dienst-Ordner läuft.
RATE = 16000
XVF_KANAELE = 6
XVF_KANAL = 0
MIKRO = os.environ.get("MIKRO_GERAET", "hw:CARD=L16K6Ch,DEV=0")
DIENST = "kuechen-dienst"

# openWakeWord rechnet in Rahmen von 80 ms.
RAHMEN = 1280
RAHMEN_S = RAHMEN / RATE
SCHWELLEN = (0.3, 0.4, 0.5, 0.6, 0.7)
# Nach einem Auslöser zählt in dieser Zeit kein zweiter: Ein Ruf liegt über mehrere Rahmen
# hinweg über der Schwelle, und im Dienst wäre das Mikrofon dann ohnehin schon offen.
SPERRE_S = 2.0
# Stille hinter jedem einzelnen Ruf, damit ein Wort am Ende der Aufnahme noch ausgewertet wird.
NACHLAUF_S = 0.5
# Leiser als das ist eine Aufnahme vermutlich leer (falsches Gerät, Mikrofon stumm).
LEISE_DB = -50.0
STUECK_S = 600


class Abbruch(Exception):
    """Ein Fehler, der mit einem Satz für Florian endet statt mit einem Traceback."""


# --- reine Logik ---------------------------------------------------------------------------
def kanal0(roh: bytes, kanaele: int = XVF_KANAELE, kanal: int = XVF_KANAL) -> array:
    """Ein Kanal aus verschachteltem PCM16. Ein angebrochener Rahmen am Ende fällt weg."""
    proben = array("h")
    proben.frombytes(roh[: len(roh) - len(roh) % (2 * kanaele)])
    return proben[kanal::kanaele]


def pegel_db(proben: array) -> float:
    """Spitzenpegel in dBFS; -inf bei reiner Stille oder leerer Aufnahme."""
    spitze = max((abs(p) for p in proben), default=0)
    return 20 * math.log10(spitze / 32768) if spitze else float("-inf")


def rahmen(proben: array, groesse: int = RAHMEN):
    """Teilt in Rahmen fester Größe; der letzte wird mit Stille aufgefüllt."""
    for anfang in range(0, len(proben), groesse):
        stueck = proben[anfang : anfang + groesse]
        if len(stueck) < groesse:
            stueck.extend([0] * (groesse - len(stueck)))
        yield stueck


def treffer(hoechstwerte: list[float], schwelle: float) -> int:
    """Wie viele einzelne Rufe erkannt wären: höchster Wert der Aufnahme auf oder über der Schwelle."""
    return sum(1 for wert in hoechstwerte if wert >= schwelle)


def ausloeser(
    werte: list[float], schwelle: float, sperre: int
) -> list[tuple[int, float]]:
    """Auslöser in einer langen Aufnahme: (Rahmen, höchster Wert). Nach jedem zählt `sperre`
    Rahmen lang kein weiterer; der höchste Wert kommt aus dieser Zeit."""
    gefunden: list[tuple[int, float]] = []
    i = 0
    while i < len(werte):
        if werte[i] >= schwelle:
            gefunden.append((i, max(werte[i : i + max(sperre, 1)])))
            i += max(sperre, 1)
        else:
            i += 1
    return gefunden


def zahl(wert: float, stellen: int = 1) -> str:
    return f"{wert:.{stellen}f}".replace(".", ",")


def zeit_text(sekunden: float) -> str:
    """Stelle in einer Aufnahme als mm:ss."""
    ganz = int(sekunden)
    return f"{ganz // 60:02d}:{ganz % 60:02d}"


def rufe_tabelle(
    reihen: dict[str, list[float]], schwellen: tuple[float, ...] = SCHWELLEN
) -> list[str]:
    """Je Ordner eine Zeile „Treffer/Aufnahmen“ für jede Schwelle."""
    breite = max([len(name) for name in reihen] + [len("Rufe")])
    zeilen = [f"{'Rufe':<{breite}}  " + "  ".join(f"{zahl(s):>5}" for s in schwellen)]
    for name, werte in reihen.items():
        spalten = (f"{treffer(werte, s)}/{len(werte)}" for s in schwellen)
        zeilen.append(f"{name:<{breite}}  " + "  ".join(f"{t:>5}" for t in spalten))
    return zeilen


def abend_tabelle(
    stuecke: list[list[float]], schwellen: tuple[float, ...] = SCHWELLEN
) -> list[str]:
    """Fehlauslöser je Schwelle, absolut und je Stunde. `stuecke`: die Werte je Datei.

    Gezählt wird je Datei: An der Naht zwischen zwei Stücken könnte derselbe Laut zweimal
    zählen. Das überschätzt die Fehlauslöser höchstens, es verschweigt keinen.
    """
    stunden = sum(len(werte) for werte in stuecke) * RAHMEN_S / 3600
    sperre = round(SPERRE_S / RAHMEN_S)
    zeilen = ["Schwelle  Fehlauslöser  je Stunde"]
    for s in schwellen:
        anzahl = sum(len(ausloeser(werte, s, sperre)) for werte in stuecke)
        je_stunde = zahl(anzahl / stunden) if stunden else "–"
        zeilen.append(f"{zahl(s):>8}  {anzahl:>12}  {je_stunde:>9}")
    return zeilen


# --- Dateien -------------------------------------------------------------------------------
def wav_schreiben(pfad: Path, proben: array) -> None:
    with wave.open(str(pfad), "wb") as datei:
        datei.setnchannels(1)
        datei.setsampwidth(2)
        datei.setframerate(RATE)
        datei.writeframes(proben.tobytes())


def wav_lesen(pfad: Path) -> array:
    """Liest eine Aufnahme dieses Werkzeugs. Alles andere wird abgelehnt statt umgerechnet:
    Ein falsch gelesenes Format ergäbe still falsche Zahlen."""
    with wave.open(str(pfad), "rb") as datei:
        form = (datei.getnchannels(), datei.getsampwidth(), datei.getframerate())
        if form != (1, 2, RATE):
            raise Abbruch(
                f"{pfad}: erwartet mono, 16 Bit, {RATE} Hz, ist aber "
                f"{form[0]} Kanäle, {form[1] * 8} Bit, {form[2]} Hz"
            )
        proben = array("h")
        proben.frombytes(datei.readframes(datei.getnframes()))
    return proben


def wav_dateien(ordner: Path) -> list[Path]:
    if not ordner.is_dir():
        raise Abbruch(f"Ordner fehlt: {ordner}")
    dateien = sorted(ordner.glob("*.wav"))
    if not dateien:
        raise Abbruch(f"Keine .wav-Dateien in {ordner}")
    return dateien


# --- aufnehmen (Pi) ------------------------------------------------------------------------
def arecord(sekunden: int | None = None) -> list[str]:
    befehl = ["arecord", "-q", "-D", MIKRO, "-f", "S16_LE", "-r", str(RATE)]
    befehl += ["-c", str(XVF_KANAELE), "-t", "raw"]
    if sekunden is not None:
        befehl += ["-d", str(sekunden)]
    return befehl


@contextmanager
def dienst_angehalten():
    """Hält den Küchen-Dienst an, solange aufgenommen wird, und startet ihn danach wieder,
    auch nach Strg-C. Lief er vorher nicht, bleibt er aus."""
    lief = (
        subprocess.run(
            ["systemctl", "is-active", "--quiet", DIENST], check=False
        ).returncode
        == 0
    )
    if lief:
        print(f"Halte {DIENST} an (er hält das Mikrofon fest) …")
        if (
            subprocess.run(
                ["sudo", "systemctl", "stop", DIENST], check=False
            ).returncode
            != 0
        ):
            raise Abbruch(
                f"{DIENST} ließ sich nicht anhalten, es wurde nichts aufgenommen"
            )
    try:
        yield
    finally:
        if lief:
            if (
                subprocess.run(
                    ["sudo", "systemctl", "start", DIENST], check=False
                ).returncode
                == 0
            ):
                print(f"{DIENST} läuft wieder.")
            else:
                print(
                    f"ACHTUNG: {DIENST} ist nicht wieder gestartet. Von Hand: sudo systemctl start {DIENST}",
                    file=sys.stderr,
                )


def ton_datei(ordner: Path) -> Path:
    """Ein kurzer Ton als Zeichen „jetzt rufen“."""
    pfad = ordner / "ton.wav"
    dauer, hertz = 0.15, 880
    proben = array(
        "h",
        (
            int(9000 * math.sin(2 * math.pi * hertz * n / RATE))
            for n in range(int(dauer * RATE))
        ),
    )
    wav_schreiben(pfad, proben)
    return pfad


def rufe_aufnehmen(ordner: Path, anzahl: int, sekunden: int) -> None:
    ordner.mkdir(parents=True, exist_ok=True)
    if any(ordner.glob("ruf-*.wav")):
        raise Abbruch(
            f"In {ordner} liegen schon Rufe. Anderen Ordner nehmen oder die alten löschen."
        )
    ton_geht = True
    leise = 0
    with tempfile.TemporaryDirectory() as temp, dienst_angehalten():
        ton = ton_datei(Path(temp))
        print(f"{anzahl} Rufe, je {sekunden} s. Nach jedem Ton einmal „Elektra“ sagen.")
        time.sleep(3)
        for n in range(1, anzahl + 1):
            if (
                ton_geht
                and subprocess.run(["pw-play", str(ton)], check=False).returncode != 0
            ):
                ton_geht = False
                print(
                    "Der Ton lässt sich nicht abspielen (pw-play). Weiter ohne Ton: "
                    "rufen, sobald die Zeile „Ruf …“ erscheint.",
                    file=sys.stderr,
                )
            print(f"Ruf {n}/{anzahl} …", end=" ", flush=True)
            lauf = subprocess.run(
                arecord(sekunden), stdout=subprocess.PIPE, check=False
            )
            proben = kanal0(lauf.stdout)
            if lauf.returncode != 0 or len(proben) < RATE:
                raise Abbruch(
                    f"arecord lieferte keinen Ton (Code {lauf.returncode}, Gerät {MIKRO})"
                )
            pegel = pegel_db(proben)
            wav_schreiben(ordner / f"ruf-{n:02d}.wav", proben)
            if pegel < LEISE_DB:
                leise += 1
                print(f"Spitze {zahl(pegel)} dB, kaum Ton")
            else:
                print(f"Spitze {zahl(pegel)} dB")
            time.sleep(1)
    print(f"{anzahl} Rufe in {ordner}.")
    if leise:
        print(
            f"ACHTUNG: {leise} davon sind fast still. Anhören, bevor gezählt wird.",
            file=sys.stderr,
        )


def abend_aufnehmen(ordner: Path, stunden: float) -> None:
    ordner.mkdir(parents=True, exist_ok=True)
    if any(ordner.glob("abend-*.wav")):
        raise Abbruch(
            f"In {ordner} liegt schon eine Aufnahme. Anderen Ordner nehmen oder die alte löschen."
        )
    ziel_s = stunden * 3600
    roh_je_stueck = STUECK_S * RATE * XVF_KANAELE * 2
    gesamt_s = 0.0
    with dienst_angehalten():
        prozess = subprocess.Popen(arecord(), stdout=subprocess.PIPE)
        print(
            f"Nehme {zahl(stunden)} h auf, in Stücken von {STUECK_S // 60} Minuten. Strg-C hört früher auf."
        )
        try:
            n = 0
            while gesamt_s < ziel_s:
                rest = int(min(ziel_s - gesamt_s, STUECK_S) * RATE) * XVF_KANAELE * 2
                roh = prozess.stdout.read(min(roh_je_stueck, rest))
                proben = kanal0(roh)
                if not proben:
                    raise Abbruch(
                        f"arecord hat aufgehört (Code {prozess.poll()}, Gerät {MIKRO}) nach {zeit_text(gesamt_s)}"
                    )
                wav_schreiben(ordner / f"abend-{n:03d}.wav", proben)
                gesamt_s += len(proben) / RATE
                print(
                    f"abend-{n:03d}.wav, Spitze {zahl(pegel_db(proben))} dB, bisher {zahl(gesamt_s / 3600, 2)} h"
                )
                n += 1
        except KeyboardInterrupt:
            print("\nAbgebrochen. Das angefangene Stück fehlt, die fertigen bleiben.")
        finally:
            prozess.terminate()
            prozess.wait()
    print(f"{zahl(gesamt_s / 3600, 2)} h in {ordner}.")


# --- zählen (Pi oder Mac) ------------------------------------------------------------------
class Erkenner:
    """Dünne Hülle um openwakeword.Model; nicht Teil der Tests (braucht Paket und Modell)."""

    def __init__(self, modell: Path) -> None:
        if not modell.is_file():
            raise Abbruch(f"Modell fehlt: {modell}")
        if modell.suffix != ".onnx":
            raise Abbruch(
                f"{modell.name}: gebraucht wird die .onnx-Datei (auf dem Pi gibt es kein tflite-runtime)"
            )
        try:
            import numpy
            from openwakeword.model import Model
        except ImportError as fehler:
            raise Abbruch(
                f"openwakeword oder numpy fehlt ({fehler}); Einrichtung: docs/weckwort-probe.md"
            ) from fehler
        self.numpy = numpy
        try:
            self.modell = Model(
                wakeword_models=[str(modell)], inference_framework="onnx"
            )
        except Exception as fehler:  # onnxruntime wirft je nach Ursache Verschiedenes
            raise Abbruch(
                f"Modell nicht ladbar: {fehler}. Fehlen die Grundmodelle von openWakeWord? "
                "Siehe docs/weckwort-probe.md, „Einrichten“."
            ) from fehler

    def werte(self, proben: array) -> list[float]:
        """Ein Wert zwischen 0 und 1 je Rahmen von 80 ms."""
        self.modell.reset()
        ergebnis = []
        for stueck in rahmen(proben):
            antwort = self.modell.predict(
                self.numpy.frombuffer(stueck.tobytes(), dtype=self.numpy.int16)
            )
            if len(antwort) != 1:
                raise Abbruch(f"Erwartet ein Modell, geladen sind: {sorted(antwort)}")
            ergebnis.append(float(next(iter(antwort.values()))))
        return ergebnis


def zaehlen(
    modell: Path, rufe: list[Path], abend: Path | None, schwelle: float
) -> None:
    if not rufe and abend is None:
        raise Abbruch(
            "Nichts zu zählen: --rufe ORDNER … und/oder --abend ORDNER angeben"
        )
    erkenner = Erkenner(modell)
    ton_s = 0.0
    rechen_s = 0.0
    print(f"Modell {modell.name}")

    if rufe:
        reihen: dict[str, list[float]] = {}
        for ordner in rufe:
            hoechst = []
            for datei in wav_dateien(ordner):
                proben = wav_lesen(datei)
                proben.extend([0] * int(NACHLAUF_S * RATE))
                anfang = time.perf_counter()
                werte = erkenner.werte(proben)
                rechen_s += time.perf_counter() - anfang
                ton_s += len(proben) / RATE
                hoechst.append(max(werte, default=0.0))
            reihen[ordner.name] = hoechst
        print()
        print("\n".join(rufe_tabelle(reihen)))
        print(f"\nHöchster Wert je Ruf (unter {zahl(schwelle)} wäre überhört):")
        for name, hoechst in reihen.items():
            print(f"  {name}: " + " ".join(zahl(w, 2) for w in hoechst))

    if abend is not None:
        alle: list[list[float]] = []
        funde: list[str] = []
        sperre = round(SPERRE_S / RAHMEN_S)
        dateien = wav_dateien(abend)
        for datei in dateien:
            proben = wav_lesen(datei)
            anfang = time.perf_counter()
            werte = erkenner.werte(proben)
            rechen_s += time.perf_counter() - anfang
            ton_s += len(proben) / RATE
            for stelle, wert in ausloeser(werte, schwelle, sperre):
                funde.append(
                    f"  {datei.name} bei {zeit_text(stelle * RAHMEN_S)} (Wert {zahl(wert, 2)})"
                )
            alle.append(werte)
        stunden = sum(len(w) for w in alle) * RAHMEN_S / 3600
        print(f"\nAbend: {zahl(stunden, 2)} h in {len(dateien)} Dateien")
        print("\n".join(abend_tabelle(alle)))
        if funde:
            print(f"\nFehlauslöser bei Schwelle {zahl(schwelle)}, zum Nachhören:")
            print("\n".join(funde))
        else:
            print(f"\nKein Fehlauslöser bei Schwelle {zahl(schwelle)}.")

    if ton_s:
        print(
            f"\nRechenzeit: {zahl(rechen_s)} s für {zahl(ton_s / 60)} min Ton, "
            f"das sind {zahl(100 * rechen_s / ton_s)} % eines Kerns im Dauerbetrieb."
        )


# --- Aufruf --------------------------------------------------------------------------------
def argumente(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe fürs Aktivierungswort (kuechen-display#111)"
    )
    befehle = parser.add_subparsers(dest="befehl", required=True)

    rufe = befehle.add_parser("rufe", help="einzelne Rufe aufnehmen (auf dem Pi)")
    rufe.add_argument("ordner", type=Path)
    rufe.add_argument("--anzahl", type=int, default=20)
    rufe.add_argument("--sekunden", type=int, default=4)

    abend = befehle.add_parser("abend", help="Küche ohne Ruf aufnehmen (auf dem Pi)")
    abend.add_argument("ordner", type=Path)
    abend.add_argument("--stunden", type=float, default=3.0)

    zaehl = befehle.add_parser(
        "zaehlen", help="Modell über die Aufnahmen laufen lassen"
    )
    zaehl.add_argument("modell", type=Path, help=".onnx-Datei")
    zaehl.add_argument("--rufe", type=Path, nargs="*", default=[], metavar="ORDNER")
    zaehl.add_argument("--abend", type=Path, metavar="ORDNER")
    zaehl.add_argument(
        "--schwelle",
        type=float,
        default=0.5,
        help="für die Liste der einzelnen Werte und Fehlauslöser (Standard 0,5)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    a = argumente(argv)
    try:
        if a.befehl == "rufe":
            rufe_aufnehmen(a.ordner, a.anzahl, a.sekunden)
        elif a.befehl == "abend":
            abend_aufnehmen(a.ordner, a.stunden)
        else:
            zaehlen(a.modell, a.rufe, a.abend, a.schwelle)
    except Abbruch as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAbgebrochen.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
