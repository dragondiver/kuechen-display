"""Regeln der Kiosk-Seite (pi/kiosk/regeln.js): Alter von Wetter und Terminen (#50), langer Druck (#82).

Die Regel steht in JavaScript, damit die Seite sie nutzt; geprüft wird sie hier mit Node (auf
dem Mac und in GitHub Actions vorhanden, sonst übersprungen)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REGELN = Path(__file__).parents[1] / "kiosk" / "regeln.js"
JETZT = 1_800_000_000  # Unix-Sekunden

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="kein node")


def ist_alt(stand, jetzt_s):
    skript = (
        f"const r = require({json.dumps(str(REGELN))});"
        f"console.log(JSON.stringify(r.istAlt({json.dumps(stand)}, {jetzt_s * 1000})));"
    )
    aus = subprocess.run(
        ["node", "-e", skript], capture_output=True, text=True, check=True
    )
    return json.loads(aus.stdout)


def test_frisch_ist_nicht_blass():
    assert ist_alt(JETZT - 60, JETZT) is False


def test_genau_eine_stunde_ist_noch_frisch():
    assert ist_alt(JETZT - 3600, JETZT) is False


def test_eine_sekunde_mehr_als_eine_stunde_ist_blass():
    assert ist_alt(JETZT - 3601, JETZT) is True


def test_viel_aelter_ist_blass():
    assert ist_alt(JETZT - 6 * 3600, JETZT) is True


@pytest.mark.parametrize("stand", [0, None])
def test_ohne_stand_gibt_es_nichts_zu_verblassen(stand):
    assert ist_alt(stand, JETZT) is False


def lang(dauer_ms, weg_px):
    skript = (
        f"const r = require({json.dumps(str(REGELN))});"
        f"console.log(JSON.stringify(r.langerDruck({dauer_ms}, {weg_px})));"
    )
    aus = subprocess.run(
        ["node", "-e", skript], capture_output=True, text=True, check=True
    )
    return json.loads(aus.stdout)


@pytest.mark.parametrize(
    "dauer_ms,weg_px,erwartet",
    [
        (800, 0, True),  # genau 0,8 s zählt
        (1500, 12, True),  # kleines Wackeln ist erlaubt
        (799, 0, False),  # ein Tippen oder ein kurzer Halt
        (300, 0, False),
        (900, 13, False),  # Wischen oder Rollen
        (900, 80, False),
    ],
)
def test_langer_druck_braucht_zeit_und_ruhe(dauer_ms, weg_px, erwartet):
    assert lang(dauer_ms, weg_px) is erwartet


def uebernehmen(eigen_aktiv, jetzt_ms, schutz_bis_ms):
    skript = (
        f"const r = require({json.dumps(str(REGELN))});"
        f"console.log(JSON.stringify(r.standUebernehmen({json.dumps(eigen_aktiv)}, {jetzt_ms}, {schutz_bis_ms})));"
    )
    aus = subprocess.run(
        ["node", "-e", skript], capture_output=True, text=True, check=True
    )
    return json.loads(aus.stdout)


@pytest.mark.parametrize(
    "eigen,jetzt,bis,erwartet",
    [
        (False, 5000, 0, True),  # Ruhe: dem Dienst glauben
        (True, 5000, 0, False),  # Finger liegt oder Senden steht aus
        (False, 5000, 5001, False),  # kurz nach dem Loslassen
        (False, 5001, 5001, True),  # Schutzzeit genau um
    ],
)
def test_schieber_folgt_dem_stand_nur_in_ruhe(eigen, jetzt, bis, erwartet):
    assert uebernehmen(eigen, jetzt, bis) is erwartet
